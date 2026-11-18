"""
quant_framework core package
"""

try:
    from quant_framework.core.agy_client import GeminiClient, VirtualSession, PortLockManager
    from quant_framework.core.func_call_corrector import ASTSandboxCorrector
    from quant_framework.core.dimension_rules import DimensionAuditor
    from quant_framework.core.dgp_schema import HypothesisSpec
    from quant_framework.core.gatekeeper import Gatekeeper
    from quant_framework.core.production_gate import ProductionGate
    from quant_framework.core.rag_memory import RAGMemoryEngine
    from quant_framework.core.sim_runner import SimBatchRunner
    from quant_framework.core.field_resolver import DatasetFieldResolver
    from quant_framework.core.operator_registry import OperatorRegistry
except ModuleNotFoundError:
    from core.agy_client import GeminiClient, VirtualSession, PortLockManager
    from core.func_call_corrector import ASTSandboxCorrector
    from core.dimension_rules import DimensionAuditor
    from core.dgp_schema import HypothesisSpec
    from core.gatekeeper import Gatekeeper
    from core.production_gate import ProductionGate
    from core.rag_memory import RAGMemoryEngine
    from core.sim_runner import SimBatchRunner
    from core.field_resolver import DatasetFieldResolver
    from core.operator_registry import OperatorRegistry

__all__ = [
    "GeminiClient",
    "VirtualSession",
    "PortLockManager",
    "ASTSandboxCorrector",
    "DimensionAuditor",
    "HypothesisSpec",
    "Gatekeeper",
    "ProductionGate",
    "RAGMemoryEngine",
    "SimBatchRunner",
    "DatasetFieldResolver",
    "OperatorRegistry",
]
