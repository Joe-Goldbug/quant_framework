"""
crowding_pairing.py
铁律 A 的确定性执行器：主锚字段与归一化字段的「冷热非对称配对」(Asymmetric Crowding Pairing)

背景问题:
    全平台研究员扎堆使用 coverage 最高的前 5 个热门字段，并在最外层无脑套
    group_rank(..., subindustry)，导致新因子的 ProdCorr 长期卡在 0.65 ~ 0.85。

本模块提供的能力:
    1. FieldCrowdingProfiler: 基于数据集全量字段的 alpha_count 分布，计算拥挤度分位
       并划分为 COLD (后 40%) / WARM / HOT (前 30%) 三档；
    2. classify(): 对任一 Stage 0 种子的 fields_used 做配对合法性判定，输出
       主锚字段 (低拥挤、coverage >= 0.25) 与归一锚字段 (coverage >= 0.80)；
    3. annotate_cards(): 把拥挤度分位注入字段卡片，供 LLM 直接读取，不再靠它猜；
    4. candidate_pairs(): 直接给出可用的冷热配对清单，作为 Stage 0 任务卡的硬提示；
    5. enforce(): 对 Stage 0 产出做物理过滤，未构成非对称配对的种子直接拒收。

设计原则: 纯标准库、零副作用、可被 main.py / 测试脚本独立调用。
"""

import bisect
import json
import math
import os
import sys
from typing import Dict, List, Optional, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


COLD_PCT = 0.40          # alpha_count 位于数据集后 40% => 冷门可挖
HOT_PCT = 0.70           # alpha_count 位于数据集前 30% => 全平台拥挤
MIN_ANCHOR_COVERAGE = 0.25   # 主锚字段最低覆盖率
MIN_NORMALIZER_COVERAGE = 0.80  # 归一锚字段最低覆盖率


class FieldCrowdingProfiler:
    """数据集字段拥挤度画像器 (基于 alpha_count 的分位统计)"""

    def __init__(self, fields_meta: Dict[str, dict]):
        self.meta = fields_meta or {}
        self._pct: Dict[str, float] = {}
        self._alpha_count: Dict[str, float] = {}
        self._coverage: Dict[str, float] = {}
        self.min_anchor_coverage: float = MIN_ANCHOR_COVERAGE
        self.min_normalizer_coverage: float = MIN_NORMALIZER_COVERAGE
        self._build()

    # ---------------- 基础解析 ----------------
    @staticmethod
    def _num(meta: dict, *keys, default=None) -> Optional[float]:
        for k in keys:
            v = meta.get(k)
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if math.isnan(fv) or math.isinf(fv):
                continue
            return fv
        return default

    def _build(self):
        rows: List[Tuple[str, float]] = []
        for name, meta in self.meta.items():
            if not isinstance(meta, dict):
                continue
            ac = self._num(meta, "alpha_count", "alphaCount", "alpha_cnt")
            cov = self._num(meta, "coverage", "cover", default=1.0)
            if cov is None:
                cov = 1.0
            self._coverage[name] = cov
            if ac is None:
                continue
            self._alpha_count[name] = ac
            rows.append((name, ac))

        if not rows:
            return

        sorted_acs = sorted(v for _, v in rows)
        n = len(sorted_acs)
        for name, ac in rows:
            # 分位定义: alpha_count 严格小于该值的字段占比 (0 => 全平台尚未挖掘，最冷门)
            # 注意必须用 bisect_left: 数据集里大量字段 alpha_count = 0，用 bisect_right 会把
            # 它们全部误判为最拥挤 (分位 = 全零字段占比)，与事实完全相反。
            rank = bisect.bisect_left(sorted_acs, ac) / float(n)
            self._pct[name] = round(rank, 4)

        # 自适应归一锚与主锚覆盖率门槛 (防止在另类/非美数据集上因无 >= 0.80 字段导致全军覆没)
        all_covs = sorted(self._coverage.values())
        if all_covs:
            high_cov_count = sum(1 for c in all_covs if c >= MIN_NORMALIZER_COVERAGE)
            if high_cov_count < 2:
                # 覆盖率前 25% 分位数 (75th percentile)
                pct_75_idx = min(int(len(all_covs) * 0.75), len(all_covs) - 1)
                pct_75_cov = all_covs[pct_75_idx]
                self.min_normalizer_coverage = max(0.40, pct_75_cov)
                # 若主锚固定门槛超过中位数，也动态同步下调
                med_cov = all_covs[len(all_covs) // 2]
                if self.min_anchor_coverage > med_cov:
                    self.min_anchor_coverage = max(0.15, round(med_cov * 0.8, 2))

    @property
    def has_crowding_data(self) -> bool:
        """数据集中是否存在任何 alpha_count 画像 (全部缺失时无法执行铁律 A 校验)"""
        return bool(self._pct)

    # ---------------- 属性查询 ----------------
    def alpha_count(self, name: str) -> Optional[float]:
        return self._alpha_count.get(name)

    def coverage(self, name: str) -> float:
        return self._coverage.get(name, 1.0)

    def percentile(self, name: str) -> Optional[float]:
        return self._pct.get(name)

    def tier(self, name: str) -> str:
        p = self._pct.get(name)
        if p is None:
            return "UNKNOWN"
        if p <= COLD_PCT:
            return "COLD"
        if p >= HOT_PCT:
            return "HOT"
        return "WARM"

    def is_cold_anchor(self, name: str) -> bool:
        """主锚候选: 低拥挤 (后 40%) 且覆盖率达标"""
        return self.tier(name) == "COLD" and self.coverage(name) >= self.min_anchor_coverage

    def is_scale_anchor(self, name: str) -> bool:
        """归一锚候选: 高覆盖度内生总量字段"""
        return self.coverage(name) >= self.min_normalizer_coverage

    def role_hint(self, name: str) -> str:
        cold = self.is_cold_anchor(name)
        scale = self.is_scale_anchor(name)
        if cold and scale:
            return "低拥挤主锚 + 高覆盖归一锚 (双角色，需另配一个不同字段做分母)"
        if cold:
            return "低拥挤主锚候选 (优先放在分子)"
        if scale:
            return "高覆盖总量归一锚候选 (适合做分母/差分基准)"
        if self.tier(name) == "HOT":
            return "全平台拥挤热点 (仅可做分母，禁止做分子主信号)"
        return "中性字段"

    # ---------------- 配对判定 ----------------
    def classify(self, fields_used: List[str]) -> dict:
        """判定一个 Stage 0 种子的字段组合是否构成冷热非对称配对"""
        used = [f for f in (fields_used or []) if f]

        # 单字段自归一判定 (ATOM Alpha 单因子范式，允许 COLD 及非 HOT 且高覆盖 WARM 字段准入)
        if len(used) == 1:
            single = used[0]
            tier = self.tier(single) if self.has_crowding_data else "COLD"
            cov = self.coverage(single)
            is_valid_single = (self.is_cold_anchor(single) or (tier != "HOT" and cov >= self.min_anchor_coverage)) if self.has_crowding_data else True
            cold_pct = self.percentile(single)
            issues = []
            if self.has_crowding_data and not is_valid_single:
                issues.append("单字段主信号必须为低拥挤度主锚字段 (后 40%) 或高覆盖度非热门主锚字段")
            return {
                "is_asymmetric": is_valid_single,
                "main_anchor": single,
                "normalizer": None,
                "main_anchor_alpha_pct": cold_pct,
                "main_anchor_tier": tier,
                "normalizer_coverage": cov,
                "pairing_score": 1.0,
                "issues": issues,
            }
        cold_anchor = None
        for f in used:
            if self.is_cold_anchor(f):
                cold_anchor = f
                break

        normalizer = None
        for f in used:
            if f == cold_anchor:
                continue
            if self.is_scale_anchor(f):
                normalizer = f
                break

        issues: List[str] = []
        if cold_anchor is None:
            hot_in_use = [f for f in used if self.tier(f) == "HOT"]
            issues.append(
                "缺少低拥挤度主锚字段 (要求 coverage >= %.2f 且 alpha_count 位于数据集后 40%%)"
                % self.min_anchor_coverage
                + ("；当前全是拥挤热点: %s" % hot_in_use if hot_in_use else "")
            )
        if normalizer is None:
            issues.append(
                "缺少高覆盖度总量归一锚 (要求 coverage >= %.2f)" % self.min_normalizer_coverage
            )

        cold_pct = self.percentile(cold_anchor) if cold_anchor else None
        is_asymmetric = cold_anchor is not None and normalizer is not None

        score = 0.0
        if is_asymmetric:
            score = 1.0 + 0.5 * (1.0 - (cold_pct if cold_pct is not None else COLD_PCT))

        return {
            "is_asymmetric": is_asymmetric,
            "main_anchor": cold_anchor,
            "normalizer": normalizer,
            "main_anchor_alpha_pct": cold_pct,
            "main_anchor_tier": self.tier(cold_anchor) if cold_anchor else None,
            "normalizer_coverage": round(self.coverage(normalizer), 3) if normalizer else None,
            "pairing_score": round(score, 3),
            "issues": issues,
        }

    # ---------------- 供 Prompt 使用的产物 ----------------
    def annotate_cards(self, cards: List[dict]) -> List[dict]:
        """把拥挤度分位与角色建议直接写进字段卡片，杜绝 LLM 自行猜测"""
        out = []
        for c in cards:
            if not isinstance(c, dict):
                continue
            card = dict(c)
            name = card.get("name", "")
            p = self.percentile(name)
            card["alpha_pct"] = round(p, 3) if p is not None else None
            card["crowding_tier"] = self.tier(name)
            card["pairing_role_hint"] = self.role_hint(name)
            out.append(card)
        return out

    # 纯标识类字段 (币种代码/财月/标志位) 不适合做经济信号主锚
    IDENTIFIER_HINTS = ("currency_code", "_flag", "fiscal_month", "_id", "iso_code", "ticker")

    def _is_identifier_like(self, name: str) -> bool:
        low = name.lower()
        return any(h in low for h in self.IDENTIFIER_HINTS)

    def candidate_pairs(self, limit: int = 8) -> List[dict]:
        """给出可用的冷热配对清单 (低拥挤主锚 x 高覆盖归一锚)"""
        colds = [
            n for n in self._pct
            if self.is_cold_anchor(n) and not self._is_identifier_like(n)
        ]
        scales = [n for n in self._pct if self.is_scale_anchor(n)]

        # 主锚优先: 覆盖率处于 min_anchor_coverage~0.85 的细分业务流 (过高的覆盖率往往是大路货总量字段)
        def _cold_rank(n):
            cov = self.coverage(n)
            pct = self.percentile(n) or 0.0
            in_band = 0 if self.min_anchor_coverage <= cov <= max(0.85, self.min_normalizer_coverage) else 1
            return (in_band, pct, abs(cov - 0.5))

        # 归一锚优先: 覆盖率最高、且本身被广泛使用 (alpha_pct 高) 的内生总量字段
        def _norm_rank(n):
            return (-self.coverage(n), -(self.percentile(n) or 0.0))

        colds.sort(key=_cold_rank)
        scales.sort(key=_norm_rank)

        pairs: List[dict] = []
        top_scales = scales[:max(3, min(len(scales), 6))]
        for idx, c in enumerate(colds):
            candidates = [s for s in top_scales if s != c]
            if not candidates:
                candidates = [s for s in scales if s != c]
            if not candidates:
                continue
            # 确定性轮换 top 归一锚，打散归一化推荐，防单一字段独占清单造成思维锚定
            s = candidates[idx % len(candidates)]
            pairs.append({
                "main_anchor": c,
                "main_anchor_alpha_count": self.alpha_count(c),
                "main_anchor_alpha_pct": self.percentile(c),
                "main_anchor_coverage": round(self.coverage(c), 3),
                "normalizer": s,
                "normalizer_coverage": round(self.coverage(s), 3),
                "normalizer_alpha_pct": self.percentile(s),
            })
            if len(pairs) >= limit:
                break
        return pairs

    def summary(self) -> dict:
        tiers = {"COLD": 0, "WARM": 0, "HOT": 0, "UNKNOWN": 0}
        for name in self.meta:
            tiers[self.tier(name)] = tiers.get(self.tier(name), 0) + 1
        return {
            "field_total": len(self.meta),
            "alpha_count_known": len(self._pct),
            "tier_counts": tiers,
        }


def enforce_stage0_pairing(
    seeds: List[dict],
    profiler: FieldCrowdingProfiler,
    expected_count: int = 0,
    min_survival_ratio: float = 0.5,
    strict: bool = True,
) -> Tuple[List[dict], List[dict], dict]:
    """
    对 Stage 0 产出执行铁律 A 物理过滤。

    返回 (kept, rejected, report)。
    strict=True 且存活率低于 min_survival_ratio 时，report['should_reject_all'] = True，
    由调用方决定是否整体打回重造 (与现有「存活种子不足即重跑」策略一致)。
    """
    kept: List[dict] = []
    rejected: List[dict] = []

    # 退化模式: 字段画像完全没有 alpha_count 时，铁律 A 无法判定，跳过硬校验而非误杀全部种子
    if not profiler.has_crowding_data:
        for s in seeds:
            if isinstance(s, dict):
                s["pairing"] = {
                    "is_asymmetric": None,
                    "main_anchor": None,
                    "normalizer": None,
                    "pairing_score": 0.0,
                    "issues": ["字段画像缺少 alpha_count，铁律 A 校验已跳过 (degraded)"],
                }
        return list(seeds), [], {
            "total": len(seeds),
            "kept": len(seeds),
            "rejected": 0,
            "survival_ratio": 1.0,
            "min_required": 0,
            "should_reject_all": False,
            "skipped": True,
            "reason": "数据集字段画像缺少 alpha_count，无法计算拥挤度分位，铁律 A 校验降级跳过。",
            "rejected_detail": [],
            "profiler": profiler.summary(),
        }

    for s in seeds:
        if not isinstance(s, dict):
            continue
        fields_used = s.get("fields_used") or []
        pairing = profiler.classify(fields_used)
        s["pairing"] = pairing
        if pairing["is_asymmetric"]:
            kept.append(s)
        else:
            rejected.append({
                "id": s.get("id"),
                "fields_used": fields_used,
                "expression": s.get("expression", ""),
                "issues": pairing["issues"],
            })

    total = len(kept) + len(rejected)
    ratio = (len(kept) / total) if total else 0.0
    target = expected_count or total
    min_required = max(1, int(target * min_survival_ratio)) if target else 0

    report = {
        "total": total,
        "kept": len(kept),
        "rejected": len(rejected),
        "survival_ratio": round(ratio, 3),
        "min_required": min_required,
        "should_reject_all": bool(strict and total > 0 and len(kept) < min_required),
        "rejected_detail": rejected,
        "profiler": profiler.summary(),
    }
    final_kept = [] if report["should_reject_all"] else kept
    return final_kept, rejected, report

