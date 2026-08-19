"""
门禁 5：变异测试（断言有效性验证）—— 骨架占位

目的：验证"测试断言真的能抓到缺陷"，专治 AI 同源假绿。
若变异体（注入缺陷的代码）没被现有断言抓住 → 断言可能与代码同源，需人工补独立断言。

骨架阶段：
  - 默认 PASS + WARN 提示接入（不阻断），避免误伤主流程
  - 提供 contract：配置 mutation_cmd（如 Stryker 命令）后转为真实门禁
"""
from __future__ import annotations

import os
import subprocess

from .base import Gate, GateResult, GateSetupError


class MutationCheckGate(Gate):
    name = "mutation_check"

    def init(self) -> None:
        cfg = self.gate_cfg
        self.mutation_cmd = cfg.get("mutation_cmd")
        self.min_kill_rate = float(cfg.get("min_kill_rate", 0.7))

    def run(self) -> GateResult:
        if not self.mutation_cmd:
            # 骨架模式：跳过并提示，不给流水线挂红
            return GateResult(
                name=self.name,
                passed=True,
                skipped=True,
                blocking=self.blocking,
                detail="变异测试未配置（config.gates.mutation_check.mutation_cmd 为空），骨架阶段跳过。接入后按 kill rate 判定断言有效性。",
                metrics={"min_kill_rate": self.min_kill_rate},
            )

        try:
            proc = subprocess.run(self.mutation_cmd, capture_output=True, text=True, timeout=3600)
        except Exception as e:
            raise GateSetupError(f"变异测试执行失败: {e}")

        out = (proc.stdout or "") + (proc.stderr or "")
        # 尝试从输出提取 kill rate（Stryker 格式 "xx.xx% killed"）
        import re
        m = re.search(r"([\d.]+)\s*%\s*(?:killed|mutation score|覆盖)", out, re.IGNORECASE)
        rate = float(m.group(1)) / 100.0 if m else None
        passed = (rate is None and proc.returncode == 0) or (rate is not None and rate >= self.min_kill_rate)

        return GateResult(
            name=self.name,
            passed=passed,
            blocking=self.blocking,
            detail=f"变异测试 kill rate {rate:.1%}" if rate else f"变异测试退出码 {proc.returncode}（未解析 kill rate）",
            issues=[] if passed else [out[-1500:]],
            metrics={"kill_rate": rate, "min_kill_rate": self.min_kill_rate},
        )
