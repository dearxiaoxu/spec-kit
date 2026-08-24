#!/usr/bin/env python3
"""Deterministically generate reviewable test candidates from discovered assets."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.common import (
    InputError,
    ToolError,
    assert_isolated_output,
    atomic_write,
    digest,
    redact,
    validate_candidate_doc,
    write_json,
)


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
            assertions.append({"kind": "status", "matcher": "equals", "expected": int(response) if str(response).isdigit() else response, "evidence_refs": refs, "human_review_required": True})
            break
    if scenario["id"] == "shape": assertions.append({"kind": "shape", "matcher": "documented_schema", "expected": endpoint.get("request_schema") or {}, "evidence_refs": refs, "human_review_required": True})
    if scenario["id"] == "unauthenticated":
        assertions.append({"kind": "status", "matcher": "one_of", "expected": [401, 403], "evidence_refs": refs, "human_review_required": True})
    if not assertions:
        assertions.append({"kind": "business", "matcher": "human_confirmation", "expected": scenario["title"], "evidence_refs": refs, "human_review_required": True})
    status = "BLOCKED" if blocked else "CANDIDATE"
    if existing: status = "BLOCKED"; blocked.append("已有测试覆盖，默认不重复生成")
    return {
        "case_id": case_id, "title": title, "module": path.strip("/").split("/")[2] if path.startswith("/api/") and len(path.split("/")) > 2 else "unknown",
        "test_type": "api", "priority": "P1" if risk != "readonly" else "P2", "risk": risk,
        "allowed_environments": allowed_env(risk), "preconditions": ["fixture-managed authentication"],
        "test_data": [], "steps": [{"action": "request", "method": method, "path_expression": path_expression(path), "client": scenario.get("client", "apiClient")}],
        "expected_results": assertions, "cleanup": (["resourceTracker or approved cleanup"] if risk == "stateful" else []),
        "evidence_refs": refs, "confidence": endpoint.get("confidence", "low"), "human_confirmations": blocked + ["confirm status codes and business assertions"],
        "lifecycle_status": status, "automatable": False, "coverage": {"existing_test_refs": existing, "coverage_status": "covered" if existing else "uncovered"},
        "generation_metadata": {"generator_version": "2.0", "template_version": "2.0", "rule_id": f"deterministic.{scenario['id']}", "input_digest": digest(endpoint), "model_provider": None, "model": None, "prompt_version": None},
        "review": {"reviewer": None, "reviewed_at": None, "decision": None, "notes": None},
    }


HIGH_RISK_CAPABILITIES = {
    "create", "review", "transfer-to-sdd", "ai-generation", "template-management", "upload",
    "archive", "delete", "team-create", "mail-settings", "import", "export", "incremental-export",
    "progress-reset", "role-change", "password-reset", "model-management", "key-pool",
    "connection-test", "default-chat", "default-judge", "template-create", "preset-import",
    "preset-export", "rules", "prompt", "estimation-model", "create-from-requirement",
}


def make_module_case(module):
    """Create one safe, review-only navigation candidate for every registered module surface."""
    module_id = module.get("module_id", "unknown")
    route = module.get("route", "/")
    refs = list(module.get("evidence_refs", []))
    existing = list(module.get("existing_test_refs", []))
    policy = module.get("coverage_policy", "blocked")
    probe_mode = module.get("probe_mode", "blocked")
    confirmations = ["确认页面可达、权限边界和主区域选择器"]
    risky = sorted(set(module.get("capabilities", [])) & HIGH_RISK_CAPABILITIES)
    if risky:
        confirmations.append(f"禁止在只读探测中触发高风险能力: {', '.join(risky)}")
    if existing:
        confirmations.append("已有测试覆盖，候选仅用于模块面可追溯，不重复自动生成")
    if policy in {"manual-only", "blocked"} or probe_mode != "readonly":
        confirmations.append(module.get("coverage_reason", "模块仅允许人工验收"))
    lifecycle = "CANDIDATE" if policy == "candidate" and probe_mode == "readonly" else "BLOCKED"
    identity = {"module_id": module_id, "scenario": "page-reachable", "route": route}
    return {
        "case_id": f"case-{digest(identity)[:16]}",
        "title": f"{module.get('name', module_id)} - 模块页面只读可达性",
        "module": module_id,
        "module_id": module_id,
        "test_type": "ui",
        "priority": "P1" if module.get("risk") != "readonly" else "P2",
        "risk": "readonly",
        "source_risk": module.get("risk", "unknown"),
        "allowed_environments": ["production-like", "isolated"],
        "preconditions": ["fixture-managed authentication", "只读导航，不提交表单或触发生成"],
        "test_data": [],
        "steps": [{"action": "navigate", "route": route, "client": "page"}],
        "expected_results": [{
            "kind": "ui", "matcher": "human_confirmation",
            "expected": "模块页面可达且主区域按当前角色正确渲染",
            "evidence_refs": refs, "human_review_required": True,
        }],
        "cleanup": [],
        "evidence_refs": refs,
        "confidence": "medium",
        "human_confirmations": confirmations,
        "lifecycle_status": lifecycle,
        "automatable": False,
        "coverage": {
            "policy": policy,
            "existing_test_refs": existing,
            "coverage_status": "covered" if existing else policy,
        },
        "generation_metadata": {
            "generator_version": "2.1", "template_version": "2.1",
            "rule_id": "deterministic.module-page-reachable", "input_digest": digest(module),
            "model_provider": None, "model": None, "prompt_version": None,
        },
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
    for module in sorted(assets.get("modules", []), key=lambda item: item.get("module_id", "")):
        if only_uncovered and module.get("existing_test_refs"):
            continue
        cases.append(make_module_case(module))
    cases = {case["case_id"]: case for case in cases}
    ordered = [cases[key] for key in sorted(cases)]
    return ordered[:max_cases] if max_cases else ordered

def markdown(doc):
    lines=["# Candidate Test Cases", "", f"- Input digest: `{doc['input_digest']}`", f"- Candidates: `{len(doc['candidates'])}`", "", "> These are candidates only. They are not approved for production or direct execution.", ""]
    for case in doc["candidates"]:
        lines += [f"## {case['case_id']} - {case['title']}", f"- status: `{case['lifecycle_status']}`; risk: `{case['risk']}`; type: `{case['test_type']}`", f"- environments: `{', '.join(case['allowed_environments'])}`", f"- evidence: `{', '.join(case['evidence_refs']) or 'none'}`", f"- human confirmation: {'; '.join(case['human_confirmations'])}", "", "### Steps", ""]
        for step in case["steps"]:
            if step.get("action") == "navigate":
                lines.append(f"1. `{step['client']}` navigate `{step['route']}`")
            else:
                lines.append(f"1. `{step['client']}` {step['method']} `{step['path_expression']}`")
        lines += ["", "### Expected", ""]
        for item in case["expected_results"]: lines.append(f"- {item['kind']} {item['matcher']}: {item['expected']}")
        lines.append("")
    return "\n".join(lines)


def resolve_cli_paths(assets_arg=None, out_dir_arg=None):
    """Resolve IDE-friendly defaults without overwriting previous generated artifacts."""
    pipeline_root = Path(__file__).resolve().parents[1]
    cache_root = pipeline_root / ".pipeline-cache"
    if assets_arg:
        source = Path(assets_arg).resolve()
    else:
        discovered = sorted(
            cache_root.glob("**/discovered-assets.json"),
            key=lambda path: (path.stat().st_mtime_ns, str(path)),
            reverse=True,
        ) if cache_root.exists() else []
        if not discovered:
            raise InputError(
                "未找到 discovered-assets.json；请先运行 discover.py，"
                "或通过 --assets 指定扫描结果"
            )
        source = discovered[0].resolve()
        print(f"[INFO] 未指定 --assets，使用最新扫描结果: {source}", file=sys.stderr)
    if out_dir_arg:
        output = Path(out_dir_arg).resolve()
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = cache_root / "generated-cases" / stamp
        print(f"[INFO] 未指定 --out-dir，输出到新目录: {output}", file=sys.stderr)
    return source, output

def main(argv=None):
    parser=argparse.ArgumentParser(description="根据 discovered-assets 生成确定性候选测试用例")
    parser.add_argument("--assets", help="discovered-assets.json；省略时使用缓存中最新扫描结果")
    parser.add_argument("--out-dir", help="隔离输出目录；省略时创建新的时间戳缓存目录")
    parser.add_argument("--only-uncovered", action="store_true"); parser.add_argument("--max-cases", type=int); parser.add_argument("--validate", action="store_true"); parser.add_argument("--dry-run", action="store_true")
    args=parser.parse_args(argv)
    try:
        source, output = resolve_cli_paths(args.assets, args.out_dir)
        if not source.exists(): raise InputError(f"assets 不存在: {source}")
        source_doc=json.loads(source.read_text(encoding="utf-8")); cases=generate(source_doc, args.only_uncovered, args.max_cases)
        doc={"schema_version":"1.0", "input_digest":digest(source_doc), "candidates":cases, "summary": {"total":len(cases), "module_surfaces":len({c.get('module_id') for c in cases if c.get('module_id')}), "by_status": {status:sum(1 for c in cases if c['lifecycle_status']==status) for status in sorted({c['lifecycle_status'] for c in cases})}}}
        errors=validate_candidate_doc(doc) if args.validate else []
        if errors: raise ToolError("; ".join(errors))
        if args.dry_run: print(json.dumps(doc["summary"], ensure_ascii=False, sort_keys=True)); return 0
        pipeline_root=Path(__file__).resolve().parents[1]; assert_isolated_output(output, pipeline_root, [pipeline_root / "tests", pipeline_root / "assets"])
        if output.exists() and any(output.iterdir()): raise ToolError(f"输出目录非空，拒绝覆盖: {output}")
        write_json(output/"candidate-cases.json", redact(doc)); atomic_write(output/"candidate-cases.md", markdown(redact(doc))); print(output/"candidate-cases.json"); return 0
    except (ToolError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr); return getattr(exc, "code", 2)
if __name__ == "__main__": sys.exit(main())
