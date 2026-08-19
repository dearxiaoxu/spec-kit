"""
门禁 4：E2E / 接口回归（对接现有 Playwright 项目）

调用 spec-kit-autotest 的 npm scripts（test:api / test:ui / test:smoke），
解析 reports/test-results.json 判定通过率。

防假绿要点：这里的"通过"仅代表自动化回归通过，
关键断言的人工审查由 human_review 记录约束（见 README 铁律），不在此门禁内自动豁免。
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import List

from .base import Gate, GateResult, GateSetupError


class E2ERegressionGate(Gate):
    name = "e2e_regression"

    def init(self) -> None:
        cfg = self.gate_cfg
        self.autotest_dir = cfg.get("autotest_dir") or (self.config.get("autotest_dir") or "")
        if not self.autotest_dir or not os.path.isdir(self.autotest_dir):
            raise GateSetupError("未配置 Playwright 项目目录（config.autotest_dir 或 gates.e2e_regression.autotest_dir）")
        self.npm_script = cfg.get("script", "test:api")
        self.report_file = cfg.get("report_file", "reports/test-results.json")
        self.min_pass_rate = float(cfg.get("min_pass_rate", 0.95))
        self.timeout = int(cfg.get("timeout", 1800))

    def _run(self) -> subprocess.CompletedProcess:
        # 不覆盖 reporter：config 已配置 json reporter 输出到 reports/test-results.json
        cmd = ["npm", "run", self.npm_script]
        return subprocess.run(cmd, cwd=self.autotest_dir, capture_output=True, text=True, timeout=self.timeout)

    def _parse_report(self) -> dict:
        path = os.path.join(self.autotest_dir, self.report_file)
        if not os.path.exists(path):
            # playwright 的 json reporter 输出在 stdout 中，尝试解析
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _count(self, data: dict) -> tuple:
        # 优先用 playwright json 报告的顶层 stats（最稳）
        stats = data.get("stats") if isinstance(data, dict) else {}
        if stats:
            total = int(stats.get("expected", 0)) + int(stats.get("unexpected", 0)) + int(stats.get("flaky", 0))
            passed = int(stats.get("expected", 0)) + int(stats.get("flaky", 0))
            failed = int(stats.get("unexpected", 0))
            return total, passed, failed
        # 兜底：遍历 suites -> specs -> tests（status: expected=通过）
        suites = data.get("suites", []) if isinstance(data, dict) else []
        total = passed = failed = 0

        def walk(items):
            nonlocal total, passed, failed
            for s in items or []:
                for spec in s.get("specs", []) or []:
                    for t in spec.get("tests", []) or []:
                        total += 1
                        if t.get("status") == "expected":
                            passed += 1
                        else:
                            failed += 1
                walk(s.get("suites"))

        walk(suites)
        return total, passed, failed

    def run(self) -> GateResult:
        proc = self._run()
        report = self._parse_report()
        total, passed, failed = self._count(report)
        if total == 0:
            # 无 JSON 结构时退化为进程退出码判断
            ok = proc.returncode == 0
            return GateResult(
                name=self.name,
                passed=ok,
                blocking=self.blocking,
                detail=f"npm run {self.npm_script} 退出码 {proc.returncode}（未解析到 JSON 用例统计）",
                issues=[] if ok else [proc.stdout[-1500:] or proc.stderr[-1500:]],
                metrics={"exit_code": proc.returncode},
            )
        rate = passed / total
        issues: List[str] = []
        if failed:
            issues.append(f"{failed} 条用例失败")
        if proc.returncode != 0 and rate >= self.min_pass_rate:
            issues.append("进程退出码非 0 但用例通过率达标，请人工确认是否有未统计的崩溃")

        return GateResult(
            name=self.name,
            passed=rate >= self.min_pass_rate and proc.returncode == 0,
            blocking=self.blocking,
            detail=f"{self.npm_script}: 通过率 {rate:.1%}（{passed}/{total}）",
            issues=issues,
            metrics={"total": total, "passed": passed, "failed": failed, "pass_rate": round(rate, 4)},
        )
