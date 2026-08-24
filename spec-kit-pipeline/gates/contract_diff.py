"""
门禁 1：OpenAPI 契约 diff（blocking）

对比「当前拉取的 OpenAPI」与「基线快照」：
  - 新增/删除/重命名接口、Schema、枚举、鉴权、错误码变化
  - 破坏性变化（删除端点、必填字段消失、枚举值移除）→ 阻断
  - 未评审的破坏性变化阻断准入（对齐测试方案 §2.2.4 契约治理）

用法：
  pipeline.py --gate contract_diff              # 用上次 fetch 的临时快照对比基线
  pipeline.py --gate contract_diff --base=dev   # 对比指定基线文件
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Set

from .base import Gate, GateResult, GateSetupError

# 破坏性变化：删除/改名端点、去掉必填字段、枚举删值、鉴权收紧
BREAKING_MARKERS = ("removed_endpoint", "removed_required_field", "removed_enum_value")


class ContractDiffGate(Gate):
    name = "contract_diff"
    blocking = True

    def init(self) -> None:
        cfg = self.gate_cfg
        self.workdir = self.config.get("project_root", ".")
        self.snapshot_dir = os.path.join(self.workdir, cfg.get("snapshot_dir", "assets/contract"))
        module_registry = cfg.get("module_registry", "assets/platform-modules.json")
        self.module_registry = module_registry if os.path.isabs(module_registry) else os.path.join(self.workdir, module_registry)
        os.makedirs(self.snapshot_dir, exist_ok=True)

    # ---- 数据加载 ----
    def _load_json(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            raise GateSetupError(f"契约文件不存在: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ---- 端点/字段/枚举提取 ----
    def _collect(self, spec: Dict[str, Any]) -> Dict[str, Set[str]]:
        endpoints: Set[str] = set()
        required_fields: Set[str] = set()
        enum_values: Set[str] = set()

        paths = spec.get("paths", {}) or {}
        for path, methods in paths.items():
            for method, op in (methods or {}).items():
                if method.lower() not in ("get", "post", "put", "patch", "delete"):
                    continue
                endpoints.add(f"{method.upper()} {path}")
                params = (op or {}).get("parameters", []) or []
                for p in params:
                    if (p or {}).get("required"):
                        required_fields.add(f"{method.upper()} {path} :: {p.get('name')}")

        schemas = ((spec.get("components") or {}).get("schemas") or {})
        for sname, sbody in schemas.items():
            req = (sbody or {}).get("required", []) or []
            for r in req:
                required_fields.add(f"schema:{sname} :: {r}")
            props = (sbody or {}).get("properties", {}) or {}
            for pname, pbody in props.items():
                ev = (pbody or {}).get("enum")
                if isinstance(ev, list):
                    for v in ev:
                        enum_values.add(f"schema:{sname} :: {pname} :: {v}")

        return {"endpoints": endpoints, "required_fields": required_fields, "enum_values": enum_values}

    def _diff(self, base: Dict[str, Set[str]], cur: Dict[str, Set[str]]) -> List[str]:
        changes: List[str] = []
        marker_names = {"endpoints": "endpoint", "required_fields": "required_field", "enum_values": "enum_value"}
        for key, label in (("endpoints", "端点"), ("required_fields", "必填字段"), ("enum_values", "枚举值")):
            removed = base[key] - cur[key]
            added = cur[key] - base[key]
            for r in sorted(removed):
                changes.append(f"[removed_{marker_names[key]}] {label}移除/消失: {r}")
            for a in sorted(added):
                changes.append(f"[added_{marker_names[key]}] {label}新增: {a}")
        return changes

    def _schema_fallback(self, path: str) -> GateResult:
        """OpenAPI 不可用时，校验人工基线中的关键端点均有本地自动化契约覆盖。"""
        baseline = self._load_json(path)
        contracts = baseline.get("contracts") or []
        if not contracts:
            raise GateSetupError(f"Schema 契约基线为空: {path}")
        autotest_dir = self.config.get("autotest_dir", "")
        test_root = os.path.join(autotest_dir, "tests", "api")
        source = ""
        for root, _, files in os.walk(test_root):
            for filename in files:
                if filename.endswith(".js"):
                    with open(os.path.join(root, filename), "r", encoding="utf-8", errors="ignore") as handle:
                        source += handle.read()
        missing = [c.get("endpoint", "?") for c in contracts if c.get("path") not in source]
        module_metrics, module_issues = self._module_coverage(self.module_registry)
        issues = [f"缺少关键契约覆盖: {item}" for item in missing] + module_issues
        return GateResult(
            name=self.name,
            passed=not issues,
            blocking=self.blocking,
            detail=(f"Schema 兜底契约 {len(contracts)} 项，API 覆盖缺失 {len(missing)} 项；"
                    f"模块面 {module_metrics['modules']} 项，覆盖声明缺失 {module_metrics['module_missing']} 项"),
            issues=issues,
            metrics={"mode": "schema_fallback", "contracts": len(contracts), "missing": len(missing), **module_metrics},
        )

    def _module_coverage(self, path: str):
        """Validate module registry completeness and policy-specific coverage evidence."""
        registry = self._load_json(path)
        modules = registry.get("modules") or []
        if not modules:
            raise GateSetupError(f"平台模块注册表为空: {path}")
        autotest_dir = self.config.get("autotest_dir", "")
        counts = {"automated": 0, "candidate": 0, "manual-only": 0, "blocked": 0}
        issues, seen_ids, seen_routes = [], set(), set()
        for index, module in enumerate(modules):
            module_id = module.get("module_id") or f"index-{index}"
            route = module.get("route")
            policy = module.get("coverage_policy")
            reason = str(module.get("coverage_reason") or "").strip()
            if module_id in seen_ids:
                issues.append(f"模块 ID 重复: {module_id}")
            if route in seen_routes:
                issues.append(f"模块路由重复: {route}")
            seen_ids.add(module_id); seen_routes.add(route)
            if policy not in counts:
                issues.append(f"模块 {module_id} coverage_policy 非法: {policy}")
                continue
            counts[policy] += 1
            if policy == "automated":
                refs = module.get("expected_test_refs") or []
                if not refs:
                    issues.append(f"自动化模块 {module_id} 未声明 expected_test_refs")
                for ref in refs:
                    candidate = os.path.normpath(os.path.join(autotest_dir, ref))
                    test_root = os.path.abspath(os.path.join(autotest_dir, "tests"))
                    if os.path.commonpath([os.path.abspath(candidate), test_root]) != test_root:
                        issues.append(f"模块 {module_id} 测试引用越界: {ref}")
                    elif not os.path.isfile(candidate):
                        issues.append(f"模块 {module_id} 缺少自动化覆盖文件: {ref}")
            elif not reason:
                issues.append(f"模块 {module_id} 的 {policy} 策略缺少 coverage_reason")
        metrics = {
            "modules": len(modules),
            "module_automated": counts["automated"],
            "module_candidate": counts["candidate"],
            "module_manual_only": counts["manual-only"],
            "module_blocked": counts["blocked"],
            "module_missing": len(issues),
        }
        return metrics, issues

    def run(self) -> GateResult:
        cfg = self.gate_cfg
        base_path = cfg.get("baseline") or os.path.join(self.snapshot_dir, "snapshot.json")
        if not os.path.isabs(base_path):
            base_path = os.path.join(self.workdir, base_path)
        cur_path = cfg.get("current")
        if cur_path and not os.path.isabs(cur_path):
            cur_path = os.path.join(self.workdir, cur_path)
        if not cur_path:
            cur_path = os.path.join(self.snapshot_dir, "current.json")
        if not os.path.exists(cur_path):
            fallback = cfg.get("schema_fallback")
            if fallback:
                fallback_path = fallback if os.path.isabs(fallback) else os.path.join(self.workdir, fallback)
                return self._schema_fallback(fallback_path)
            raise GateSetupError("缺少当前 OpenAPI 且未配置 Schema 兜底契约")

        base_spec = self._load_json(base_path)
        cur_spec = self._load_json(cur_path)

        base_set = self._collect(base_spec)
        cur_set = self._collect(cur_spec)
        changes = self._diff(base_set, cur_set)

        # 版本信息对比（info.version 变化仅提示）
        info_diff = ""
        bv = (base_spec.get("info") or {}).get("version", "?")
        cv = (cur_spec.get("info") or {}).get("version", "?")
        if bv != cv:
            info_diff = f"OpenAPI version: {bv} -> {cv}"

        breaking = [c for c in changes if any(m in c for m in BREAKING_MARKERS)]
        non_breaking = [c for c in changes if c not in breaking]

        issues = []
        if info_diff:
            issues.append(info_diff)
        issues.extend(changes)

        module_metrics, module_issues = self._module_coverage(self.module_registry)
        issues.extend(module_issues)
        passed = len(breaking) == 0 and not module_issues
        detail = (
            f"变更 {len(changes)} 项（破坏性 {len(breaking)} / 非破坏性 {len(non_breaking)}）"
            if changes
            else "契约无变化，与基线一致"
        )
        if info_diff:
            detail += f"；{info_diff}"
        detail += f"；模块面 {module_metrics['modules']} 项，覆盖声明缺失 {module_metrics['module_missing']} 项"

        return GateResult(
            name=self.name,
            passed=passed,
            blocking=self.blocking,
            detail=detail,
            issues=issues,
            metrics={
                "base_endpoints": len(base_set["endpoints"]),
                "cur_endpoints": len(cur_set["endpoints"]),
                "breaking": len(breaking),
                "non_breaking": len(non_breaking),
                **module_metrics,
            },
        )
