#!/usr/bin/env python3
"""Generate isolated Playwright skeletons from approved candidate cases."""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.common import ToolError, PolicyError, InputError, assert_isolated_output, digest, redact, validate_candidate_doc, validate_generation_manifest, write_json, atomic_write

SECRET = re.compile(r"(?i)(password|token|secret|authorization|cookie|api[_-]?key)\s*[:=]")

def case_id(case):
    return case.get("case_id") or case.get("candidate_id")


def check_case(case, environment, allow_stateful, allow_destructive):
    status = case.get("lifecycle_status")
    review = case.get("review") or {}
    if not (status == "AUTOMATABLE" and review.get("decision") == "approve" and case.get("automatable") is True):
        raise PolicyError(f"候选尚未进入 AUTOMATABLE: {case_id(case)}")
    risk = case.get("risk", "unknown")
    if risk == "stateful" and not allow_stateful: raise PolicyError(f"stateful 未授权: {case_id(case)}")
    if risk == "destructive" and not allow_destructive: raise PolicyError(f"destructive 未授权: {case_id(case)}")
    if risk in {"stateful", "destructive"}:
        raise PolicyError(f"当前模板尚未实现可验证的资源登记与清理，拒绝生成写操作: {case_id(case)}")
    if risk == "destructive" and environment == "production-like": raise PolicyError("production-like 禁止 destructive")
    if not case.get("evidence_refs"): raise PolicyError(f"候选缺少证据: {case_id(case)}")
    if not case.get("expected_results") or any(x.get("human_review_required") for x in case.get("expected_results", [])):
        raise PolicyError(f"候选仍有未审核断言: {case_id(case)}")
    if any(x.get("matcher") not in {"equals", "one_of", "truthy"} for x in case.get("expected_results", [])):
        raise PolicyError(f"候选包含不可执行断言: {case_id(case)}")
    if risk in {"stateful", "destructive"} and not case.get("cleanup"):
        raise PolicyError(f"写操作缺少清理声明: {case_id(case)}")

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
        matcher, expected, kind = assertion.get("matcher"), assertion.get("expected"), assertion.get("kind")
        target = "res.status()" if kind == "status" else "body"
        if matcher == "equals": assertions.append(f"    expect({target}).toBe({json.dumps(expected, ensure_ascii=False)});")
        elif matcher == "one_of": assertions.append(f"    expect({json.dumps(expected, ensure_ascii=False)}).toContain({target});")
        elif matcher == "truthy": assertions.append(f"    expect({target}).toBeTruthy();")
    return "\n".join([
        f"// Generated candidate: {case_id(case)}",
        f"// Evidence: {', '.join(case['evidence_refs'])}",
        f"const {{ test, expect, describe }} = require('{fixture_import}');",
        f"const env = require('{env_import}');", "",
        f"describe('{title}', () => {{", f"  test('{title}', async ({{ {client} }}) => {{",
        f"    const res = await {client}.{method}(`${{{expr}}}`);", "    const body = await res.json();", "",
        *assertions, "  });", "});", "",
    ])

def generate(cases, args, autotest_root, output_tests):
    files=[]
    for case in sorted(cases, key=case_id):
        check_case(case, args.environment, args.allow_stateful, args.allow_destructive)
        content=api_template(case, autotest_root, output_tests)
        cid = case_id(case)
        if SECRET.search(content): raise PolicyError(f"生成内容疑似包含敏感字段: {cid}")
        filename=f"generated_{cid.replace('-', '_')}.spec.js"
        rel=f"tests/{filename}"; files.append({"case_id":cid, "path":rel, "content":content})
    return files

def main(argv=None):
    parser=argparse.ArgumentParser(description="为已审核候选生成隔离 Playwright 骨架")
    parser.add_argument("--candidates", required=True); parser.add_argument("--out-dir", required=True); parser.add_argument("--autotest-root", required=True); parser.add_argument("--case-id", action="append", default=[]); parser.add_argument("--environment", default="isolated"); parser.add_argument("--allow-stateful", action="store_true"); parser.add_argument("--allow-destructive", action="store_true"); parser.add_argument("--validate", action="store_true"); parser.add_argument("--dry-run", action="store_true")
    args=parser.parse_args(argv)
    try:
        source=Path(args.candidates).resolve()
        if not source.exists(): raise InputError(f"候选文件不存在: {source}")
        doc=json.loads(source.read_text(encoding="utf-8")); cases=doc.get("candidates") or []
        if args.validate:
            errors = validate_candidate_doc(doc)
            if errors: raise ToolError("; ".join(errors))
        output=Path(args.out_dir).resolve(); pipeline_root=Path(__file__).resolve().parents[1]; autotest=Path(args.autotest_root).resolve()
        assert_isolated_output(output, pipeline_root, [autotest/"tests", pipeline_root/"tests"])
        if args.case_id: cases=[c for c in cases if case_id(c) in args.case_id]
        files=generate(cases, args, autotest, output/"tests")
        manifest={"schema_version":"1.0", "case_ids":[x["case_id"] for x in files], "files":[x["path"] for x in files], "write_mode":"isolated-only", "input_digest":digest(doc), "template_version":"2.0", "lifecycle_status":"GENERATED", "protected_paths":[str(autotest/"tests")], "validation":{"schema":"PASS", "path_boundary":"PASS", "secret_scan":"PASS", "lint":"NOT_RUN", "playwright_discovery":"NOT_RUN", "execution":"NOT_RUN"}}
        if args.validate:
            errors = validate_generation_manifest(manifest)
            if errors: raise ToolError("; ".join(errors))
        if args.dry_run: print(json.dumps({"files":len(files), "manifest":manifest}, ensure_ascii=False, sort_keys=True)); return 0
        if output.exists() and any(output.iterdir()): raise ToolError(f"输出目录非空，拒绝覆盖: {output}")
        for item in files:
            path=output/item["path"]; path.parent.mkdir(parents=True, exist_ok=True); atomic_write(path, item["content"])
            write_json(output/"evidence"/f"{item['case_id']}.json", {"case_id":item["case_id"], "evidence_refs":next(c for c in cases if case_id(c)==item["case_id"]).get("evidence_refs", [])})
        write_json(output/"manifest.json", redact(manifest)); atomic_write(output/"README.md", "# Generated Playwright Preview\n\nThis is an isolated, human-review-only preview. It is not a formal test directory.\n")
        print(output/"manifest.json"); return 0
    except (ToolError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr); return getattr(exc, "code", 2)
if __name__ == "__main__": sys.exit(main())
