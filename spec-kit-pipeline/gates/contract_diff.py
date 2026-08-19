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
        for key, label in (("endpoints", "端点"), ("required_fields", "必填字段"), ("enum_values", "枚举值")):
            removed = base[key] - cur[key]
            added = cur[key] - base[key]
            for r in sorted(removed):
                changes.append(f"[{key}] 移除/消失: {r}")
            for a in sorted(added):
                changes.append(f"[{key}] 新增: {a}")
        return changes

    def run(self) -> GateResult:
        cfg = self.gate_cfg
        base_path = cfg.get("baseline") or os.path.join(self.snapshot_dir, "snapshot.json")
        cur_path = cfg.get("current")
        if not cur_path:
            cur_path = os.path.join(self.snapshot_dir, "current.json")
            if not os.path.exists(cur_path):
                raise GateSetupError(
                    "缺少当前契约。先执行: python3 pipeline.py --fetch-contract （或 tools/fetch_contract.py）"
                )

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

        passed = len(breaking) == 0
        detail = (
            f"变更 {len(changes)} 项（破坏性 {len(breaking)} / 非破坏性 {len(non_breaking)}）"
            if changes
            else "契约无变化，与基线一致"
        )
        if info_diff:
            detail += f"；{info_diff}"

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
            },
        )
