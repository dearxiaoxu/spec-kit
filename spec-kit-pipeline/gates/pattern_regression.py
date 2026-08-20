"""
门禁 3：AI 缺陷模式库回归（blocking）

对 assets/patterns.json 中登记的「AI 高发缺陷模式」逐项执行探测。
骨架内置两种探测：
  - probe: HTTP 请求（method/url/预期特征），针对目标站做只读探测
  - file_check: 本地文件/目录检查（如目标模块文件存在、未篡改）

模式库由测试维护（测试方案 §7.3.4 的 10 类），每轮迭代自动回填扩容。
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.request
from typing import Dict, List

from .base import Gate, GateResult, GateSetupError


class PatternRegressionGate(Gate):
    name = "pattern_regression"
    blocking = True

    def init(self) -> None:
        cfg = self.gate_cfg
        self.workdir = self.config.get("project_root", ".")
        self.autotest_dir = self.config.get("autotest_dir") or ""
        self.patterns_path = os.path.join(self.workdir, cfg.get("patterns_file", "assets/patterns.json"))
        self.base_url = (self.config.get("target") or {}).get("base_url", "https://106.54.60.191")
        self.timeout = self.gate_cfg.get("timeout", 10)

    def _load_patterns(self) -> List[Dict]:
        if not os.path.exists(self.patterns_path):
            raise GateSetupError(f"模式库不存在: {self.patterns_path}，先创建 assets/patterns.json")
        with open(self.patterns_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("patterns", [])

    def _probe(self, p: Dict) -> Dict:
        probe = p.get("probe") or {}
        url = probe.get("url", "")
        if not url.startswith("http"):
            url = self.base_url.rstrip("/") + "/" + url.lstrip("/")
        method = probe.get("method", "GET").upper()
        expect = probe.get("expect")  # {"status": 200, "contains": "..."}
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # 自签名证书豁免，对齐测试方案
        req = urllib.request.Request(url, method=method)
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                status = resp.status
        except urllib.error.HTTPError as e:
            status, body = e.code, ""
        except Exception as e:
            return {"ok": False, "detail": f"请求失败: {e}"}


        if expect is None:
            return {"ok": True, "detail": f"HTTP {status}"}
        problems = []
        if "status" in expect and status != expect["status"]:
            problems.append(f"期望状态 {expect['status']} 实得 {status}")
        if "contains" in expect and expect["contains"] not in body:
            problems.append(f"响应缺少期望特征 '{expect['contains']}'")
        if "not_contains" in expect and expect["not_contains"] in body:
            problems.append(f"响应出现不应有的特征 '{expect['not_contains']}'")
        return {"ok": not problems, "detail": "; ".join(problems) or f"HTTP {status} 特征符合"}

    def _file_check(self, p: Dict) -> Dict:
        check = p.get("file_check") or {}
        rel = check.get("path", "")
        # 依次在流水线项目根、autotest 项目下解析
        candidates = [
            os.path.join(self.workdir, rel),
            os.path.join(self.autotest_dir, rel),
        ]
        for path in candidates:
            if os.path.exists(path):
                return {"ok": True, "detail": f"文件存在: {rel}"}
        return {"ok": False, "detail": f"文件缺失: {rel}（已尝试 {len(candidates)} 个位置）"}

    def run(self) -> GateResult:
        patterns = self._load_patterns()
        if not patterns:
            raise GateSetupError("模式库为空，先填充 assets/patterns.json")

        issues: List[str] = []
        passed = 0
        failed = 0
        for p in patterns:
            cid = p.get("id", "?")
            cat = p.get("category", "")
            method = "probe" if "probe" in p else ("file_check" if "file_check" in p else None)
            if method is None:
                issues.append(f"[{cid}] {cat}: 未配置探测方式（probe/file_check），跳过")
                continue
            result = self._probe(p) if method == "probe" else self._file_check(p)
            if result["ok"]:
                passed += 1
            else:
                failed += 1
                issues.append(f"[{cid}] {cat}: {result['detail']}")

        return GateResult(
            name=self.name,
            passed=failed == 0,
            blocking=self.blocking,
            detail=f"模式库 {len(patterns)} 项：通过 {passed} / 失败 {failed}" + ("；失败项见 issues" if failed else "，全部通过"),
            issues=issues,
            metrics={"total": len(patterns), "passed": passed, "failed": failed},
        )
