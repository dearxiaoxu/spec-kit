"""Shared safety, serialization, and validation helpers for offline generators."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SENSITIVE_KEY = re.compile(r"(?:password|passwd|pwd|token|authorization|cookie|secret|api[_-]?key|private[_-]?key)", re.I)
SENSITIVE_TEXT = re.compile(
    r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+|((?:password|token|secret|api[_-]?key)\s*[:=]\s*)[^\s,}\]]+"
)
PROTECTED_NAMES = {".env", ".env.local", ".auth", "storageState.json", "test-results.json"}
SAFE_STATUS_KEYS = {"secret_scan"}
LIFECYCLE = {"DISCOVERED", "CANDIDATE", "IN_REVIEW", "REVIEWED", "AUTOMATABLE", "GENERATED", "VALIDATED", "EXECUTED", "REJECTED", "BLOCKED", "STALE"}
MODULE_RISKS = {"readonly", "stateful", "destructive"}
MODULE_PROBE_MODES = {"readonly", "manual-only", "blocked"}
MODULE_COVERAGE_POLICIES = {"automated", "candidate", "manual-only", "blocked"}

class ToolError(Exception):
    """Expected user/configuration or policy error."""
    code = 2

class PolicyError(ToolError):
    code = 3

class InputError(ToolError):
    code = 4


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[REDACTED]" if str(key) not in SAFE_STATUS_KEYS and SENSITIVE_KEY.search(str(key)) else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return SENSITIVE_TEXT.sub(lambda match: f"{match.group(1) or match.group(2) or ''}[REDACTED]", value)
    return value


def resolve_path(value: str | Path, root: Path, *, must_exist: bool = False) -> Path:
    path = Path(value)
    resolved = (path if path.is_absolute() else root / path).resolve()
    if must_exist and not resolved.exists():
        raise InputError(f"输入不存在: {resolved}")
    return resolved


def is_within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath([str(path.resolve()), str(root.resolve())]) == str(root.resolve())
    except ValueError:
        return False


def assert_within(path: Path, root: Path, label: str = "路径") -> None:
    if not is_within(path, root):
        raise PolicyError(f"{label}越界: {path}")


def assert_isolated_output(path: Path, workspace: Path, protected: Iterable[Path]) -> None:
    assert_within(path, workspace, "输出路径")
    resolved = path.resolve()
    for protected_path in protected:
        p = protected_path.resolve()
        if resolved == p or is_within(resolved, p) or is_within(p, resolved):
            raise PolicyError(f"输出目录与受保护目录冲突: {resolved} / {p}")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def write_json(path: Path, value: Any) -> None:
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def stable_unique(items: Iterable[Any], key) -> list[Any]:
    result = {}
    for item in items:
        result[key(item)] = item
    return [result[k] for k in sorted(result)]


def relative_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def validate_asset_doc(doc: dict) -> list[str]:
    errors = []
    if doc.get("schema_version") != "1.0": errors.append("schema_version 必须为 1.0")
    if not isinstance(doc.get("assets"), dict): errors.append("assets 必须为对象")
    if not isinstance(doc.get("evidence"), list): errors.append("evidence 必须为数组")
    evidence_ids = set()
    for i, item in enumerate(doc.get("evidence", [])):
        for key in ("evidence_id", "kind", "path", "location", "content_hash", "collected_at", "redaction_status", "target_version"):
            if not item.get(key): errors.append(f"evidence[{i}] 缺少 {key}")
        evidence_ids.add(item.get("evidence_id"))
    for group in (doc.get("assets") or {}).values():
        if not isinstance(group, list): continue
        for item in group:
            for ref in item.get("evidence_refs", []):
                if ref not in evidence_ids: errors.append(f"资产引用未知证据: {ref}")
    modules = (doc.get("assets") or {}).get("modules")
    if modules is not None:
        if not isinstance(modules, list):
            errors.append("assets.modules 必须为数组")
            return errors
        ids, routes = set(), set()
        for i, module in enumerate(modules):
            for key in ("module_id", "name", "route", "spaces", "capabilities", "risk", "probe_mode", "coverage_policy", "coverage_reason", "evidence_refs"):
                if module.get(key) in (None, "", []): errors.append(f"assets.modules[{i}] 缺少 {key}")
            for key in ("expected_test_refs", "api_evidence_refs"):
                if key not in module or not isinstance(module.get(key), list):
                    errors.append(f"assets.modules[{i}] {key} 必须为数组")
            module_id, route = module.get("module_id"), module.get("route")
            if module_id in ids: errors.append(f"模块 ID 重复: {module_id}")
            if route in routes: errors.append(f"模块路由重复: {route}")
            ids.add(module_id); routes.add(route)
            if not isinstance(route, str) or not route.startswith("/") or ".." in Path(route.split("?", 1)[0]).parts:
                errors.append(f"assets.modules[{i}] 路由非法")
            if module.get("risk") not in MODULE_RISKS: errors.append(f"assets.modules[{i}] risk 非法")
            if module.get("probe_mode") not in MODULE_PROBE_MODES: errors.append(f"assets.modules[{i}] probe_mode 非法")
            if module.get("coverage_policy") not in MODULE_COVERAGE_POLICIES: errors.append(f"assets.modules[{i}] coverage_policy 非法")
    return errors


def validate_candidate_doc(doc: dict) -> list[str]:
    errors = []
    if doc.get("schema_version") != "1.0": errors.append("schema_version 必须为 1.0")
    if not isinstance(doc.get("candidates"), list): errors.append("candidates 必须为数组")
    for i, case in enumerate(doc.get("candidates", [])):
        for key in ("case_id", "title", "lifecycle_status", "evidence_refs"):
            if not case.get(key): errors.append(f"candidates[{i}] 缺少 {key}")
        if case.get("lifecycle_status") not in LIFECYCLE: errors.append(f"candidates[{i}] 生命周期非法")
        if not case.get("steps"): errors.append(f"candidates[{i}] steps 不能为空")
        if not case.get("expected_results"): errors.append(f"candidates[{i}] expected_results 不能为空")
        if case.get("lifecycle_status") in {"AUTOMATABLE", "GENERATED", "VALIDATED", "EXECUTED"}:
            if case.get("review", {}).get("decision") != "approve": errors.append(f"candidates[{i}] 自动化状态必须 review.decision=approve")
            if case.get("automatable") is not True: errors.append(f"candidates[{i}] 自动化状态必须 automatable=true")
            if any(x.get("human_review_required") for x in case.get("expected_results", [])): errors.append(f"candidates[{i}] 仍有待确认断言")
        if case.get("risk") == "destructive" and "production-like" in case.get("allowed_environments", []):
            errors.append(f"candidates[{i}] destructive 不得允许 production-like")
        if case.get("risk") in {"stateful", "destructive"} and not case.get("cleanup"):
            errors.append(f"candidates[{i}] 写操作必须声明 cleanup")
    return errors


def validate_generation_manifest(doc: dict) -> list[str]:
    errors = []
    if doc.get("schema_version") != "1.0": errors.append("schema_version 必须为 1.0")
    if doc.get("lifecycle_status") != "GENERATED": errors.append("生成清单状态必须为 GENERATED")
    if doc.get("write_mode") != "isolated-only": errors.append("write_mode 必须为 isolated-only")
    if not isinstance(doc.get("case_ids"), list) or not isinstance(doc.get("files"), list): errors.append("case_ids/files 必须为数组")
    if any(Path(path).is_absolute() or ".." in Path(path).parts for path in doc.get("files", [])): errors.append("files 包含越界路径")
    validation = doc.get("validation") or {}
    for key in ("schema", "path_boundary", "secret_scan"):
        if validation.get(key) != "PASS": errors.append(f"validation.{key} 必须为 PASS")
    for key in ("lint", "playwright_discovery", "execution"):
        if validation.get(key) not in {"PASS", "FAIL", "NOT_RUN"}: errors.append(f"validation.{key} 状态非法")
    return errors
