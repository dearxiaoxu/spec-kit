"""
Gate 基类与结果模型 —— Spec-Kit 流水线门禁的统一契约。

每个门禁（Gate）实现 run(ctx) -> GateResult：
  - name       门禁标识（如 contract_diff）
  - passed     是否通过
  - blocking   是否阻断性门禁（失败即中断流水线，模拟 CONTRACT_MISMATCH）
  - detail     人可读的失败/告警说明（门禁自动但不静默）
  - skipped    是否跳过（未配置/环境缺失时跳过并提示，不假装通过）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Dict, List, Optional


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    SKIP = "SKIP"
    FLAKY = "FLAKY"
    ENV_ERROR = "ENV_ERROR"
    CONFIG_ERROR = "CONFIG_ERROR"


def redact_sensitive(value: str) -> str:
    """对报告中的常见凭据字段做兜底脱敏。"""
    text = str(value)
    patterns = [
        r"(?i)(password|passwd|pwd|token|authorization|secret|api[_-]?key)(\s*[:=]\s*)([^\s,}\]]+)",
        r"(?i)(bearer\s+)[A-Za-z0-9._-]+",
    ]
    for pattern in patterns:
        text = re.sub(pattern, lambda m: f"{m.group(1)}{m.group(2) if m.lastindex and m.lastindex >= 2 else ''}[REDACTED]", text)
    return text


@dataclass
class GateResult:
    name: str
    passed: bool = True
    blocking: bool = False
    skipped: bool = False
    detail: str = ""
    issues: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    status: Optional[GateStatus] = None

    def __post_init__(self) -> None:
        if self.status is None:
            if self.skipped:
                self.status = GateStatus.SKIP
            elif not self.passed and self.blocking:
                self.status = GateStatus.BLOCKED
            else:
                self.status = GateStatus.PASS if self.passed else GateStatus.FAIL
        elif not isinstance(self.status, GateStatus):
            self.status = GateStatus(self.status)
        self.skipped = self.status == GateStatus.SKIP
        self.blocking = self.blocking or self.status == GateStatus.BLOCKED
        self.passed = self.status in (GateStatus.PASS, GateStatus.SKIP)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "blocking": self.blocking,
            "skipped": self.skipped,
            "detail": redact_sensitive(self.detail),
            "issues": [redact_sensitive(issue) for issue in self.issues[:20]],
            "metrics": self.metrics,
            "status": self.status.value,
        }


class Gate:
    """所有门禁的基类。子类实现 run()，可选实现 init() 做启动校验。"""

    name: str = "base"
    blocking: bool = False
    # 触发条件表达式（如 "stage == 'code' and gates.contract_diff.enabled"）
    # 留空表示总是启用，是否启用由 config.gates.<name>.enabled 控制
    when: Optional[str] = None

    def __init__(self, config: Dict[str, Any], ctx: Dict[str, Any]):
        self.config = config
        self.ctx = ctx

    def init(self) -> None:
        """启动校验：配置缺失/依赖缺失时 raise GateSetupError 以跳过该门禁。"""
        pass

    def run(self) -> GateResult:
        raise NotImplementedError

    # ---- 子类工具方法 ----
    @property
    def gate_cfg(self) -> Dict[str, Any]:
        return (self.config.get("gates") or {}).get(self.name, {}) or {}

    def enabled(self) -> bool:
        cfg = self.gate_cfg
        # 显式 enabled: false 才关闭；缺省视为开启（骨架阶段尽量宽松）
        return cfg.get("enabled", True)


class GateSetupError(Exception):
    """门禁因环境/配置缺失无法执行时抛出，流水线将其转为 skipped 而非失败。"""
    pass


class GateEnvironmentError(Exception):
    """门禁无法可靠执行：目标环境不可达、持续 5xx 或响应格式异常。"""
    pass
