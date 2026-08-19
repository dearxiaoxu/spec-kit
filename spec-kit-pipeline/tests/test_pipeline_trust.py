from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE_ROOT))

import pipeline
from gates.base import Gate, GateResult
from gates.e2e_regression import E2ERegressionGate


class ExplodingBlockingGate(Gate):
    name = "exploding_blocking"
    blocking = True

    def run(self) -> GateResult:
        raise RuntimeError("boom")


class PipelineResultTrustTests(unittest.TestCase):
    def test_skipped_result_is_marked_skip(self):
        result = GateResult(name="disabled", passed=True, skipped=True)
        self.assertEqual(pipeline.result_mark(result), "SKIP")

    def test_report_summary_excludes_skipped_from_passed(self):
        results = [
            GateResult(name="passed", passed=True),
            GateResult(name="skipped", passed=True, skipped=True),
            GateResult(name="failed", passed=False),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = pipeline.write_report(results, {"report_dir": tmpdir})
            with open(report_path, "r", encoding="utf-8") as handle:
                report = json.load(handle)
            with open(report_path.removesuffix(".json") + ".md", "r", encoding="utf-8") as handle:
                markdown = handle.read()

        self.assertEqual(report["summary"], {
            "total": 3,
            "passed": 1,
            "failed": 1,
            "skipped": 1,
        })
        self.assertIn("## [SKIP] skipped", markdown)

    def test_blocking_gate_exception_keeps_blocking_semantics(self):
        result = pipeline.run_gate(ExplodingBlockingGate, {})
        self.assertFalse(result.passed)
        self.assertTrue(result.blocking)
        self.assertIn("boom", result.detail)

    def test_blocking_gate_exception_makes_main_return_three(self):
        with patch.object(pipeline, "ALL_GATES", [ExplodingBlockingGate]), \
                patch.object(pipeline, "load_config", return_value={}), \
                patch.object(pipeline, "write_report"), \
                patch.object(sys, "argv", ["pipeline.py"]):
            self.assertEqual(pipeline.main(), 3)


class E2EReportFreshnessTests(unittest.TestCase):
    def make_gate(self, autotest_dir: str) -> E2ERegressionGate:
        config = {
            "autotest_dir": autotest_dir,
            "gates": {
                "e2e_regression": {
                    "report_file": "reports/test-results.json",
                    "script": "test:api",
                }
            },
        }
        gate = E2ERegressionGate(config, ctx={})
        gate.init()
        return gate

    def test_old_report_is_removed_before_test_command_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir, "reports", "test-results.json")
            report_path.parent.mkdir()
            report_path.write_text('{"stats":{"expected":99}}', encoding="utf-8")
            gate = self.make_gate(tmpdir)

            def fake_run():
                self.assertFalse(report_path.exists())
                return subprocess.CompletedProcess([], 0, "", "")

            with patch.object(gate, "_run", side_effect=fake_run):
                result = gate.run()

        self.assertTrue(result.passed)
        self.assertEqual(result.metrics, {"exit_code": 0})
        self.assertIn("未解析到 JSON", result.detail)

    def test_new_report_generated_by_current_run_is_parsed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir, "reports", "test-results.json")
            report_path.parent.mkdir()
            report_path.write_text('{"stats":{"expected":99}}', encoding="utf-8")
            gate = self.make_gate(tmpdir)

            def fake_run():
                self.assertFalse(report_path.exists())
                report_path.write_text(
                    '{"stats":{"expected":2,"unexpected":0,"flaky":0}}',
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess([], 0, "", "")

            with patch.object(gate, "_run", side_effect=fake_run):
                result = gate.run()

        self.assertTrue(result.passed)
        self.assertEqual(result.metrics["total"], 2)
        self.assertEqual(result.metrics["passed"], 2)


if __name__ == "__main__":
    unittest.main()
