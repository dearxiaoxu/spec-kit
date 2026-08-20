"""Shared safety, serialization, and validation helpers for offline generators."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable

SENSITIVE_KEY = re.compile(r"(?:password|passwd|pwd|token|authorization|cookie|secret|api[_-]?key|private[_-]?key)", re.I)
SENSITIVE_TEXT = re.compile(
    r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+|((?:password|token|secret|api[_-]?key)\s*[:=]\s*)[^\s,}\]]+"
)
PROTECTED_NAMES = {".env", ".env.local", ".auth", "storageState.json", "test-results.json"}

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


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[REDACTED]" if SENSITIVE_KEY.search(str(key)) else redact(item) for key, item in value.items()}
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
    return errors


def validate_candidate_doc(doc: dict) -> list[str]:
    errors = []
    if doc.get("schema_version") != "1.0": errors.append("schema_version 必须为 1.0")
    if not isinstance(doc.get("candidates"), list): errors.append("candidates 必须为数组")
    for i, case in enumerate(doc.get("candidates", [])):
        for key in ("candidate_id", "title", "lifecycle_status", "evidence_refs"):
            if not case.get(key): errors.append(f"candidates[{i}] 缺少 {key}")
        if case.get("lifecycle_status") == "VALIDATED" and case.get("review", {}).get("decision") != "approve":
            errors.append(f"candidates[{i}] VALIDATED 必须 review.decision=approve")
        if case.get("risk") == "destructive" and "production-like" in case.get("allowed_environments", []):
            errors.append(f"candidates[{i}] destructive 不得允许 production-like")
    return errors
