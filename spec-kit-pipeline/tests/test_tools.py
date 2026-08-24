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
from tools.common import PolicyError, redact, validate_candidate_doc


class DiscoveryTests(unittest.TestCase):
    def test_embedded_contract_method_is_preserved(self):
        with tempfile.TemporaryDirectory(dir=WORKSPACE_ROOT) as tmp:
            root = Path(tmp)
            contract = root / "contract.json"
            contract.write_text(json.dumps({"contracts": [{"endpoint": "POST /api/v1/jobs", "name": "create"}]}), encoding="utf-8")
            assets = {"endpoints": [], "observed_flows": [], "source_rules": [], "tests": [], "unreadable": []}
            evidence = []
            discover.parse_contract(contract, root, assets, evidence, [], "build-1")
            self.assertEqual((assets["endpoints"][0]["method"], assets["endpoints"][0]["path"]), ("POST", "/api/v1/jobs"))
            self.assertEqual(assets["endpoints"][0]["side_effect"], "stateful")

    def test_embedded_method_wins_when_contract_has_short_path(self):
        with tempfile.TemporaryDirectory(dir=WORKSPACE_ROOT) as tmp:
            root = Path(tmp); contract = root / "contract.json"
            contract.write_text(json.dumps({"contracts": [{"endpoint": "POST /api/v1/jobs", "path": "/jobs"}]}), encoding="utf-8")
            assets = {"endpoints": [], "observed_flows": [], "source_rules": [], "tests": [], "unreadable": []}
            discover.parse_contract(contract, root, assets, [], [], "build-1")
            self.assertEqual((assets["endpoints"][0]["method"], assets["endpoints"][0]["path"]), ("POST", "/jobs"))

    def test_har_query_values_are_always_redacted(self):
        with tempfile.TemporaryDirectory(dir=WORKSPACE_ROOT) as tmp:
            root = Path(tmp)
            har = root / "sample.har"
            har.write_text(json.dumps({"log": {"entries": [{"request": {"method": "GET", "url": "https://example.test/users?email=a@b.test&id=42"}, "response": {"status": 200, "content": {}}}]}}), encoding="utf-8")
            assets = {"observed_flows": [], "unreadable": []}
            discover.parse_har(har, root, assets, [], "build-1")
            self.assertEqual(assets["observed_flows"][0]["query"], [["email", "[REDACTED]"], ["id", "[REDACTED]"]])


class CandidateTests(unittest.TestCase):
    def test_candidates_never_self_approve_and_have_assertions(self):
        source = {"assets": {"tests": [], "endpoints": [{"method": "POST", "path": "/api/v1/jobs", "side_effect": "stateful", "responses": ["201"], "evidence_refs": ["ev-1"], "confidence": "high", "auth": {"required": True}, "request_schema": {"required": ["name"], "properties": {"name": {"minLength": 1}}}}]}}
        cases = generate_cases.generate(source)
        self.assertTrue(cases)
        self.assertTrue(all(case["lifecycle_status"] == "CANDIDATE" for case in cases))
        self.assertTrue(all(case["automatable"] is False and case["expected_results"] for case in cases))
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
