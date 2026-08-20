#!/usr/bin/env python3
"""Deterministically generate reviewable test candidates from discovered assets."""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.common import ToolError, InputError, assert_isolated_output, digest, redact, validate_candidate_doc, write_json, atomic_write


def endpoint_key(e): return f"{str(e.get('method','GET')).upper()} {e.get('path','')}"
def covered(endpoint, assets): return [t["path"] for t in assets.get("tests", []) if endpoint.get("path", "") in " ".join(t.get("covered_paths", []))]
def risk_for(e): return e.get("side_effect", "unknown")
def allowed_env(risk): return ["production-like", "isolated"] if risk == "readonly" else ["isolated"]
def path_expression(path):
    return f"env.api('{path}')" if path.startswith("/api/") else f"env.api('/{path.lstrip('/')}' )"

def make_case(endpoint, scenario, assets):
    method = str(endpoint.get("method", "GET")).upper(); path = endpoint.get("path", "")
    risk = risk_for(endpoint); refs = list(endpoint.get("evidence_refs", [])); existing = covered(endpoint, assets)
    blocked = []
    if risk not in {"readonly", "stateful", "destructive"}: blocked.append("未知副作用")
    if risk == "destructive": blocked.append("破坏性操作默认阻断")
    if risk == "stateful" and "isolated" not in allowed_env(risk): blocked.append("缺少隔离环境")
    title = f"{method} {path} - {scenario['title']}"
    identity = {"endpoint": endpoint_key(endpoint), "scenario": scenario["id"], "client": scenario.get("client", "apiClient")}
    case_id = f"case-{digest(identity)[:16]}"
    assertions = []
    for response in endpoint.get("responses", []):
        if str(response).startswith("2") and scenario["id"] == "reachable":
            assertions.append({"kind": "status", "expression": f"status is one of documented success responses ({response})", "strength": "candidate", "human_review_required": True})
            break
    if scenario["id"] == "shape": assertions.append({"kind": "shape", "expression": "response has documented JSON shape", "strength": "candidate", "human_review_required": True})
    if scenario["id"] == "unauthenticated":
        assertions.append({"kind": "status", "expression": "documented unauthenticated status", "strength": "candidate", "human_review_required": True})
    status = "BLOCKED" if blocked else ("DRAFT" if any(x.get("human_review_required") for x in assertions) else "AUTOMATABLE")
    if existing: status = "DRAFT"; blocked.append("已有测试覆盖，默认不重复生成")
    return {
        "candidate_id": case_id, "title": title, "module": path.strip("/").split("/")[2] if path.startswith("/api/") and len(path.split("/")) > 2 else "unknown",
        "test_type": "api", "priority": "P1" if risk != "readonly" else "P2", "risk": risk,
        "allowed_environments": allowed_env(risk), "preconditions": ["fixture-managed authentication"],
        "test_data": [], "steps": [{"action": "request", "method": method, "path_expression": path_expression(path), "client": scenario.get("client", "apiClient")}],
        "expected_results": assertions, "cleanup": (["resourceTracker or approved cleanup"] if risk == "stateful" else []),
        "evidence_refs": refs, "confidence": endpoint.get("confidence", "low"), "human_confirmations": blocked + ["confirm status codes and business assertions"],
        "lifecycle_status": status, "automatable": status == "AUTOMATABLE", "coverage": {"existing_test_refs": existing, "coverage_status": "covered" if existing else "uncovered"},
        "generator": {"rule_id": f"deterministic.{scenario['id']}", "rule_version": "1", "input_digest": digest(endpoint)},
        "review": {"reviewer": None, "reviewed_at": None, "decision": None, "notes": None},
    }

def generate(doc, only_uncovered=False, max_cases=None):
    assets = doc.get("assets", {}); cases=[]
    for endpoint in sorted(assets.get("endpoints", []), key=endpoint_key):
        existing = covered(endpoint, assets)
        if only_uncovered and existing: continue
        scenarios = [{"id":"reachable", "title":"请求可达性", "client":"apiClient"}, {"id":"shape", "title":"响应结构", "client":"apiClient"}]
        schema = endpoint.get("request_schema") or {}
        props = schema.get("properties") or {}
        required = schema.get("required") or []
        if required: scenarios.append({"id":"required", "title":"缺少必填字段", "client":"apiClient"})
        if any("maxLength" in value or "minLength" in value for value in props.values() if isinstance(value, dict)):
            scenarios.append({"id":"boundary", "title":"字段边界", "client":"apiClient"})
        if endpoint.get("auth", {}).get("required"):
            scenarios.append({"id":"unauthenticated", "title":"未认证访问", "client":"anonClient"})
        for scenario in scenarios: cases.append(make_case(endpoint, scenario, assets))
    cases = {case["candidate_id"]: case for case in cases}
    ordered = [cases[key] for key in sorted(cases)]
    return ordered[:max_cases] if max_cases else ordered

def markdown(doc):
    lines=["# Candidate Test Cases", "", f"- Input digest: `{doc['input_digest']}`", f"- Candidates: `{len(doc['candidates'])}`", "", "> These are candidates only. They are not approved for production or direct execution.", ""]
    for case in doc["candidates"]:
        lines += [f"## {case['candidate_id']} - {case['title']}", f"- status: `{case['lifecycle_status']}`; risk: `{case['risk']}`; type: `{case['test_type']}`", f"- environments: `{', '.join(case['allowed_environments'])}`", f"- evidence: `{', '.join(case['evidence_refs']) or 'none'}`", f"- human confirmation: {'; '.join(case['human_confirmations'])}", "", "### Steps", ""]
        for step in case["steps"]: lines.append(f"1. `{step['client']}` {step['method']} `{step['path_expression']}`")
        lines += ["", "### Expected", ""]
        for item in case["expected_results"]: lines.append(f"- {item['expression']}")
        lines.append("")
    return "\n".join(lines)

def main(argv=None):
    parser=argparse.ArgumentParser(description="根据 discovered-assets 生成确定性候选测试用例")
    parser.add_argument("--assets", required=True); parser.add_argument("--out-dir", required=True); parser.add_argument("--only-uncovered", action="store_true"); parser.add_argument("--max-cases", type=int); parser.add_argument("--validate", action="store_true"); parser.add_argument("--dry-run", action="store_true")
    args=parser.parse_args(argv)
    try:
        source=Path(args.assets).resolve()
        if not source.exists(): raise InputError(f"assets 不存在: {source}")
        source_doc=json.loads(source.read_text(encoding="utf-8")); cases=generate(source_doc, args.only_uncovered, args.max_cases)
        doc={"schema_version":"1.0", "input_digest":digest(source_doc), "candidates":cases, "summary": {"total":len(cases), "by_status": {status:sum(1 for c in cases if c['lifecycle_status']==status) for status in sorted({c['lifecycle_status'] for c in cases})}}}
        errors=validate_candidate_doc(doc) if args.validate else []
        if errors: raise ToolError("; ".join(errors))
        if args.dry_run: print(json.dumps(doc["summary"], ensure_ascii=False, sort_keys=True)); return 0
        output=Path(args.out_dir).resolve(); pipeline_root=Path(__file__).resolve().parents[1]; assert_isolated_output(output, pipeline_root, [pipeline_root / "tests", pipeline_root / "assets"])
        if output.exists() and any(output.iterdir()): raise ToolError(f"输出目录非空，拒绝覆盖: {output}")
        write_json(output/"candidate-cases.json", redact(doc)); atomic_write(output/"candidate-cases.md", markdown(redact(doc))); print(output/"candidate-cases.json"); return 0
    except (ToolError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr); return getattr(exc, "code", 2)
if __name__ == "__main__": sys.exit(main())
