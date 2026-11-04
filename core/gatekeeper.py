"""
gatekeeper.py
确定性门禁与阶梯剪枝漏斗拦截器 (AEGIS 工业级全维度重构版)
彻底解决：
1. 只看 Sharpe 放过垃圾 Fitness (0.38) 的致命漏洞 -> 强制 Fitness >= 1.00
2. 放过不可行 Margin (1.74 bps) 的亏损漏洞 -> 强制美股 USA Margin >= 10.0 bps (0.0010)
3. 放过疯狂换手 (121.72%) 的漏洞 -> 强制 Turnover 位于合理区间 [5.0%, 50.0%]
4. 阶梯漏斗早停: Step 1 (若无 |Sharpe|>=1.0 立即物理熔断，绝不纠缠); Step 2 (fail_num==0 且 Margin>=基准50%)
5. 库内相关性严格卡死: ProdCorr < 0.70, 本地 SelfCorr <= 0.60
"""

import json
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    from quant_framework.core.rag_memory import RAGMemoryEngine
except ImportError:
    from core.rag_memory import RAGMemoryEngine

class Gatekeeper:
    # 区域差异化基准 Margin 门槛 (AEGIS 标准)
    REGION_MIN_MARGIN_BPS = {
        "USA": 10.0,
        "EUR": 10.0,
        "ASI": 15.0,
        "GLB": 15.0,
        "GBR": 15.0,
        "DEU": 15.0,
        "IND": 20.0,
        "MEA": 20.0
    }

    @classmethod
    def get_min_margin_bps(cls, region: str) -> float:
        return cls.REGION_MIN_MARGIN_BPS.get(region.upper(), 10.0)

    # 平台生产库相关性可能出现的全部字段名 (Brain 原生返回 prodCorrelation)
    PROD_CORR_KEYS = (
        "pcorr", "prod_corr", "prodCorr", "prodCorrelation",
        "production_correlation", "prod_correlation"
    )

    @classmethod
    def extract_prod_corr(cls, res: dict):
        """
        健壮提取平台生产库相关性 (ProdCorr)。

        2026-10-31 根因修复: 旧实现只读 res["pcorr"]，而 Brain 真实返回体把该指标放在
        metrics/is 下的 prodCorrelation，导致所有候选的 ProdCorr 恒为 0.0，
        0.7164 这种越线因子被静默放行。现做多层级、多别名扫描，并返回 None 表示「未核实」。
        """
        if not isinstance(res, dict):
            return None
        values = []
        containers = [res]
        for key in ("is", "metrics", "settings", "ra", "stats"):
            sub = res.get(key)
            if isinstance(sub, dict):
                containers.append(sub)
        for box in containers:
            for k in cls.PROD_CORR_KEYS:
                v = box.get(k)
                if v is None:
                    continue
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    continue
                if fv != fv:  # NaN
                    continue
                if 0.0 <= fv <= 1.0:
                    values.append(fv)
                elif 1.0 < fv <= 100.0:  # 平台偶发按百分比返回
                    values.append(fv / 100.0)
        if not values:
            return None
        # 多个容器取值不一致时取最大 (最保守)
        return round(max(values), 4)

    @classmethod
    def extract_self_corr(cls, res: dict):
        """健壮提取个人存量库自相关性 (SelfCorr)，未核实返回 None"""
        if not isinstance(res, dict):
            return None
        values = []
        for box in [res] + [res.get(k) for k in ("is", "metrics", "settings") if isinstance(res.get(k), dict)]:
            for k in ("sc", "self_corr", "selfCorr", "selfCorrelation", "self_correlation"):
                v = box.get(k)
                if v is None:
                    continue
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    continue
                if fv == fv and 0.0 <= fv <= 1.0:
                    values.append(fv)
        return round(max(values), 4) if values else None

    @classmethod
    def extract_expression(cls, res: dict) -> str:
        """从 WorldQuant Brain 各种可能的回测结果数据结构中健壮提取表达式代码"""
        if not isinstance(res, dict):
            return ""
        regular = res.get("regular")
        if isinstance(regular, dict):
            reg_code = regular.get("code")
            if reg_code:
                return reg_code
        elif isinstance(regular, str) and regular:
            return regular

        settings = res.get("settings")
        if isinstance(settings, dict):
            set_reg = settings.get("regular")
            if isinstance(set_reg, str) and set_reg:
                return set_reg
            elif isinstance(set_reg, dict) and set_reg.get("code"):
                return set_reg.get("code")

        return res.get("code") or res.get("expression") or ""

    @classmethod
    def audit_step1_batch(
        cls,
        sim_result_data: dict,
        min_sharpe: float = 1.0,
        expected_polarity: int = 1,
        check_parasitism: bool = True
    ) -> dict:
        """
        Step 1 极速初筛 (Staged Funnel Step 1):
        批次中若无任何一个变体满足 |Sharpe| >= 1.0，判定当前主信号无统计显著性，
        立即物理熔断跳出，绝不浪费算力纠缠！
        包含因果极性一致性核验 (expected_polarity) 与高阶中性化残差寄生审计 (check_parasitism)。
        """
        results = sim_result_data.get("alpha_results", sim_result_data if isinstance(sim_result_data, list) else [sim_result_data])
        
        qualified_seeds = []
        all_sharpes = {}
        max_abs_sharpe = 0.0

        # 统计批次中基础中性化 (SUBINDUSTRY / INDUSTRY / SECTOR / MARKET) 的最高表现
        base_neuts = {"SUBINDUSTRY", "INDUSTRY", "SECTOR", "MARKET"}
        base_sharpes = []
        for res in results:
            if res.get("status") in ["ERROR", "CANCELLED", "FAILED"] or "error" in res:
                continue
            r_neut = (
                res.get("neutralization") or
                res.get("settings", {}).get("neutralization") or
                res.get("neut") or ""
            ).upper()
            is_m = res.get("is") or res.get("metrics") or {}
            raw_sh = is_m.get("sharpe")
            if raw_sh is not None:
                try:
                    sh = float(raw_sh)
                    if r_neut in base_neuts:
                        base_sharpes.append(abs(sh))
                except (ValueError, TypeError):
                    pass
        max_base_sharpe = max(base_sharpes) if base_sharpes else 0.0

        valid_eval_count = 0
        for idx, res in enumerate(results):
            if res.get("status") in ["ERROR", "CANCELLED", "FAILED"] or "error" in res:
                continue
            expr = cls.extract_expression(res)
            if not expr or expr.startswith("alpha_"):
                continue
            is_m = res.get("is") or res.get("metrics") or {}
            raw_sharpe = is_m.get("sharpe")
            if raw_sharpe is None:
                continue
            try:
                sharpe = float(raw_sharpe)
                all_sharpes[expr] = sharpe
            except (ValueError, TypeError):
                continue

            valid_eval_count += 1
            if abs(sharpe) > max_abs_sharpe:
                max_abs_sharpe = abs(sharpe)
            
            if abs(sharpe) >= min_sharpe:
                raw_neut = (
                    res.get("neutralization") or
                    res.get("settings", {}).get("neutralization") or
                    res.get("neut") or ""
                ).upper()

                # 高阶中性化残差寄生审计 (check_parasitism)
                is_high_order = bool(raw_neut and raw_neut not in base_neuts)
                if check_parasitism and is_high_order and base_sharpes and max_base_sharpe < 0.75:
                    print(f"⚠️ [寄生剔除] 变体 {expr[:40]}... 在高阶中性化 {raw_neut} 下 Sharpe={sharpe:.2f}，但在基础行业中性化下最高 |Sharpe|={max_base_sharpe:.2f} < 0.75，判定为模型残差寄生！")
                    continue

                # 因果极性一致性审计 (expected_polarity)
                has_reverse = ("reverse(" in expr.lower()) or expr.strip().startswith("-")
                effective_polarity = -expected_polarity if has_reverse else expected_polarity
                is_polarity_inverted = bool(sharpe < 0 or (effective_polarity * sharpe < 0))
                status_str = "POLARITY_INVERTED" if is_polarity_inverted else "STEP1_PASSED"

                fitness = float(is_m.get("fitness") or 0.0)
                turnover = float(is_m.get("turnover") or 0.0)
                if "margin_bps" in is_m:
                    margin_bps = float(is_m.get("margin_bps") or 0.0)
                else:
                    margin_bps = float(is_m.get("margin") or 0.0) * 10000.0
                parsed_chk = cls.parse_brain_checks(res)
                pcorr_val = cls.extract_prod_corr(res)
                alpha_id = res.get("id") or res.get("alpha_id")
                qualified_seeds.append({
                    "id": alpha_id,
                    "alpha_id": alpha_id,
                    "expression": expr,
                    "sharpe": sharpe,
                    "fitness": fitness,
                    "margin_bps": margin_bps,
                    "turnover": turnover,
                    "neutralization": raw_neut,
                    "prod_corr": pcorr_val,
                    "pcorr": pcorr_val,
                    "prod_corr_verified": pcorr_val is not None,
                    "self_corr": cls.extract_self_corr(res),
                    "is_polarity_inverted": is_polarity_inverted,
                    "fail_count": parsed_chk["fail_count"],
                    "fails": parsed_chk["fails"],
                    "warning_count": len(parsed_chk["warnings"]),
                    "warnings": parsed_chk["warnings"],
                    "cluster_sharpe": parsed_chk["cluster_sharpe"],
                    "ladder_2y_sharpe": parsed_chk["ladder_2y_sharpe"],
                    "sub_universe_sharpe": parsed_chk["sub_universe_sharpe"],
                    "cw_failed": parsed_chk["cw_failed"],
                    "metrics": is_m,
                    "status": status_str
                })

        # 区分真实的统计失效与仿真平台网络/并发异常取消 (CANCELLED / ERROR)
        if valid_eval_count == 0 and len(results) > 0 and not os.environ.get("AEGIS_MOCK_MODE"):
            return {
                "should_prune": False,
                "max_abs_sharpe": 0.0,
                "qualified_count": 0,
                "qualified_seeds": [],
                "platform_failure": True,
                "message": (
                    f"⚠️ 【仿真平台异常未决】批次中所有变体均未能在平台完成有效计算 (全部为 CANCELLED/ERROR/无指标)！\n"
                    f"平台基础设施异常绝不假定为信号失效剪枝！保留当前主信号种子待恢复后继续回测。"
                )
            }

        should_prune = len(qualified_seeds) == 0
        return {
            "should_prune": should_prune,
            "max_abs_sharpe": max_abs_sharpe,
            "qualified_count": len(qualified_seeds),
            "qualified_seeds": qualified_seeds,
            "all_sharpes": all_sharpes,
            "platform_failure": False,
            "message": (
                f"【Step 1 熔断退出】全批变体最高 |Sharpe| 仅为 {max_abs_sharpe:.2f} (< {min_sharpe:.2f})！"
                f"判定主信号为伪因果，立即剪枝，秒级切换下一个主信号！"
            ) if should_prune else f"【Step 1 通过】捕获 {len(qualified_seeds)} 条达标种子 (最高 |Sharpe| = {max_abs_sharpe:.2f})"
        }

    @classmethod
    def parse_brain_checks(cls, res: dict) -> dict:
        """
        从 WorldQuant Brain 真实的 res['is']['checks'] 列表中解析合规检查项
        Brain API checks 格式: [{"name": "CONCENTRATED_WEIGHT", "result": "FAIL", "value": ...}, ...]
        同时向下兼容 mock 测试字典
        """
        is_data = res.get("is") or res.get("metrics") or {}
        checks_list = is_data.get("checks")
        if checks_list is None:
            checks_list = res.get("checks", [])

        fails = []
        warnings = []
        cluster_sharpe = None
        ladder_2y_sharpe = None
        sub_universe_sharpe = None

        if isinstance(checks_list, list):
            for chk in checks_list:
                if not isinstance(chk, dict):
                    continue
                name = chk.get("name", "")
                result = str(chk.get("result", "")).upper()
                val = chk.get("value")

                if result == "FAIL":
                    fails.append(name)
                elif result == "WARNING":
                    warnings.append(name)

                name_upper = name.upper()
                if "CLUSTER" in name_upper:
                    try:
                        cluster_sharpe = float(val) if val is not None else None
                    except (ValueError, TypeError):
                        pass
                elif "LADDER" in name_upper:
                    try:
                        ladder_2y_sharpe = float(val) if val is not None else None
                    except (ValueError, TypeError):
                        pass
                elif "SUB_UNIVERSE" in name_upper:
                    try:
                        sub_universe_sharpe = float(val) if val is not None else None
                    except (ValueError, TypeError):
                        pass
        elif isinstance(checks_list, dict):
            fails = list(checks_list.get("fails", []))
            warnings = list(checks_list.get("warnings", []))
            cluster_sharpe = checks_list.get("cluster_sharpe")

        # 兼容旧测试数据中的 ra 字典
        ra = res.get("ra", {})
        if ra:
            if ra.get("ra_failed") and not fails:
                fails.append("PLATFORM_FAILED")
            if "fail_num" in ra and ra["fail_num"] > len(fails):
                for _ in range(ra["fail_num"] - len(fails)):
                    fails.append("UNKNOWN_FAIL")
            if "ra_failed_checks" in ra:
                for f in ra["ra_failed_checks"]:
                    if f not in fails:
                        fails.append(f)

        return {
            "fail_count": len(fails),
            "fails": fails,
            "warnings": warnings,
            "cluster_sharpe": cluster_sharpe,
            "ladder_2y_sharpe": ladder_2y_sharpe,
            "sub_universe_sharpe": sub_universe_sharpe,
            "cw_failed": "CONCENTRATED_WEIGHT" in fails
        }

    @classmethod
    def audit_step2_batch(cls, sim_result_data: dict, region: str = "USA") -> list:
        """
        Step 2 合规门槛 (Staged Funnel Step 2):
        必须同时满足：
        1. 平台校验无阻断错误: fail_num == 0
        2. Margin 达到区域基准的 50% (例如 USA 必须 >= 5.0 bps)
        3. 换手率不超过 70%
        """
        results = sim_result_data.get("alpha_results", sim_result_data if isinstance(sim_result_data, list) else [sim_result_data])
        min_margin_bps = cls.get_min_margin_bps(region)
        step2_margin_threshold = (min_margin_bps * 0.5) / 10000.0  # 换算为比率

        passed = []
        for idx, res in enumerate(results):
            if res.get("status") in ["ERROR", "CANCELLED", "FAILED"] or "error" in res:
                continue
            expr = cls.extract_expression(res)
            if not expr or expr.startswith("alpha_"):
                continue
            is_m = res.get("is") or res.get("metrics") or {}
            raw_sharpe = is_m.get("sharpe")
            if raw_sharpe is None:
                continue
            try:
                sharpe = float(raw_sharpe)
                fitness = float(is_m.get("fitness", 0.0))
                margin = float(is_m.get("margin", 0.0))
                turnover = float(is_m.get("turnover", 0.0))
            except (ValueError, TypeError):
                continue

            parsed_checks = cls.parse_brain_checks(res)
            fail_num = parsed_checks["fail_count"]

            fails = []
            if abs(sharpe) < 1.0:
                fails.append(f"|Sharpe| {abs(sharpe):.2f} < 1.0")
            if fail_num > 0:
                fails.append(f"平台检查项不合格 (fail_num = {fail_num}, 项: {parsed_checks['fails']})")
            if margin < step2_margin_threshold:
                fails.append(f"Margin {margin*10000:.2f} bps < Step2 门槛 {min_margin_bps*0.5:.1f} bps")
            if turnover > 0.70:
                fails.append(f"换手率过高 {turnover*100:.1f}% > 70%")

            if not fails:
                alpha_id = res.get("id") or res.get("alpha_id")
                passed.append({
                    "id": alpha_id,
                    "alpha_id": alpha_id,
                    "expression": expr,
                    "sharpe": sharpe,
                    "fitness": fitness,
                    "margin_bps": margin * 10000,
                    "turnover": turnover,
                    "fail_count": fail_num,
                    "fails": parsed_checks["fails"],
                    "warning_count": len(parsed_checks["warnings"]),
                    "warnings": parsed_checks["warnings"],
                    "cluster_sharpe": parsed_checks["cluster_sharpe"],
                    "ladder_2y_sharpe": parsed_checks["ladder_2y_sharpe"],
                    "sub_universe_sharpe": parsed_checks["sub_universe_sharpe"],
                    "status": "STEP2_PASSED"
                })
            else:
                print(f"[Gatekeeper Step 2 REJECT] {', '.join(fails)} | Expr: {expr[:40]}...")

        return passed

    @classmethod
    def audit_final_alpha(cls, sim_result_data: dict, region: str = "USA", pcorr_max: float = 0.70,
                          sc_max: float = 0.60, require_corr_verified: bool = True) -> list:
        """
        终极全维度生产级准入门禁 (Submission-Grade Gate):
        彻底封死一切垃圾与违规因子：
        1. Sharpe >= 1.58
        2. Fitness >= 1.00 (彻底斩断 0.38 垃圾)
        3. Margin >= 区域门槛 (USA/EUR >= 10 bps, ASI/GLB >= 15 bps, IND/MEA >= 20 bps) (彻底斩断 1.74 bps)
        4. Turnover ∈ [5.0%, 50.0%] (彻底斩断 121.72% 畸高换手)
        5. Checks: fail_num == 0 且集中度无违规
        6. 相关性: 平台 ProdCorr < 0.70, 本地 SelfCorr <= 0.60
        7. 相关性必须「已核实」: 若结果体中完全没有 ProdCorr 字段，一律不予放行，
           必须先跑 /alphas/{id}/correlations/prod 探针确认后再提交
           (可用环境变量 AEGIS_ALLOW_UNVERIFIED_PCORR=1 临时降级为告警)。
        """
        results = sim_result_data.get("alpha_results", sim_result_data if isinstance(sim_result_data, list) else [sim_result_data])
        min_margin_bps = cls.get_min_margin_bps(region)
        margin_threshold = min_margin_bps / 10000.0
        allow_unverified = os.environ.get("AEGIS_ALLOW_UNVERIFIED_PCORR") == "1"
        require_corr_verified = require_corr_verified and not allow_unverified

        passed_final = []
        corr_blocked = []

        for res in results:
            if res.get("status") in ["ERROR", "CANCELLED", "FAILED"] or "error" in res:
                continue
            expr = cls.extract_expression(res)
            if not expr or expr.startswith("alpha_") or expr == "unknown":
                continue
            is_m = res.get("is") or res.get("metrics") or {}
            raw_sharpe = is_m.get("sharpe")
            if raw_sharpe is None:
                continue
            try:
                sharpe = float(raw_sharpe)
                fitness = float(is_m.get("fitness", 0.0))
                margin = float(is_m.get("margin", 0.0))
                turnover = float(is_m.get("turnover", 0.0))
                two_year = float(is_m.get("two_year_sharpe", is_m.get("sharpe_2y", 0.0)))
            except (ValueError, TypeError):
                continue
            
            parsed_checks = cls.parse_brain_checks(res)
            fail_checks = parsed_checks["fails"]
            fail_num = parsed_checks["fail_count"]
            cw_failed = parsed_checks["cw_failed"]

            pcorr = cls.extract_prod_corr(res)
            pcorr_verified = pcorr is not None
            sc = cls.extract_self_corr(res)

            fails = []
            if sharpe < 1.58:
                fails.append(f"Sharpe {sharpe:.2f} < 1.58")
            if fitness < 1.00:
                fails.append(f"Fitness {fitness:.2f} < 1.00 (最重要的指标严重不合格)")
            if margin < margin_threshold:
                fails.append(f"Margin {margin*10000:.2f} bps < {region} 区域死线 {min_margin_bps:.1f} bps (无法覆盖交易滑点)")
            if turnover > 0.50:
                fails.append(f"换手率过高 {turnover*100:.1f}% > 50.0% (高频交易消耗利润)")
            if turnover < 0.05:
                fails.append(f"换手率过低 {turnover*100:.1f}% < 5.0% (仓位几乎不动)")
            if fail_num > 0:
                fails.append(f"平台检查项不合格 (fail_num={fail_num}, 违规项: {fail_checks})")
            if cw_failed:
                fails.append("持仓过分集中 (CONCENTRATED_WEIGHT)")
            if pcorr is not None and pcorr >= pcorr_max:
                fails.append(f"平台生产库相关性 {pcorr:.3f} >= {pcorr_max} (严重共线性无法提交)")
            if sc is not None and sc > sc_max:
                fails.append(f"个人存量库自相关性 {sc:.3f} > {sc_max} (与已有提交撞车)")
            if not pcorr_verified:
                msg = "平台生产库相关性 ProdCorr 未核实 (结果体缺少 prodCorrelation/pcorr 字段)"
                if require_corr_verified:
                    fails.append(msg + "，严禁在未核实相关性的情况下提交")
                else:
                    print(f"⚠️ [Gatekeeper Final] {msg}，已按 AEGIS_ALLOW_UNVERIFIED_PCORR 降级为告警。")

            if not fails:
                alpha_id = res.get("id") or res.get("alpha_id")
                passed_final.append({
                    "id": alpha_id,
                    "alpha_id": alpha_id,
                    "expression": expr,
                    "sharpe": sharpe,
                    "fitness": fitness,
                    "margin_bps": margin * 10000,
                    "turnover_pct": turnover * 100,
                    "turnover": turnover,
                    "pcorr": pcorr,
                    "prod_corr": pcorr,
                    "prod_corr_verified": pcorr_verified,
                    "sc": sc,
                    "fail_count": fail_num,
                    "fails": fail_checks,
                    "warning_count": len(parsed_checks["warnings"]),
                    "warnings": parsed_checks["warnings"],
                    "cluster_sharpe": parsed_checks["cluster_sharpe"],
                    "ladder_2y_sharpe": parsed_checks["ladder_2y_sharpe"],
                    "sub_universe_sharpe": parsed_checks["sub_universe_sharpe"],
                    "two_year_sharpe": two_year,
                    "status": "APPROVED_SUBMITTABLE"
                })
            else:
                if any("相关性" in f for f in fails):
                    corr_blocked.append({"expression": expr, "pcorr": pcorr, "fails": fails})
                print(f"[Gatekeeper Final REJECT] 因子被拦截: {', '.join(fails)}")

        if corr_blocked:
            print(
                f"🔗 [相关性拦截] {len(corr_blocked)} 条因子仅因 ProdCorr/SelfCorr 未过线被拦，"
                f"已转入下一轮去拥挤处方队列 (症状 prod_corr_overflow)。"
            )
        return passed_final

    @classmethod
    def is_near_miss_champion(cls, res: dict, region: str = "USA", allow_pending_prod_corr: bool = False) -> bool:
        """
        六边形准冠军 (Near-Miss Quasi-Champion) 物理鉴定:
        攻克全平台最难两大痛点:
        1. 平台 ProdCorr < 0.70 (且已核实，除非在预取阶段 allow_pending_prod_corr=True)
        2. Margin >= 区域溢价门槛 (min_margin * 1.2，如 GLB >= 18.0 bps, USA >= 12.0 bps)
        3. Sharpe >= 1.45 (离 1.58 仅差一步之遥)
        4. Fitness >= 1.00 且无结构性 Fail (忽略 Brain 原生的 LOW_SHARPE/区域Sharpe 等表现项 Fail) 且 turnover <= 0.50 且无 CW 集中度违规
        """
        if not isinstance(res, dict):
            return False
        is_m = res.get("is") or res.get("metrics") or {}
        raw_sharpe = is_m.get("sharpe") if (res.get("is") or res.get("metrics")) else res.get("sharpe")
        if raw_sharpe is None:
            return False
        try:
            sharpe = float(raw_sharpe)
            fitness = float(is_m.get("fitness") or res.get("fitness") or 0.0)
            turnover = float(is_m.get("turnover") or res.get("turnover") or 0.0)
            if "margin_bps" in res:
                margin_bps = float(res.get("margin_bps") or 0.0)
            elif "margin_bps" in is_m:
                margin_bps = float(is_m.get("margin_bps") or 0.0)
            else:
                margin_bps = float(is_m.get("margin") or res.get("margin") or 0.0) * 10000.0
        except (ValueError, TypeError):
            return False

        pcorr = cls.extract_prod_corr(res)
        if allow_pending_prod_corr:
            if pcorr is not None and pcorr >= 0.70:
                return False
        else:
            if pcorr is None or pcorr >= 0.70:
                return False

        min_margin = cls.get_min_margin_bps(region)
        premium_margin = min_margin * 1.2

        parsed = cls.parse_brain_checks(res)
        cw_failed = parsed["cw_failed"]

        # 核心修复 (漏洞 1): Brain 原生会在 Sharpe < 1.58 时返回 LOW_SHARPE / LOW_GLB_EMEA_SHARPE 等 FAIL 项。
        # 准冠军鉴定只排查结构性/合规性硬伤 (如 CONCENTRATED_WEIGHT, DATA_COVERAGE 等)，忽略 Sharpe/子夏普类表现 Fail。
        perf_fail_keywords = ("SHARPE", "EMEA", "APAC", "REGIONAL", "SUB_UNIVERSE", "LADDER", "2Y", "4Y", "YEARLY")
        structural_fails = [f for f in parsed.get("fails", []) if not any(k in str(f).upper() for k in perf_fail_keywords)]

        return bool(
            fitness >= 1.00 and
            sharpe >= 1.45 and
            margin_bps >= premium_margin and
            turnover <= 0.50 and
            len(structural_fails) == 0 and
            not cw_failed
        )

    @classmethod
    def diagnose_and_route_prescriptions(cls, alpha_metrics: dict, checks_parsed: dict = None, 
                                         yearly_stats: list = None, operator_count: int = 0,
                                         prod_corr: float = None, max_operator_limit: int = 8) -> dict:
        """
        Gate 4: 确定性法医诊断与处方路由锁 (Symptom-to-Prescription Lock)
        由 Python 硬算病灶标签，从 RAG 知识库按需调取处方卡，
        并锁定下一轮允许修改的 AST 算子集合（物理封杀 LLM 乱改参数或无脑堆砌算子）
        """
        checks_parsed = checks_parsed or {}
        # 兼容性: 若传入的是未解析的 raw res / metrics，自动解析
        if "checks" in checks_parsed or "is" in checks_parsed or "metrics" in checks_parsed:
            if "fails" not in checks_parsed or "warnings" not in checks_parsed:
                checks_parsed = cls.parse_brain_checks(checks_parsed)

        fails = checks_parsed.get("fails", [])
        warnings = checks_parsed.get("warnings", [])
        all_issues_str = " ".join(str(x).upper() for x in (fails + warnings))

        yearly_stats = yearly_stats or []
        symptoms = []
        allowed_ast_ops = set(["group_rank", "subindustry", "industry"]) # 基础结构算子常驻

        # 0. 诊断生产库相关性越线 (ProdCorr >= 0.65 预警，>= 0.70 超限)
        if prod_corr is not None:
            try:
                pc = float(prod_corr)
            except (TypeError, ValueError):
                pc = None
            if pc is not None and pc >= 0.65:
                symptoms.append("prod_corr_overflow" if pc >= 0.70 else "prod_corr_elevated_above_065")
                allowed_ast_ops.update([
                    "group_zscore", "group_neutralize", "zscore", "scale",
                    "SUBSTITUTE_LOW_ALPHA_COUNT_FIELD", "ts_delta", "ts_zscore"
                ])

        # 1. 诊断多空持仓失衡与零值死重
        if yearly_stats:
            avg_long = sum(y.get("long_count", 0) for y in yearly_stats) / max(len(yearly_stats), 1)
            avg_short = sum(y.get("short_count", 0) for y in yearly_stats) / max(len(yearly_stats), 1)
            total_count = avg_long + avg_short
            if total_count > 0 and abs(avg_long - avg_short) / total_count > 0.10:
                symptoms.append("dead_weight_imbalance")
                allowed_ast_ops.update(["ts_zscore", "subtract_ts_mean", "trade_when", "rank_tail_power"])

        # 2. 诊断同簇共线性 (含 CLUSTER FAIL/WARNING)
        cluster_sharpe = checks_parsed.get("cluster_sharpe")
        if (cluster_sharpe is not None and cluster_sharpe < 1.58) or "CLUSTER" in all_issues_str:
            symptoms.append("cluster_collinearity")
            allowed_ast_ops.update(["SUBSTITUTE_LOW_ALPHA_COUNT_FIELD", "ts_delta", "group_neutralize", "group_zscore", "quantile_spread_subtract", "winsorize", "signed_power"])

        # 2b. 诊断区域夏普与临界夏普缺口 (LOW_GLB_EMEA_SHARPE, LOW_GLB_APAC_SHARPE, LOW_SHARPE)
        if any(k in all_issues_str for k in ("EMEA", "APAC", "REGIONAL", "LOW_SHARPE")):
            symptoms.append("regional_or_sharpe_deficit")
            allowed_ast_ops.update(["winsorize", "signed_power", "s_log_1p", "group_neutralize", "group_zscore", "subindustry", "country", "ts_decay_linear", "ts_decay_exp_window"])

        # 3. 诊断集中度违规与子宇宙/近两年稳健性警告 (含 FAIL 与 WARNING)
        if "CONCENTRATED" in all_issues_str or checks_parsed.get("cw_failed"):
            symptoms.append("cw_bottleneck")
            allowed_ast_ops.update(["s_log_1p", "winsorize", "signed_power"])

        if any(k in all_issues_str for k in ("SUB_UNIVERSE", "LADDER", "2Y", "ROBUST")):
            symptoms.append("sub_universe_or_2y_instability")
            allowed_ast_ops.update(["winsorize", "ts_zscore", "ts_decay_exp_window", "signed_power", "trade_when"])

        # 4. 诊断换手率过高脉冲 (> 50%)，并授权状态记忆算子 trade_when 冻结无信息日持仓
        turnover = float(alpha_metrics.get("turnover", 0.0))
        if turnover > 0.40 or "TURNOVER" in all_issues_str:
            # 40% 以上即进入 trade_when 的适用区间 (目标压降至 12%~25% 黄金区间)
            allowed_ast_ops.update(["trade_when", "ts_decay_exp_window", "ts_decay_linear"])
        if turnover > 0.50 or "HIGH_TURNOVER" in all_issues_str:
            symptoms.append("turnover_overflow")
            allowed_ast_ops.update(["ts_decay_exp_window", "ts_decay_linear"])

        # 5. 诊断 Power Pool 算子超限 (研究挖掘阶段默认 > 8，准冠军优化阶段才放宽到 > 10)
        if operator_count > max_operator_limit:
            symptoms.append("operator_count_overflow")
            if max_operator_limit >= 10:
                allowed_ast_ops.add("PRUNE_REDUNDANT_OPERATOR_TO_LE_10")
            else:
                allowed_ast_ops.add("PRUNE_REDUNDANT_OPERATOR_TO_LE_8")

        # 动态按需调取专属 Tier-2 知识卡片
        mounted_cards = []
        for tag in symptoms:
            card = RAGMemoryEngine.get_card_on_demand(tag)
            if card and "error" not in card:
                mounted_cards.append(card)

        verdict = {
            "symptoms": symptoms,
            "allowed_mutations": sorted(list(allowed_ast_ops)),
            "rag_prescriptions": mounted_cards
        }
        print(f"\n🩺 [Gatekeeper 处方诊断] 确诊病灶: {symptoms}")
        print(f"🔒 [授权算子白名单]: {verdict['allowed_mutations']}")
        return verdict

    @classmethod
    def audit_raw_signal(cls, sim_result, min_sharpe: float = 1.20, min_positive_years: int = 9) -> list:
        """兼容性接口: 原始主信号硬门禁初筛"""
        if isinstance(sim_result, str):
            with open(sim_result, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = sim_result
        results = data.get("alpha_results", [])
        passed = []
        for res in results:
            is_m = res.get("is") or res.get("metrics") or {}
            sharpe = float(is_m.get("sharpe", -999.0))
            yearly = is_m.get("yearly_stats", [])
            if "positive_years" in is_m:
                pos_years = int(is_m["positive_years"])
            else:
                pos_years = sum(1 for y in yearly if y.get("pnl", 0) > 0)
            if sharpe >= min_sharpe and pos_years >= min_positive_years:
                expr = cls.extract_expression(res)
                passed.append({"expression": expr, "sharpe": sharpe, "is": is_m})
        return passed

if __name__ == "__main__":
    # 模拟 user 刚刚测出的 pwvZJW6j 垃圾数据
    pwvZJW6j_fake = {
        "alpha_results": [{
            "expression": "pwvZJW6j_sample",
            "is": {
                "sharpe": 1.30,
                "fitness": 0.38,
                "margin": 0.000174, # 1.74 bps
                "turnover": 1.2172   # 121.72%
            },
            "pcorr": 0.8670,
            "ra": {"fail_num": 0}
        }]
    }
    print("Testing Gatekeeper on pwvZJW6j:")
    s1 = Gatekeeper.audit_step1_batch(pwvZJW6j_fake)
    print("Step 1:", s1["message"])
    s2 = Gatekeeper.audit_step2_batch(pwvZJW6j_fake, region="USA")
    print("Step 2 passed count:", len(s2))
    final = Gatekeeper.audit_final_alpha(pwvZJW6j_fake, region="USA")
    print("Final passed count:", len(final))
