from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PIPELINE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE_ROOT))

from gates.base import GateSetupError
from gates.mutation_check import mutation_rate_from_output, mutation_rate_from_report


class MutationScoreParsingTests(unittest.TestCase):
    def test_reads_current_stryker_json_statuses(self):
        report = {
            "files": {
                "a.js": {
                    "mutants": [
                        {"status": "Killed"},
                        {"status": "Timeout"},
                        {"status": "Survived"},
                        {"status": "NoCoverage"},
                    ]
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "mutation.json")
            path.write_text(json.dumps(report), encoding="utf-8")
            self.assertEqual(mutation_rate_from_report(str(path)), 0.5)

    def test_missing_report_allows_console_fallback(self):
        self.assertIsNone(mutation_rate_from_report("/definitely/missing/mutation.json"))

    def test_empty_report_is_configuration_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "mutation.json")
            path.write_text('{"files": {}}', encoding="utf-8")
            with self.assertRaises(GateSetupError):
                mutation_rate_from_report(str(path))

    def test_reads_current_console_format(self):
        self.assertEqual(mutation_rate_from_output("Final mutation score 54.60 under breaking threshold 70"), 0.546)

    def test_reads_legacy_console_format(self):
        self.assertEqual(mutation_rate_from_output("70.00% mutation score"), 0.7)

    def test_unrecognized_output_returns_none(self):
        self.assertIsNone(mutation_rate_from_output("Stryker finished"))


if __name__ == "__main__":
    unittest.main()
