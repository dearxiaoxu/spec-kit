from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PIPELINE_ROOT.parent
sys.path.insert(0, str(PIPELINE_ROOT))

from tools import discover, fetch_contract, generate_cases, generate_playwright
from tools.common import PolicyError, redact, validate_asset_doc, validate_candidate_doc


class DiscoveryTests(unittest.TestCase):
    def test_embedded_contract_method_is_preserved(self):
        with tempfile.TemporaryDirectory(dir=WORKSPACE_ROOT) as tmp:
            root = Path(tmp)
            contract = root / "contract.json"
            contract.write_text(json.dumps({"contracts": [{"endpoint": "POST /api/v1/jobs", "name": "create"}]}), encoding="utf-8")
            assets = {"endpoints": [], "observed_flows": [], "source_rules": [], "tests": [], "unreadable": []}
            evidence = []
            discover.parse_contract(contract, root, assets, evidence, "build-1")
            self.assertEqual((assets["endpoints"][0]["method"], assets["endpoints"][0]["path"]), ("POST", "/api/v1/jobs"))
            self.assertEqual(assets["endpoints"][0]["side_effect"], "stateful")

    def test_embedded_method_wins_when_contract_has_short_path(self):
        with tempfile.TemporaryDirectory(dir=WORKSPACE_ROOT) as tmp:
            root = Path(tmp); contract = root / "contract.json"
            contract.write_text(json.dumps({"contracts": [{"endpoint": "POST /api/v1/jobs", "path": "/jobs"}]}), encoding="utf-8")
            assets = {"endpoints": [], "observed_flows": [], "source_rules": [], "tests": [], "unreadable": []}
            discover.parse_contract(contract, root, assets, [], "build-1")
            self.assertEqual((assets["endpoints"][0]["method"], assets["endpoints"][0]["path"]), ("POST", "/jobs"))

    def test_har_query_values_are_always_redacted(self):
        with tempfile.TemporaryDirectory(dir=WORKSPACE_ROOT) as tmp:
            root = Path(tmp)
            har = root / "sample.har"
            har.write_text(json.dumps({"log": {"entries": [{"request": {"method": "GET", "url": "https://example.test/users?email=a@b.test&id=42"}, "response": {"status": 200, "content": {}}}]}}), encoding="utf-8")
            assets = {"observed_flows": [], "unreadable": []}
            discover.parse_har(har, root, assets, [], "build-1")
            self.assertEqual(assets["observed_flows"][0]["query"], [["email", "[REDACTED]"], ["id", "[REDACTED]"]])

    def test_platform_registry_has_exactly_fourteen_unique_modules(self):
        registry = json.loads((PIPELINE_ROOT / "assets" / "platform-modules.json").read_text(encoding="utf-8"))
        modules = registry["modules"]
        self.assertEqual(len(modules), 14)
        self.assertEqual(len({item["module_id"] for item in modules}), 14)
        self.assertEqual(len({item["route"] for item in modules}), 14)

    def test_module_registry_is_loaded_with_evidence(self):
        assets = {"modules": [], "unreadable": []}; evidence = []
        discover.parse_module_registry(
            PIPELINE_ROOT / "assets" / "platform-modules.json", WORKSPACE_ROOT,
            assets, evidence, "build-1",
        )
        self.assertEqual(len(assets["modules"]), 14)
        self.assertEqual(len(evidence), 14)
        doc = {"schema_version": "1.0", "assets": assets, "evidence": evidence}
        self.assertFalse(validate_asset_doc(doc))

    def test_duplicate_module_id_is_rejected(self):
        module = {"module_id": "x", "name": "X", "route": "/x", "spaces": ["personal"],
                  "capabilities": ["read"], "risk": "readonly", "probe_mode": "readonly",
                  "coverage_policy": "candidate", "coverage_reason": "待覆盖", "expected_test_refs": [],
                  "api_evidence_refs": [], "evidence_refs": ["ev-1"]}
        doc = {"schema_version": "1.0", "assets": {"modules": [module, {**module, "route": "/y"}]},
               "evidence": [{"evidence_id": "ev-1", "kind": "manual", "path": "registry.json",
                             "location": "/modules/0", "content_hash": "sha256:x", "collected_at": "now",
                             "redaction_status": "not_required", "target_version": "v1"}]}
        self.assertTrue(any("模块 ID 重复" in error for error in validate_asset_doc(doc)))


class CandidateTests(unittest.TestCase):
    def test_candidates_never_self_approve_and_have_assertions(self):
        source = {"assets": {"tests": [], "endpoints": [{"method": "POST", "path": "/api/v1/jobs", "side_effect": "stateful", "responses": ["201"], "evidence_refs": ["ev-1"], "confidence": "high", "auth": {"required": True}, "request_schema": {"required": ["name"], "properties": {"name": {"minLength": 1}}}}]}}
        cases = generate_cases.generate(source)
        self.assertTrue(cases)
        self.assertTrue(all(case["lifecycle_status"] == "CANDIDATE" for case in cases))
        self.assertTrue(all(case["automatable"] is False and case["expected_results"] for case in cases))
        self.assertFalse(validate_candidate_doc({"schema_version": "1.0", "candidates": cases}))

    def test_cli_paths_accept_explicit_input_and_create_isolated_default_output(self):
        source = PIPELINE_ROOT / "assets" / "platform-modules.json"
        resolved_source, output = generate_cases.resolve_cli_paths(str(source), None)
        self.assertEqual(resolved_source, source.resolve())
        self.assertTrue(output.is_relative_to(PIPELINE_ROOT / ".pipeline-cache" / "generated-cases"))

    def test_all_fourteen_modules_are_represented_in_case_layer(self):
        registry = json.loads((PIPELINE_ROOT / "assets" / "platform-modules.json").read_text(encoding="utf-8"))
        modules = [{**module, "evidence_refs": [f"ev-{module['module_id']}"], "existing_test_refs": []}
                   for module in registry["modules"]]
        cases = generate_cases.generate({"assets": {"tests": [], "endpoints": [], "modules": modules}})
        self.assertEqual(len(cases), 14)
        self.assertEqual({case["module_id"] for case in cases}, {module["module_id"] for module in modules})
        self.assertTrue(all(case["automatable"] is False for case in cases))
        self.assertEqual({case["lifecycle_status"] for case in cases}, {"CANDIDATE", "BLOCKED"})
        self.assertFalse(validate_candidate_doc({"schema_version": "1.0", "candidates": cases}))


class PlaywrightGenerationTests(unittest.TestCase):
    def args(self):
        return argparse.Namespace(environment="isolated", allow_stateful=False, allow_destructive=False)

    def approved_case(self):
        return {"case_id": "case-1", "title": "GET health", "risk": "readonly", "lifecycle_status": "AUTOMATABLE", "automatable": True, "review": {"decision": "approve"}, "evidence_refs": ["ev-1"], "steps": [{"action": "request", "method": "GET", "path_expression": "env.api('/api/health')", "client": "apiClient"}], "expected_results": [{"kind": "status", "matcher": "equals", "expected": 200, "human_review_required": False}]}

    def test_unreviewed_candidate_is_rejected(self):
        case = self.approved_case(); case["lifecycle_status"] = "CANDIDATE"
        with self.assertRaises(PolicyError):
            generate_playwright.generate([case], self.args(), WORKSPACE_ROOT / "spec-kit-autotest", PIPELINE_ROOT / ".pipeline-cache" / "preview" / "tests")

    def test_approved_candidate_generates_executable_assertion(self):
        files = generate_playwright.generate([self.approved_case()], self.args(), WORKSPACE_ROOT / "spec-kit-autotest", PIPELINE_ROOT / ".pipeline-cache" / "preview" / "tests")
        self.assertIn("expect(res.status()).toBe(200);", files[0]["content"])
        self.assertNotIn("TODO(HUMAN_REVIEW)", files[0]["content"])

    def test_stateful_generation_is_blocked_until_cleanup_template_exists(self):
        case = self.approved_case(); case["risk"] = "stateful"; case["cleanup"] = ["declared"]
        args = self.args(); args.allow_stateful = True
        with self.assertRaises(PolicyError):
            generate_playwright.generate([case], args, WORKSPACE_ROOT / "spec-kit-autotest", PIPELINE_ROOT / ".pipeline-cache" / "preview" / "tests")


class ContractFetchTests(unittest.TestCase):
    def test_tls_verification_is_default(self):
        self.assertEqual(fetch_contract._ssl_ctx().verify_mode, fetch_contract.ssl.CERT_REQUIRED)

    def test_baseline_refuses_implicit_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot.json"; path.write_text("{}", encoding="utf-8")
            with self.assertRaises(Exception):
                fetch_contract.save_contract(path, {"openapi": "3.0.0", "info": {}, "paths": {}}, overwrite=False)

    def test_secret_scan_status_is_not_redacted(self):
        self.assertEqual(redact({"secret_scan": "PASS", "api_key": "leak"}), {"secret_scan": "PASS", "api_key": "[REDACTED]"})


if __name__ == "__main__":
    unittest.main()
