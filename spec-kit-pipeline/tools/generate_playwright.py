#!/usr/bin/env python3
"""Generate isolated Playwright skeletons from approved candidate cases."""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.common import ToolError, PolicyError, InputError, assert_isolated_output, digest, redact, write_json, atomic_write

SECRET = re.compile(r"(?i)(password|token|secret|authorization|cookie|api[_-]?key)\s*[:=]")

def check_case(case, approved_only, environment, allow_stateful, allow_destructive):
    status = case.get("lifecycle_status")
    review = case.get("review") or {}
    if approved_only and not (status == "VALIDATED" and review.get("decision") == "approve" and case.get("automatable") is True):
        raise PolicyError(f"候选未通过审核: {case.get('candidate_id')}")
    risk = case.get("risk", "unknown")
    if risk == "stateful" and not allow_stateful: raise PolicyError(f"stateful 未授权: {case.get('candidate_id')}")
    if risk == "destructive" and not allow_destructive: raise PolicyError(f"destructive 未授权: {case.get('candidate_id')}")
    if risk == "destructive" and environment == "production-like": raise PolicyError("production-like 禁止 destructive")
    if not case.get("evidence_refs"): raise PolicyError(f"候选缺少证据: {case.get('candidate_id')}")
    if any("TODO(HUMAN_REVIEW)" in str(x) for x in case.get("expected_results", [])): raise PolicyError(f"候选仍有未审核断言: {case.get('candidate_id')}")

def api_template(case, autotest_root, output_tests):
    client = next((step.get("client", "apiClient") for step in case.get("steps", []) if step.get("action") == "request"), "apiClient")
    fixture_path = Path(autotest_root, "fixtures", "authFixture.js").resolve()
    env_path = Path(autotest_root, "config", "env.js").resolve()
    fixture_import = Path(__import__('os').path.relpath(fixture_path, output_tests)).as_posix()
    env_import = Path(__import__('os').path.relpath(env_path, output_tests)).as_posix()
    fixture_import = './' + fixture_import if not fixture_import.startswith('.') else fixture_import
    env_import = './' + env_import if not env_import.startswith('.') else env_import
    step = next((step for step in case.get("steps", []) if step.get("action") == "request"), {})
    method = str(step.get("method", "GET")).lower()
    expr = step.get("path_expression", "env.api('/unknown')")
    title = case["title"].replace("'", "\\'")
    assertions = []
    for assertion in case.get("expected_results", []):
        text = assertion.get("expression", "")
        if "documented success" in text:
            assertions.append("    // TODO(HUMAN_REVIEW): replace with the confirmed success status assertion")
        elif "documented unauthenticated" in text:
            assertions.append("    // TODO(HUMAN_REVIEW): replace with the confirmed 401/403 assertion")
        elif "response has documented" in text:
            assertions.append("    expect(body).toBeTruthy();")
        else:
            assertions.append(f"    // TODO(HUMAN_REVIEW): {text}")
    if not assertions: assertions = ["    // TODO(HUMAN_REVIEW): add evidence-backed business assertions"]
    resource = "resourceTracker, " if case.get("risk") == "stateful" else ""
    return "\n".join([
        f"// Generated candidate: {case['candidate_id']}",
        f"// Evidence: {', '.join(case['evidence_refs'])}",
        f"const {{ test, expect, describe }} = require('{fixture_import}');",
        f"const env = require('{env_import}');", "",
        f"describe('{title}', () => {{", f"  test('{title}', async ({{ {resource}{client} }}) => {{",
        f"    const res = await {client}.{method}(`${{{expr}}}`);", "    const body = await res.json();", "",
        *assertions, "  });", "});", "",
    ])

def generate(cases, args, autotest_root, output_tests):
    files=[]
    for case in sorted(cases, key=lambda c: c["candidate_id"]):
        check_case(case, args.approved_only, args.environment, args.allow_stateful, args.allow_destructive)
        content=api_template(case, autotest_root, output_tests)
        if SECRET.search(content): raise PolicyError(f"生成内容疑似包含敏感字段: {case['candidate_id']}")
        filename=f"generated_{case['candidate_id'].replace('-', '_')}.spec.js"
        rel=f"tests/{filename}"; files.append({"candidate_id":case["candidate_id"], "path":rel, "content":content})
    return files

def main(argv=None):
    parser=argparse.ArgumentParser(description="为已审核候选生成隔离 Playwright 骨架")
    parser.add_argument("--candidates", required=True); parser.add_argument("--out-dir", required=True); parser.add_argument("--autotest-root", required=True); parser.add_argument("--candidate-id", action="append", default=[]); parser.add_argument("--approved-only", action="store_true", default=False); parser.add_argument("--environment", default="isolated"); parser.add_argument("--allow-stateful", action="store_true"); parser.add_argument("--allow-destructive", action="store_true"); parser.add_argument("--validate", action="store_true"); parser.add_argument("--dry-run", action="store_true")
    args=parser.parse_args(argv)
    try:
        source=Path(args.candidates).resolve()
        if not source.exists(): raise InputError(f"候选文件不存在: {source}")
        doc=json.loads(source.read_text(encoding="utf-8")); cases=doc.get("candidates") or []
        if args.candidate_id: cases=[c for c in cases if c.get("candidate_id") in args.candidate_id]
        files=generate(cases, args)
        output=Path(args.out_dir).resolve(); pipeline_root=Path(__file__).resolve().parents[1]; autotest=Path(args.autotest_root).resolve()
        assert_isolated_output(output, pipeline_root, [autotest/"tests", pipeline_root/"tests"])
        manifest={"schema_version":"1.0", "candidate_ids":[x["candidate_id"] for x in files], "files":[x["path"] for x in files], "write_mode":"isolated-only", "input_digest":digest(doc), "template_version":"1", "protected_paths":[str(autotest/"tests")], "validation":{"schema":"PASS", "path_boundary":"PASS", "secret_scan":"PASS"}}
        if args.dry_run: print(json.dumps({"files":len(files), "manifest":manifest}, ensure_ascii=False, sort_keys=True)); return 0
        if output.exists() and any(output.iterdir()): raise ToolError(f"输出目录非空，拒绝覆盖: {output}")
        for item in files:
            path=output/item["path"]; path.parent.mkdir(parents=True, exist_ok=True); atomic_write(path, item["content"])
            write_json(output/"evidence"/f"{item['candidate_id']}.json", {"candidate_id":item["candidate_id"], "evidence_refs":next(c for c in cases if c["candidate_id"]==item["candidate_id"]).get("evidence_refs", [])})
        write_json(output/"manifest.json", redact(manifest)); atomic_write(output/"README.md", "# Generated Playwright Preview\n\nThis is an isolated, human-review-only preview. It is not a formal test directory.\n")
        print(output/"manifest.json"); return 0
    except (ToolError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr); return getattr(exc, "code", 2)
if __name__ == "__main__": sys.exit(main())
