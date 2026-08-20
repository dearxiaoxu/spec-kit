#!/usr/bin/env python3
"""Offline discovery of contracts, HAR observations, and Playwright coverage."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.common import (InputError, ToolError, assert_isolated_output, digest,
                          file_digest, redact, relative_posix, validate_asset_doc,
                          write_json, atomic_write)

METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
SKIP_DIRS = {".git", "node_modules", ".tools", "reports", "report", "test-results", "__pycache__"}
SKIP_FILES = {".env", ".env.local", ".auth", "storageState.json"}


def evidence(kind, path, location, detail=None):
    item = {"evidence_id": f"ev-{digest([kind, path, location])[:16]}", "kind": kind, "path": path, "location": location}
    if detail is not None:
        item["detail"] = redact(detail)
    return item


def classify(method, path):
    lowered = path.lower()
    if method == "DELETE" or any(word in lowered for word in ("delete", "destroy", "remove")):
        return "destructive"
    if method in {"POST", "PUT", "PATCH"} or any(word in lowered for word in ("approve", "archive", "publish", "execute", "submit")):
        return "stateful"
    return "readonly"


def schema_summary(schema):
    if not isinstance(schema, dict): return {}
    result = {k: schema[k] for k in ("type", "format", "minLength", "maxLength", "minimum", "maximum", "enum") if k in schema}
    if "required" in schema: result["required"] = list(schema["required"] or [])
    props = schema.get("properties") or {}
    if props:
        result["properties"] = {name: schema_summary(value) for name, value in sorted(props.items())}
    return result


def parse_contract(path: Path, root: Path, assets, evidence_list, conflicts):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        assets["unreadable"].append({"path": relative_posix(path, root), "reason": str(exc)})
        return
    rel = relative_posix(path, root)
    if "paths" in data:
        for route, operations in sorted((data.get("paths") or {}).items()):
            for method, operation in sorted((operations or {}).items()):
                if method.lower() not in METHODS: continue
                op = operation or {}
                request = ((op.get("requestBody") or {}).get("content") or {}).get("application/json", {})
                schema = schema_summary(request.get("schema") or {})
                parameters = []
                for param in op.get("parameters") or []:
                    parameters.append({k: param[k] for k in ("name", "in", "required", "schema") if k in param})
                responses = sorted(str(code) for code in (op.get("responses") or {}).keys())
                item = {
                    "asset_id": f"endpoint:{method.upper()}:{route}", "method": method.upper(), "path": route,
                    "operation": op.get("operationId"), "auth": {"required": bool(op.get("security")), "roles": []},
                    "request_schema": schema, "parameters": parameters, "responses": responses,
                    "side_effect": classify(method.upper(), route), "evidence_refs": [], "confidence": "high",
                }
                ev = evidence("contract", rel, f"/paths/{route}/{method}")
                item["evidence_refs"].append(ev["evidence_id"]); evidence_list.append(ev)
                assets["endpoints"].append(item)
        return
    for contract in data.get("contracts") or []:
        route = contract.get("path") or contract.get("endpoint")
        if not route: continue
        method = str(contract.get("method", "GET")).upper()
        ev = evidence("contract", rel, f"/contracts/{len(assets['endpoints'])}")
        evidence_list.append(ev)
        assets["endpoints"].append({
            "asset_id": f"endpoint:{method}:{route}", "method": method, "path": route,
            "operation": contract.get("name"), "auth": {"required": True, "roles": []},
            "request_schema": {}, "parameters": [], "responses": [], "side_effect": classify(method, route),
            "evidence_refs": [ev["evidence_id"]], "confidence": "medium",
        })


def response_shape(value, depth=0):
    if depth > 2: return "object"
    if isinstance(value, dict): return {str(k): response_shape(v, depth + 1) for k, v in sorted(value.items())}
    if isinstance(value, list): return [response_shape(value[0], depth + 1)] if value else []
    if value is None: return "null"
    return type(value).__name__


def parse_har(path: Path, root: Path, assets, evidence_list):
    try: data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        assets["unreadable"].append({"path": relative_posix(path, root), "reason": str(exc)})
        return
    rel = relative_posix(path, root)
    entries = ((data.get("log") or {}).get("entries") or [])
    for index, entry in enumerate(entries):
        request = entry.get("request") or {}; response = entry.get("response") or {}
        parsed = urlsplit(request.get("url", "")); route = parsed.path or "/"
        query = sorted((key, "[REDACTED]") if re.search(r"token|secret|password|key", key, re.I) else (key, value) for key, value in parse_qsl(parsed.query))
        ev = evidence("har", rel, f"/log/entries/{index}")
        evidence_list.append(ev)
        body = ((response.get("content") or {}).get("text") or "")
        shape = None
        if body and "json" in str((response.get("content") or {}).get("mimeType", "")).lower():
            try: shape = response_shape(json.loads(body))
            except json.JSONDecodeError: shape = "invalid-json"
        assets["observed_flows"].append({
            "asset_id": f"flow:{digest([request.get('method'), route, index])[:16]}",
            "method": str(request.get("method", "GET")).upper(), "path": route, "query": query,
            "status": response.get("status"), "content_type": (response.get("content") or {}).get("mimeType"),
            "response_shape": shape, "risk": classify(str(request.get("method", "GET")).upper(), route),
            "evidence_refs": [ev["evidence_id"]],
        })


def scan_source(path: Path, root: Path, assets, evidence_list):
    if path.name in SKIP_FILES or path.suffix not in {".js", ".ts", ".py", ".json", ".yaml", ".yml"}: return
    try: text = path.read_text(encoding="utf-8", errors="replace")
    except OSError: return
    rel = relative_posix(path, root); sha = file_digest(path)
    refs = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if "env.api(" in line or re.search(r"apiClient\.(get|post|put|patch|delete)", line):
            ev = evidence("source", rel, f"line:{line_no}", line[:240]); evidence_list.append(ev); refs.append(ev["evidence_id"])
    if refs:
        assets["source_rules"].append({"asset_id": f"source:{rel}", "path": rel, "sha256": sha, "evidence_refs": refs, "kind": "source"})
    if path.name.endswith(".spec.js"):
        titles = re.findall(r"(?:test|it)\s*\(\s*['\"]([^'\"]+)", text)
        assets["tests"].append({"asset_id": f"test:{rel}", "path": rel, "sha256": sha, "titles": titles, "covered_paths": sorted(set(re.findall(r"/api(?:/v1)?/[A-Za-z0-9_./{}-]+", text))), "evidence_refs": refs})


def build(args):
    root = Path(args.root).resolve(); pipeline_root = Path(args.pipeline_root).resolve(); autotest_root = Path(args.autotest_root).resolve()
    if not root.exists(): raise InputError(f"root 不存在: {root}")
    output = Path(args.out_dir).resolve()
    assert_isolated_output(output, pipeline_root, [autotest_root / "tests", pipeline_root / "tests"])
    assets = {"endpoints": [], "observed_flows": [], "source_rules": [], "tests": [], "unreadable": []}; evidence_list=[]; conflicts=[]
    contracts = [Path(p).resolve() for p in args.contract]
    if not contracts:
        default = pipeline_root / "assets/contract/current.json"
        if default.exists(): contracts = [default]
    for path in contracts: parse_contract(path, root, assets, evidence_list, conflicts)
    for path in map(Path, args.har): parse_har(path.resolve(), root, assets, evidence_list)
    source_paths = [Path(p).resolve() for p in args.source_dir]
    source_paths += [autotest_root / "tests", autotest_root / "utils", autotest_root / "config"] if not source_paths else []
    for source in source_paths:
        if source.is_file(): scan_source(source, root, assets, evidence_list)
        elif source.is_dir():
            for path in sorted(source.rglob("*")):
                if path.is_file() and not any(part in SKIP_DIRS for part in path.parts): scan_source(path, root, assets, evidence_list)
    for endpoint in assets["endpoints"]:
        endpoint["existing_test_refs"] = [test["path"] for test in assets["tests"] if endpoint["path"] in " ".join(test.get("covered_paths", []))]
    doc = {"schema_version": "1.0", "scan_run_id": args.run_id, "target": {"name": "spec-kit", "environment": args.environment, "version": args.version}, "assets": assets, "evidence": evidence_list, "conflicts": conflicts, "summary": {k: len(v) for k,v in assets.items()}}
    return doc, output


def markdown(doc):
    lines = ["# Discovered Assets", "", f"- Scan run: `{doc['scan_run_id']}`", f"- Environment: `{doc['target']['environment']}`", "", "## Summary", ""]
    for key, value in doc["summary"].items(): lines.append(f"- {key}: {value}")
    lines += ["", "## Endpoints", ""]
    for item in doc["assets"]["endpoints"]:
        lines.append(f"### `{item['method']} {item['path']}`")
        lines.append(f"- risk: `{item['side_effect']}`; confidence: `{item['confidence']}`")
        lines.append(f"- responses: `{', '.join(item['responses']) or 'unknown'}`")
        lines.append(f"- evidence: `{', '.join(item['evidence_refs'])}`")
    lines += ["", "## Existing Tests", ""]
    for item in doc["assets"]["tests"]: lines.append(f"- `{item['path']}`: {', '.join(item['titles']) or 'untitled'}")
    if doc["assets"]["unreadable"]: lines += ["", "## Unreadable", ""] + [f"- `{x['path']}`: {x['reason']}" for x in doc["assets"]["unreadable"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="离线扫描契约、HAR、源码和 Playwright 测试资产")
    parser.add_argument("--root", default="."); parser.add_argument("--pipeline-root", default="."); parser.add_argument("--autotest-root", required=True)
    parser.add_argument("--contract", action="append", default=[]); parser.add_argument("--har", action="append", default=[]); parser.add_argument("--source-dir", action="append", default=[])
    parser.add_argument("--out-dir", required=True); parser.add_argument("--run-id", default="scan-local"); parser.add_argument("--environment", default="isolated"); parser.add_argument("--version", default="unknown")
    parser.add_argument("--validate", action="store_true"); parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        doc, output = build(args)
        errors = validate_asset_doc(doc) if args.validate else []
        if errors: raise ToolError("; ".join(errors))
        if args.dry_run: print(json.dumps(doc["summary"], ensure_ascii=False, sort_keys=True)); return 0
        if output.exists() and any(output.iterdir()): raise ToolError(f"输出目录非空，拒绝覆盖: {output}")
        write_json(output / "discovered-assets.json", redact(doc)); atomic_write(output / "discovered-assets.md", markdown(redact(doc)))
        print(output / "discovered-assets.json"); return 0
    except ToolError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr); return exc.code

if __name__ == "__main__": sys.exit(main())
