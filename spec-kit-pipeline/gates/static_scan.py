"""
门禁 2：异源静态扫描

防同源的关键门禁之一：扫描工具/规则必须与「开发用的 AI 模型」异源。
骨架内置一套零依赖的"敏感信息泄露"正则扫描（可立即用），
同时支持对接外部工具（SonarQube / Semgrep / CodeQL），在 config 里配置命令即可。

内置规则（仅示例，按需扩充）：
  - 硬编码密钥：AK/SK、api_key=、password=、token=、secret=
  - 凭据写入日志/截图/导出包（提示类）
"""
from __future__ import annotations

import os
import re
import subprocess
from typing import Dict, List

from .base import Gate, GateResult, GateSetupError

# (名称, 正则, 级别: error/warn)
RULES = [
    ("硬编码 AccessKey", r"(\bAK|access[_-]?key)[\"']?\s*[:=]\s*[\"'][A-Za-z0-9+/]{16,}", "error"),
    ("硬编码 SecretKey", r"(secret[_-]?key|secret|sk-)[\"']?\s*[:=]\s*[\"'][A-Za-z0-9+/]{16,}", "error"),
    ("硬编码 API Key", r"(api[_-]?key|apikey)[\"']?\s*[:=]\s*[\"'][A-Za-z0-9\-_]{12,}", "error"),
    ("硬编码 Token", r"(token|bearer)[\"']?\s*[:=]\s*[\"'][A-Za-z0-9\-_.]{16,}", "error"),
    # 密码类降为 warn：测试用例/本地开发中的测试密码属预期数据，由人工确认而非自动阻断
    ("疑似硬编码密码", r"(password|passwd|pwd)[\"']?\s*[:=]\s*[\"'][^\"']{6,}", "warn"),
    ("凭据疑似写入日志", r"(print|console\.log|logger\.(info|debug))\(.*(password|token|secret|key)", "warn"),
]

DEFAULT_SKIP_DIRS = {"node_modules", ".git", ".tools", "reports", "test-results", "report", "venv", "__pycache__"}


class StaticScanGate(Gate):
    name = "static_scan"

    def init(self) -> None:
        cfg = self.gate_cfg
        project_root = self.config.get("project_root", ".")
        self.scan_dirs = [
            p if os.path.isabs(p) else os.path.realpath(os.path.join(project_root, p))
            for p in (cfg.get("dirs") or [project_root])
        ]
        stage = self.config.get("stage", "default")
        self.external_cmds = (cfg.get("external_cmds_by_stage") or {}).get(stage)
        if self.external_cmds is None:
            legacy = cfg.get("external_cmd")
            self.external_cmds = [legacy] if legacy else []
        self.external_cwd = self.config.get("autotest_dir", project_root)
        self.skip_dirs = set(cfg.get("skip_dirs", [])) | DEFAULT_SKIP_DIRS

    def _iter_files(self, root: str):
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in self.skip_dirs]
            for fn in filenames:
                if fn in {"package-lock.json", "semgrep.yml"}:
                    continue
                if fn.endswith((".js", ".ts", ".py", ".java", ".go", ".json", ".env", ".yaml", ".yml", ".sh")):
                    yield os.path.join(dirpath, fn)

    def _scan_builtin(self) -> List[str]:
        findings: List[str] = []
        for root in self.scan_dirs:
            if not os.path.isdir(root):
                continue
            for fp in self._iter_files(root):
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except OSError:
                    continue
                rel = os.path.relpath(fp, root)
                for name, pattern, level in RULES:
                    for m in re.finditer(pattern, content, re.IGNORECASE):
                        # 排除示例/占位（如 README 里的示例 key）
                        if "example" in rel.lower() or ".env.example" in rel:
                            continue
                        line = content.count("\n", 0, m.start()) + 1
                        findings.append(f"[{level}] {rel}:{line} {name}（匹配内容已脱敏）")
        return findings

    def _run_external(self) -> List[str]:
        if not self.external_cmds:
            return []
        findings = []
        for command in self.external_cmds:
            try:
                proc = subprocess.run(command, cwd=self.external_cwd, capture_output=True, text=True, timeout=600)
                out = (proc.stdout or "") + (proc.stderr or "")
                lines = [ln for ln in out.splitlines() if ln.strip()][:50]
                if proc.returncode != 0:
                    lines.insert(0, f"[error] 外部扫描退出码 {proc.returncode}: {' '.join(command)}")
                findings.extend(lines)
            except Exception as e:
                raise GateSetupError(f"外部扫描工具执行失败 ({' '.join(command)}): {e}")
        return findings

    def run(self) -> GateResult:
        findings = self._scan_builtin()
        if self.external_cmds:
            findings += self._run_external()

        errors = [f for f in findings if f.startswith("[error]")]
        warnings = [f for f in findings if f.startswith("[warn]")]

        return GateResult(
            name=self.name,
            passed=len(errors) == 0,
            blocking=self.blocking,
            detail=f"扫描完成：error {len(errors)} / warn {len(warnings)}" + ("（含外部工具）" if self.external_cmds else "（内置规则）"),
            issues=findings,
            metrics={"errors": len(errors), "warnings": len(warnings), "rules": len(RULES)},
        )
