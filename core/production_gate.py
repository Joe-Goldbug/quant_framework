"""
core/production_gate.py
生产资格唯一发证门禁 (Production Gate V2)

设计目标:
1. 终结“严格终审 + 宽松收割”的双轨制: 生产冠军只能由本模块发证;
2. Fail-Closed: checks 缺失、ProdCorr/SelfCorr 未核实、Horizon 证据缺失时一律不得发放生产证书;
3. 证书包含表达式、设置、指标与证据哈希，可用于审计与防篡改核对。
"""

import hashlib
import json
from typing import Dict, List, Optional, Union

try:
    from quant_framework.core.gatekeeper import Gatekeeper
    from quant_framework.core.fastexpr_ast import parse_fastexpr
except ModuleNotFoundError:
    from core.gatekeeper import Gatekeeper
    from core.fastexpr_ast import parse_fastexpr


class ProductionGate:
    """统一生产资格门禁。所有进入 production_certificates 的 Alpha 必须通过本门禁。"""

    PRODUCTION_STATUS = "PRODUCTION_ALL_PASS"
    NEAR_STATUS = "NEAR_CHAMPION"
    RESEARCH_STATUS = "RESEARCH_CANDIDATE"

    ACCEPTED_HORIZON_VERDICTS = {
        "PLATEAU",
        "EXPECTED_PLATEAU",
        "EXPECTED_DECAY",
        "EXPECTED_REVERSAL",
        "REGIME_REVERSAL_CONFIRMED",
        "STATIC_CROSS_SECTION",
    }
    REJECTED_HORIZON_VERDICTS = {
        "SPIKE",
        "UNEXPECTED_SPIKE",
        "UNEXPECTED_SIGN_FLIP",
    }

    @classmethod
    def compute_dynamic_sharpe_threshold(cls, trial_count: int = 20, base_threshold: float = 1.58) -> float:
        """
        Bailey & López de Prado Deflated Sharpe Ratio (DSR) 启发式多重检验惩罚:
        Delta_S = 0.03 * ln(1 + max(0, trial_count - 20) / 20)
        返回 min(1.75, round(base_threshold + Delta_S, 3))
        """
        import math
        trial_eff = max(0, int(trial_count) - 20)
        delta_s = 0.03 * math.log(1.0 + trial_eff / 20.0)
        return min(1.75, round(base_threshold + delta_s, 3))

    @classmethod
    def _first_present(cls, *values):
        for value in values:
            if value is not None:
                return value
        return None

    @classmethod
    def _raw_checks(cls, alpha: dict):
        if not isinstance(alpha, dict):
            return None
        containers = [alpha.get("is"), alpha.get("metrics"), alpha]
        for container in containers:
            if isinstance(container, dict) and container.get("checks") is not None:
                return container.get("checks")
        return None

    @classmethod
    def _checks_verified(cls, raw_checks) -> bool:
        if raw_checks is None:
            return False
        if isinstance(raw_checks, list):
            return len(raw_checks) > 0
        if isinstance(raw_checks, dict):
            return any(
                key in raw_checks
                for key in ("fail", "fails", "warning", "warnings", "result", "results")
            )
        return False

    @classmethod
    def _operator_count(cls, expression: str) -> int:
        if not expression:
            return 0
        parsed = parse_fastexpr(expression)
        if parsed.is_valid:
            return parsed.operator_count
        return expression.count("(")

    @classmethod
    def _settings_digest(cls, alpha: dict) -> str:
        settings = alpha.get("settings") or {}
        if not isinstance(settings, dict):
            settings = {}
        payload = {
            "region": alpha.get("region"),
            "universe": alpha.get("universe"),
            "delay": alpha.get("delay"),
            "neutralization": alpha.get("neutralization") or settings.get("neutralization"),
            "decay": alpha.get("decay", settings.get("decay")),
            "truncation": alpha.get("truncation", settings.get("truncation")),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]

    @classmethod
    def _certificate_id(cls, alpha: dict, evidence: dict) -> str:
        payload = {
            "alpha_id": alpha.get("alpha_id") or alpha.get("id"),
            "expression": alpha.get("expression") or alpha.get("code"),
            "settings_digest": evidence.get("settings_digest"),
            "sharpe": evidence.get("sharpe"),
            "fitness": evidence.get("fitness"),
            "margin_bps": evidence.get("margin_bps"),
            "prod_corr": evidence.get("prod_corr"),
            "self_corr": evidence.get("self_corr"),
            "checks_digest": evidence.get("checks_digest"),
            "horizon_verdict": evidence.get("horizon_verdict"),
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return "PC_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20].upper()

    @classmethod
    def evaluate(
        cls,
        alpha: dict,
        region: str = "USA",
        margin_threshold_bps: Optional[float] = None,
        operator_limit: int = 6,
        pcorr_max: float = 0.65,
        self_corr_max: float = 0.60,
        trial_count: int = 20,
    ) -> dict:
        """
        评估单个 Alpha 的生产资格。

        返回:
        {
            "eligible": bool,
            "status": PRODUCTION_ALL_PASS / NEAR_CHAMPION / RESEARCH_CANDIDATE,
            "certificate": dict | None,
            "reasons": [str],
            "evidence": dict
        }
        """
        if not isinstance(alpha, dict):
            return {
                "eligible": False,
                "status": cls.RESEARCH_STATUS,
                "certificate": None,
                "reasons": ["候选对象不是 dict"],
                "evidence": {},
            }

        reasons: List[str] = []
        metrics = alpha.get("is") or alpha.get("metrics") or {}
        if not isinstance(metrics, dict):
            metrics = {}

        expression = cls._first_present(alpha.get("expression"), alpha.get("code"), "")
        raw_checks = cls._raw_checks(alpha)
        checks_verified = cls._checks_verified(raw_checks)
        parsed_checks = Gatekeeper.parse_brain_checks(alpha)
        fail_count = int(parsed_checks.get("fail_count", 0) or 0)
        warning_count = len(parsed_checks.get("warnings", []) or [])

        sharpe = cls._first_present(alpha.get("sharpe"), metrics.get("sharpe"))
        fitness = cls._first_present(alpha.get("fitness"), metrics.get("fitness"))
        turnover = cls._first_present(alpha.get("turnover"), metrics.get("turnover"))
        margin_bps = cls._first_present(alpha.get("margin_bps"))
        if margin_bps is None:
            raw_margin = cls._first_present(metrics.get("margin_bps"), metrics.get("margin"))
            if raw_margin is not None:
                try:
                    margin_bps = float(raw_margin)
                    if margin_bps <= 1.0:
                        margin_bps *= 10000.0
                except (TypeError, ValueError):
                    margin_bps = None

        prod_corr = Gatekeeper.extract_prod_corr(alpha)
        self_corr = Gatekeeper.extract_self_corr(alpha)
        horizon_verdict = alpha.get("horizon_verdict")
        horizon_robust = bool(alpha.get("horizon_robust") or alpha.get("plateau_pass"))
        operator_count = cls._operator_count(str(expression or ""))
        settings_digest = cls._settings_digest(alpha)
        checks_digest = hashlib.sha256(
            json.dumps(raw_checks if raw_checks is not None else {}, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        ).hexdigest()[:16]

        if margin_threshold_bps is None:
            margin_threshold_bps = float(Gatekeeper.get_min_margin_bps(region))

        try:
            sharpe_val = float(sharpe) if sharpe is not None else None
        except (TypeError, ValueError):
            sharpe_val = None
        try:
            fitness_val = float(fitness) if fitness is not None else None
        except (TypeError, ValueError):
            fitness_val = None
        try:
            turnover_val = float(turnover) if turnover is not None else None
        except (TypeError, ValueError):
            turnover_val = None
        try:
            margin_val = float(margin_bps) if margin_bps is not None else None
        except (TypeError, ValueError):
            margin_val = None

        if not checks_verified:
            reasons.append("平台 checks 缺失或为空，无法证明 0 FAIL / 0 WARNING")
        if fail_count > 0:
            reasons.append(f"平台检查存在 FAIL: {parsed_checks.get('fails', [])}")
        if warning_count > 0:
            reasons.append(f"平台检查存在 WARNING: {parsed_checks.get('warnings', [])}")

        # Bailey & López de Prado Deflated Sharpe Ratio (DSR) 启发式多重检验惩罚
        effective_sharpe_threshold = cls.compute_dynamic_sharpe_threshold(trial_count)
        delta_s = round(effective_sharpe_threshold - 1.58, 3)

        if sharpe_val is None:
            reasons.append("Sharpe 未核实")
        elif sharpe_val < effective_sharpe_threshold:
            reasons.append(f"Sharpe {sharpe_val:.3f} < 生产动态门槛 {effective_sharpe_threshold:.3f} (trial_count={trial_count}, 动态惩罚 +{delta_s:.3f})")

        if fitness_val is None:
            reasons.append("Fitness 未核实")
        elif fitness_val < 1.0:
            reasons.append(f"Fitness {fitness_val:.3f} < 1.00")

        if margin_val is None:
            reasons.append("Margin 未核实")
        elif margin_val < float(margin_threshold_bps):
            reasons.append(f"Margin {margin_val:.2f} bps < 生产阈值 {float(margin_threshold_bps):.2f} bps")

        if turnover_val is None:
            reasons.append("Turnover 未核实")
        elif not (0.05 <= turnover_val <= 0.50):
            reasons.append(f"Turnover {turnover_val:.3f} 不在 [0.05, 0.50]")

        if prod_corr is None:
            reasons.append("ProdCorr 未核实，禁止未核实相关性晋级")
        elif prod_corr >= pcorr_max:
            reasons.append(f"ProdCorr {prod_corr:.4f} >= {pcorr_max:.2f}")

        if self_corr is None:
            reasons.append("SelfCorr 未核实，禁止未核实自相关晋级")
        elif self_corr > self_corr_max:
            reasons.append(f"SelfCorr {self_corr:.4f} > {self_corr_max:.2f}")

        if horizon_verdict in cls.REJECTED_HORIZON_VERDICTS:
            reasons.append(f"Horizon 判定为 {horizon_verdict}，存在窗口尖峰或非预期反号风险")
        elif horizon_verdict not in cls.ACCEPTED_HORIZON_VERDICTS and not horizon_robust:
            reasons.append("Horizon 稳健性证据缺失或不足")

        if operator_count > int(operator_limit):
            reasons.append(f"算子数 {operator_count} > {int(operator_limit)}")

        try:
            good_flag_result = Gatekeeper.compute_master_good_flag(alpha)
            good_flag = bool(good_flag_result.get("good_flag", False))
        except Exception:
            good_flag_result = {"good_flag": False, "error": "compute_master_good_flag_failed"}
            good_flag = False
        if not good_flag:
            reasons.append("Master good_flag 未通过或证据不足")

        evidence = {
            "trial_count": int(trial_count),
            "effective_sharpe_threshold": effective_sharpe_threshold,
            "delta_s": delta_s,
            "alpha_id": alpha.get("alpha_id") or alpha.get("id"),
            "expression": expression,
            "settings_digest": settings_digest,
            "checks_verified": checks_verified,
            "checks_digest": checks_digest,
            "fail_count": fail_count,
            "warning_count": warning_count,
            "sharpe": sharpe_val,
            "fitness": fitness_val,
            "margin_bps": margin_val,
            "turnover": turnover_val,
            "prod_corr": prod_corr,
            "prod_corr_verified": prod_corr is not None,
            "self_corr": self_corr,
            "self_corr_verified": self_corr is not None,
            "horizon_verdict": horizon_verdict,
            "horizon_robust": horizon_robust,
            "operator_count": operator_count,
            "good_flag": good_flag,
            "good_flag_details": good_flag_result,
        }

        eligible = not reasons
        if eligible:
            status = cls.PRODUCTION_STATUS
        else:
            try:
                near_miss = bool(Gatekeeper.is_near_miss_champion(alpha, region=region, allow_pending_prod_corr=True))
            except Exception:
                near_miss = False
            status = cls.NEAR_STATUS if near_miss else cls.RESEARCH_STATUS

        certificate = None
        if eligible:
            certificate = {
                "certificate_id": cls._certificate_id(alpha, evidence),
                "status": cls.PRODUCTION_STATUS,
                "region": region,
                "gate_version": "production_gate_v2",
                "evidence": evidence,
                "reasons": [],
            }

        return {
            "eligible": eligible,
            "status": status,
            "certificate": certificate,
            "reasons": reasons,
            "evidence": evidence,
        }

    @classmethod
    def evaluate_batch(
        cls,
        alphas: List[dict],
        region: str = "USA",
        margin_threshold_bps: Optional[float] = None,
        operator_limit: int = 6,
        pcorr_max: float = 0.65,
        self_corr_max: float = 0.60,
        trial_count: int = 20,
    ) -> Dict[str, List[dict]]:
        """
        批量评估，返回三池:
        production / near_miss / research，每项保存 evaluate() 的完整结果。
        """
        production: List[dict] = []
        near_miss: List[dict] = []
        research: List[dict] = []

        for alpha in alphas or []:
            a_trial = alpha.get("trial_count") if (isinstance(alpha, dict) and alpha.get("trial_count") is not None) else trial_count
            result = cls.evaluate(
                alpha,
                region=region,
                margin_threshold_bps=margin_threshold_bps,
                operator_limit=operator_limit,
                pcorr_max=pcorr_max,
                self_corr_max=self_corr_max,
                trial_count=a_trial,
            )
            if result["eligible"]:
                production.append(result)
            elif result["status"] == cls.NEAR_STATUS:
                near_miss.append(result)
            else:
                research.append(result)

        return {
            "production": production,
            "near_miss": near_miss,
            "research": research,
        }
