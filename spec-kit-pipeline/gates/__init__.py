"""门禁模块包：pipeline.py 通过此文件自动发现并注册所有 Gate。"""
from .base import Gate, GateResult, GateSetupError
from .contract_diff import ContractDiffGate
from .static_scan import StaticScanGate
from .pattern_regression import PatternRegressionGate
from .e2e_regression import E2ERegressionGate
from .mutation_check import MutationCheckGate

ALL_GATES = [
    ContractDiffGate,
    StaticScanGate,
    PatternRegressionGate,
    E2ERegressionGate,
    MutationCheckGate,
]
