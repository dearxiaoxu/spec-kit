from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE_ROOT))

import pipeline
from gates.base import Gate, GateEnvironmentError, GateResult, GateSetupError, GateStatus, redact_sensitive
from gates.contract_diff import ContractDiffGate


class SetupMissingGate(Gate):
    name = "missing"

    def init(self):
        raise GateSetupError("missing tool")


class EnvironmentGate(Gate):
    name = "environment"

    def run(self):
        raise GateEnvironmentError("503 storm")


class SkippingGate(Gate):
    name = "skipping"

    def run(self):
        return GateResult(name=self.name, skipped=True)


class GovernanceTests(unittest.TestCase):
    def test_status_derives_legacy_flags(self):
        blocked = GateResult(name="x", status=GateStatus.BLOCKED)
        self.assertFalse(blocked.passed)
        self.assertTrue(blocked.blocking)
        skipped = GateResult(name="y", status=GateStatus.SKIP)
        self.assertTrue(skipped.passed)
        self.assertTrue(skipped.skipped)

    def test_required_setup_failure_is_config_error(self):
        config = {"gates": {"missing": {"required": True, "skip_policy": "fail"}}}
        self.assertEqual(pipeline.run_gate(SetupMissingGate, config).status, GateStatus.CONFIG_ERROR)

    def test_optional_setup_failure_is_skip(self):
        self.assertEqual(pipeline.run_gate(SetupMissingGate, {}).status, GateStatus.SKIP)

    def test_gate_returned_skip_obeys_fail_policy(self):
        config = {"gates": {"skipping": {"skip_policy": "fail"}}}
        self.assertEqual(pipeline.run_gate(SkippingGate, config).status, GateStatus.CONFIG_ERROR)

    def test_environment_error_maps_to_exit_four(self):
        with patch.object(pipeline, "ALL_GATES", [EnvironmentGate]), \
                patch.object(pipeline, "load_config", return_value={}), \
                patch.object(pipeline, "write_report"), \
                patch.object(sys, "argv", ["pipeline.py"]):
            self.assertEqual(pipeline.main(), 4)

    def test_contract_diff_marks_removed_endpoint_as_breaking(self):
        gate = ContractDiffGate({}, {})
        changes = gate._diff(
            {"endpoints": {"GET /old"}, "required_fields": set(), "enum_values": set()},
            {"endpoints": set(), "required_fields": set(), "enum_values": set()},
        )
        self.assertIn("removed_endpoint", changes[0])

    def test_module_coverage_gate_accepts_reviewed_fourteen_module_registry(self):
        config = {"project_root": str(PIPELINE_ROOT), "autotest_dir": str(PIPELINE_ROOT.parent / "spec-kit-autotest"),
                  "gates": {"contract_diff": {"module_registry": "assets/platform-modules.json"}}}
        gate = ContractDiffGate(config, {})
        gate.init()
        metrics, issues = gate._module_coverage(gate.module_registry)
        self.assertEqual(metrics["modules"], 14)
        self.assertEqual(metrics["module_missing"], 0)
        self.assertFalse(issues)

    def test_load_config_resolves_project_paths(self):
        config = pipeline.load_config()
        self.assertTrue(Path(config["project_root"]).is_absolute())
        self.assertTrue(Path(config["autotest_dir"]).is_absolute())
        self.assertTrue(Path(config["report_dir"]).is_absolute())
    def test_report_redaction_hides_credentials(self):
        value = redact_sensitive("password=secret token:abc Authorization=Bearer.xyz")
        self.assertNotIn("secret", value)
        self.assertNotIn("abc", value)
        self.assertNotIn("Bearer.xyz", value)

    def test_report_names_do_not_collide_within_same_second(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {"report_dir": tmpdir, "project_root": str(PIPELINE_ROOT), "run_id": "fixed-run"}
            first = pipeline.write_report([GateResult(name="a")], config)
            second = pipeline.write_report([GateResult(name="b")], config)
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
