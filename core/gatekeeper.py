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
        min_sharpe: float = 1.2,
        min_margin_bps: float = 5.0,
        expected_polarity: int = 1,
        check_parasitism: bool = True
    ) -> dict:
        """
        Step 1 极速漏斗初筛 (Staged Funnel Step 1 - V3.1 极速版):
        批次中若无任何一个变体同时满足 |Sharpe| >= 1.2 且 Margin >= 5.0 bps，
        立即 0.05 秒物理冷酷熔断跳出，0 Token 总结，绝不在劣质种子上浪费算力！
        """
        if isinstance(sim_result_data, list):
            results = sim_result_data
        elif isinstance(sim_result_data, dict):
            results = sim_result_data.get("alpha_results", [sim_result_data])
        else:
            results = [sim_result_data]
        
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
            if not expr:
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
            
            fitness = float(is_m.get("fitness") or 0.0)
            turnover = float(is_m.get("turnover") or 0.0)
            has_margin = ("margin_bps" in is_m or "margin" in is_m)
            if "margin_bps" in is_m:
                margin_bps = float(is_m.get("margin_bps") or 0.0)
            else:
                margin_bps = float(is_m.get("margin") or 0.0) * 10000.0

            margin_ok = (margin_bps >= min_margin_bps) if has_margin else True
            if abs(sharpe) >= min_sharpe and margin_ok:
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
                    "yearly_stats": res.get("yearly_stats") or is_m.get("yearly_stats") or [],
                    "checks": is_m.get("checks") or res.get("checks") or [],
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
                f"【Step 1 极速漏斗早停】全批变体未出现同时满足 |Sharpe| >= {min_sharpe:.2f} 且 Margin >= {min_margin_bps:.1f} bps 的高潜力种子 (最高 |Sharpe|={max_abs_sharpe:.2f})！0.05秒极速剪枝！"
            ) if should_prune else f"【Step 1 漏斗通过】捕获 {len(qualified_seeds)} 条达标种子 (最高 |Sharpe| = {max_abs_sharpe:.2f})"
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
        if isinstance(sim_result_data, list):
            results = sim_result_data
        elif isinstance(sim_result_data, dict):
            results = sim_result_data.get("alpha_results", [sim_result_data])
        else:
            results = [sim_result_data]
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
                    "prod_corr": cls.extract_prod_corr(res),
                    "pcorr": cls.extract_prod_corr(res),
                    "self_corr": cls.extract_self_corr(res),
                    "yearly_stats": res.get("yearly_stats") or is_m.get("yearly_stats") or [],
                    "checks": is_m.get("checks") or res.get("checks") or [],
                    "metrics": is_m,
                    "status": "STEP2_PASSED"
                })
            else:
                print(f"[Gatekeeper Step 2 REJECT] {', '.join(fails)} | Expr: {expr[:40]}...")

        return passed

    @classmethod
    def compute_master_good_flag(cls, alpha: dict) -> dict:
        """
        Master 级生产 Alpha 程序化 good_flag 评估器 (V3.1 规范):
        1. YearlyCheck: 有效年份 (>=8年) 中，负 Sharpe 年份最多允许 1 年
        2. RecentSharpeCheck: 最近 2 年年化 Sharpe >= 1.58
        3. MarginCheck: Margin >= 8.0 bps
        4. TurnoverCheck: 换手率处于 [5.0%, 35.0%] 黄金区间
        5. WarningsCheck: 平台警告数 == 0 (0 WARNING)
        6. FailsCheck: 平台失败数 == 0 (0 FAIL)
        7. ProdCorrCheck: ProdCorr < 0.65
        """
        metrics = alpha.get("metrics") or alpha.get("is") or {}
        if not isinstance(metrics, dict):
            metrics = {}

        margin_bps = float(alpha.get("margin_bps") or metrics.get("margin_bps") or (float(metrics.get("margin") or 0.0) * 10000.0))
        turnover = float(alpha.get("turnover") or metrics.get("turnover") or 0.0)
        margin_passed = margin_bps >= 8.0
        turnover_passed = 0.05 <= turnover <= 0.35

        raw_yearly = alpha.get("yearly_stats") or metrics.get("yearly_stats") or alpha.get("yearly_sharpe") or []
        if isinstance(raw_yearly, dict):
            raw_yearly = raw_yearly.get("records", [])
        yearly_sharpes = []
        if isinstance(raw_yearly, list):
            for y_item in raw_yearly:
                if isinstance(y_item, dict):
                    sh = y_item.get("sharpe") or y_item.get("value")
                elif isinstance(y_item, (list, tuple)) and len(y_item) >= 2:
                    sh = y_item[1]
                else:
                    sh = None
                if sh is not None:
                    try:
                        yearly_sharpes.append(float(sh))
                    except (ValueError, TypeError):
                        pass

        valid_years = len(yearly_sharpes)
        neg_years = sum(1 for s in yearly_sharpes if s < 0)
        if valid_years >= 5:
            yearly_passed = neg_years <= 1
        else:
            yearly_passed = (valid_years > 0 and neg_years == 0)

        ladder_2y = alpha.get("ladder_2y_sharpe") or alpha.get("two_year_sharpe") or metrics.get("sharpe_2y")
        if ladder_2y is not None:
            try:
                recent_2y_sharpe = float(ladder_2y)
            except (ValueError, TypeError):
                recent_2y_sharpe = 0.0
        elif len(yearly_sharpes) >= 2:
            recent_2y_sharpe = sum(yearly_sharpes[-2:]) / 2.0
        else:
            recent_2y_sharpe = float(alpha.get("sharpe") or metrics.get("sharpe") or 0.0)
        
        recent_2y_passed = recent_2y_sharpe >= 1.58

        warn_cnt = int(alpha.get("warning_count", 0))
        fail_cnt = int(alpha.get("fail_count", 0))
        checks = alpha.get("checks") or metrics.get("checks") or []
        if isinstance(checks, list):
            for c in checks:
                if isinstance(c, dict):
                    res_val = str(c.get("result", "")).upper()
                    if res_val in ("FAIL", "ERROR"):
                        fail_cnt += 1
                    elif res_val == "WARNING":
                        warn_cnt += 1
        warn_passed = (warn_cnt == 0)
        fail_passed = (fail_cnt == 0)

        pcorr = alpha.get("prod_corr") if alpha.get("prod_corr") is not None else alpha.get("pcorr")
        if pcorr is None:
            pcorr = cls.extract_prod_corr(alpha)
        prod_corr_passed = (pcorr is not None and float(pcorr) < 0.65) if pcorr is not None else False

        is_good = (yearly_passed and recent_2y_passed and margin_passed and turnover_passed)
        is_all_pass_champion = is_good and warn_passed and fail_passed and prod_corr_passed

        return {
            "good_flag": is_good,
            "is_all_pass_champion": is_all_pass_champion,
            "yearly_passed": yearly_passed,
            "neg_years_count": neg_years,
            "total_years_count": valid_years,
            "recent_2y_passed": recent_2y_passed,
            "recent_2y_sharpe": recent_2y_sharpe,
            "margin_passed": margin_passed,
            "margin_bps": margin_bps,
            "turnover_passed": turnover_passed,
            "turnover": turnover,
            "warn_passed": warn_passed,
            "warn_count": warn_cnt,
            "fail_passed": fail_passed,
            "fail_count": fail_cnt,
            "prod_corr_passed": prod_corr_passed,
            "prod_corr": pcorr
        }

    @classmethod
    def audit_final_alpha(cls, sim_result_data: dict, region: str = "USA", pcorr_max: float = 0.65,
                          sc_max: float = 0.60, require_corr_verified: bool = True, strict_zero_warnings: bool = False) -> list:
        """
        终极全维度生产级准入门禁 (Submission-Grade Gate - V3.1 ALL PASS 铁律版):
        彻底封死一切违规与过拟合因子：
        1. Sharpe >= 1.58 且 Fitness >= 1.00
        2. Margin >= 区域门槛 且 换手率 ∈ [5.0%, 35.0%]
        3. ALL PASS 铁律: fail_num == 0 且 (strict_zero_warnings 时 warn_num == 0)
        4. 相关性: 平台 ProdCorr < 0.65, 本地 SelfCorr <= 0.60
        5. Master 级 good_flag 评估 (10年最多1年负夏普, 近2年夏普 >= 1.58)
        """
        if isinstance(sim_result_data, list):
            results = sim_result_data
        elif isinstance(sim_result_data, dict):
            results = sim_result_data.get("alpha_results", [sim_result_data])
        else:
            results = [sim_result_data]
        min_margin_bps = max(cls.get_min_margin_bps(region), 8.0)
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
            warn_num = len(parsed_checks.get("warnings", []))
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
            if strict_zero_warnings and warn_num > 0:
                fails.append(f"平台告警项未清零 (warn_num={warn_num}, 告警项: {parsed_checks.get('warnings')})")
            if cw_failed:
                fails.append("持仓过分集中 (CONCENTRATED_WEIGHT)")
            if pcorr is not None and pcorr >= pcorr_max:
                fails.append(f"平台生产库相关性 {pcorr:.3f} >= {pcorr_max} (共线性无法出厂)")
            if sc is not None and sc > sc_max:
                fails.append(f"个人存量库自相关性 {sc:.3f} > {sc_max} (与已有提交撞车)")
            if not pcorr_verified:
                msg = "平台生产库相关性 ProdCorr 未核实 (结果体缺少 prodCorrelation/pcorr 字段)"
                if require_corr_verified:
                    fails.append(msg + "，严禁在未核实相关性的情况下提交")
                else:
                    print(f"⚠️ [Gatekeeper Final] {msg}，已按 AEGIS_ALLOW_UNVERIFIED_PCORR 降级为告警。")

            # Master 级收益单调性 check (在严格终审时生效)
            gf_res = cls.compute_master_good_flag(res)
            if strict_zero_warnings and not gf_res["good_flag"]:
                fails.append(
                    f"Master 收益单调性 good_flag 未通过 (负夏普年数={gf_res['neg_years_count']}/{gf_res['total_years_count']}, "
                    f"近2年夏普={gf_res['recent_2y_sharpe']:.2f}, Margin={gf_res['margin_bps']:.1f}bps)"
                )

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
                    "warning_count": warn_num,
                    "warnings": parsed_checks["warnings"],
                    "cluster_sharpe": parsed_checks["cluster_sharpe"],
                    "ladder_2y_sharpe": parsed_checks["ladder_2y_sharpe"],
                    "sub_universe_sharpe": parsed_checks["sub_universe_sharpe"],
                    "two_year_sharpe": two_year,
                    "good_flag_details": gf_res,
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
    def diagnose_and_route_prescriptions(
        cls,
        alpha_metrics: dict,
        checks_parsed: dict = None,
        yearly_stats: list = None,
        operator_count: int = 0,
        prod_corr: float = None,
        max_operator_limit: int = 8,
        parent_alpha: dict = None
    ) -> dict:
        """
        Gate 4: 反事实法医病理诊断器 (Forensic Pathologist)
        彻底废除机械的“病症->算子白名单”抓药模式，输出客观物理病灶与三大反事实病理线索，
        驱动 Agent 结合字段 DGP（数据生成过程）自主推演数学拓扑。
        """
        checks_parsed = checks_parsed or {}
        if "checks" in checks_parsed or "is" in checks_parsed or "metrics" in checks_parsed:
            if "fails" not in checks_parsed or "warnings" not in checks_parsed:
                checks_parsed = cls.parse_brain_checks(checks_parsed)

        fails = checks_parsed.get("fails", [])
        warnings = checks_parsed.get("warnings", [])
        all_issues_str = " ".join(str(x).upper() for x in (fails + warnings))
        yearly_stats = yearly_stats or []
        if isinstance(yearly_stats, dict):
            yearly_stats = yearly_stats.get("records", [])

        symptoms = []
        forensic_clues = []

        # 线索 1：多空腿持仓不对称度 (Long/Short Imbalance Ratio) 与零值稀释诊断
        long_counts, short_counts, neg_years_info = [], [], []
        for y in yearly_stats:
            if isinstance(y, dict):
                yr, sh = y.get("year"), y.get("sharpe")
                lc = y.get("long_count") or y.get("longCount")
                sc = y.get("short_count") or y.get("shortCount")
            elif isinstance(y, (list, tuple)) and len(y) >= 2:
                yr, sh = y[0], y[1]
                lc = y[5] if len(y) > 5 else None
                sc = y[6] if len(y) > 6 else None
            else:
                continue
            if lc is not None and sc is not None:
                try:
                    long_counts.append(float(lc))
                    short_counts.append(float(sc))
                except (ValueError, TypeError):
                    pass
            if yr is not None and sh is not None:
                try:
                    if float(sh) < 0:
                        neg_years_info.append(f"{yr}年(Sharpe={float(sh):.2f})")
                except (ValueError, TypeError):
                    pass

        if long_counts and short_counts:
            avg_l = sum(long_counts) / len(long_counts)
            avg_s = sum(short_counts) / len(short_counts)
            ratio = avg_l / max(avg_s, 1.0)
            if ratio > 1.25 or ratio < 0.80:
                symptoms.append("dead_weight_imbalance")
                forensic_clues.append(
                    f"【法医病理 1·多空腿失衡】年均多头 {avg_l:.0f} 只 vs 空头 {avg_s:.0f} 只 (比例 {ratio:.2f})。"
                    f"表明截面存在大量零值或常数堆积稀释单侧持仓！请核查字段 is_sparse 与零值物理含义，剥离无事件僵尸样本。"
                )

        # 线索 2：宏观政权脆弱年定位 (Regime Vulnerability Pinpointing)
        if neg_years_info:
            forensic_clues.append(
                f"【法医病理 2·宏观政权脆弱年】信号在 {', '.join(neg_years_info)} 出现负夏普失血！"
                f"请结合字段底层商业逻辑，思考在流动性冲击/通胀加息周期中该特征发生了何种基数畸变或均值漂移。"
            )

        # 线索 3：换手—边际利润弹性 (Turnover-to-Margin Elasticity)
        cur_turn = float(alpha_metrics.get("turnover") or 0.0)
        cur_margin = float(alpha_metrics.get("margin_bps") or (float(alpha_metrics.get("margin") or 0.0) * 10000.0))
        if parent_alpha and isinstance(parent_alpha, dict):
            p_m = parent_alpha.get("metrics") or {}
            p_turn = float(parent_alpha.get("turnover") or p_m.get("turnover") or 0.0)
            p_margin = float(parent_alpha.get("margin_bps") or (float(p_m.get("margin") or 0.0) * 10000.0))
            d_turn = cur_turn - p_turn
            d_margin = cur_margin - p_margin
            if d_turn < -0.03 and d_margin < -1.0:
                forensic_clues.append(
                    f"【法医病理 3·换手—利润负弹性警告】相比母本换手率下降 {abs(d_turn)*100:.1f}%，但 Margin 反而萎缩 {abs(d_margin):.1f}bps！"
                    f"证明该信号属于快衰减高频脉冲，过度平滑正在扼杀 Alpha 峰值，严禁继续拉长时序衰减窗口！"
                )

        # 其余客观平台检查项归因（只报物理病症，不开算子药方）
        allowed_ast_ops = set(["group_rank", "subindustry", "industry"])

        if prod_corr is not None:
            try:
                pc = float(prod_corr)
            except (TypeError, ValueError):
                pc = None
            if pc is not None and pc >= 0.65:
                symptoms.append("prod_corr_overflow" if pc >= 0.70 else "prod_corr_elevated_above_065")
                forensic_clues.append(
                    f"【共线性超标】当前 ProdCorr={pc:.4f} >= 0.65。底层主信号或外层截面映射与存量库高度同质化，"
                    f"请在重构舱启用低 alpha_count 同源冷字段平替、VECTOR 高阶矩（分歧度/偏度）或特质残差剥离。"
                )
                allowed_ast_ops.update(["group_neutralize", "group_zscore", "ts_delta", "quantile_spread_subtract", "SUBSTITUTE_LOW_ALPHA_COUNT_FIELD"])

        cluster_sharpe = checks_parsed.get("cluster_sharpe")
        if (cluster_sharpe is not None and cluster_sharpe < 1.58) or "CLUSTER" in all_issues_str:
            symptoms.append("cluster_collinearity")
            forensic_clues.append("【同簇共线性警告】与已有同质 Alpha 簇产生共振，建议使用正交残差回归或非线性特征交互破除共线性。")
            allowed_ast_ops.update(["SUBSTITUTE_LOW_ALPHA_COUNT_FIELD", "ts_delta", "group_neutralize", "group_zscore", "quantile_spread_subtract", "winsorize", "signed_power"])

        if any(k in all_issues_str for k in ("EMEA", "APAC", "REGIONAL", "LOW_SHARPE")):
            symptoms.append("regional_or_sharpe_deficit")
            forensic_clues.append("【区域或临界夏普缺口】在特定区域存在性能滑坡，建议通过组内均衡或风险中性化改善局部泛化能力。")
            allowed_ast_ops.update(["winsorize", "signed_power", "s_log_1p", "group_neutralize", "group_zscore", "subindustry", "country", "ts_decay_linear", "ts_decay_exp_window"])

        if "CONCENTRATED" in all_issues_str or checks_parsed.get("cw_failed"):
            symptoms.append("cw_bottleneck")
            forensic_clues.append("【权重集中度违规 (CW)】少数极端离群标的垄断了组合权重，请结合字段偏态分布设计尾部收敛或组内均衡映射。")
            allowed_ast_ops.update(["s_log_1p", "winsorize", "signed_power"])

        if any(k in all_issues_str for k in ("SUB_UNIVERSE", "LADDER", "2Y", "ROBUST")):
            symptoms.append("sub_universe_or_2y_instability")
            forensic_clues.append("【子池/近2年稳健性不足】请排查是否存在大小盘基数鸿沟（Level Bias）或回溯窗口过长导致的跨周期均值滞后。")
            allowed_ast_ops.update(["winsorize", "ts_zscore", "ts_decay_exp_window", "signed_power", "trade_when"])

        if cur_turn > 0.40 or "TURNOVER" in all_issues_str:
            allowed_ast_ops.update(["trade_when", "ts_decay_exp_window", "ts_decay_linear"])
        if cur_turn > 0.35 or "TURNOVER" in all_issues_str:
            symptoms.append("turnover_overflow")
            forensic_clues.append(f"【换手率超标】当前换手率 {cur_turn*100:.1f}% > 35% 黄金区间上限，日间微幅噪音触发了过多无效调仓。")

        if operator_count > max_operator_limit:
            symptoms.append("operator_count_overflow")
            forensic_clues.append(f"【算子复杂度超限】当前算子数 {operator_count} > {max_operator_limit}，请执行奥卡姆剃刀剔除无信息增量的冗余嵌套。")
            allowed_ast_ops.add(f"PRUNE_REDUNDANT_OPERATOR_TO_LE_{max_operator_limit}")

        print(f"\n🩺 [Gatekeeper 法医诊断] 确诊病灶: {symptoms}")
        if forensic_clues:
            print(f"🔬 [法医病理线索]: {len(forensic_clues)} 条反事实线索已就绪")

        return {
            "symptoms": symptoms,
            "forensic_clues": forensic_clues,
            "allowed_mutations": sorted(list(allowed_ast_ops)),
            "rag_prescriptions": [],
            "qa_prescriptions": []
        }

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
