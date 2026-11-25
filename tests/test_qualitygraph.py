import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from qualitygraph import investigate


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "synthetic"


class InvestigationTests(unittest.TestCase):
    def test_end_to_end_demo(self):
        process = subprocess.run(
            [sys.executable, str(ROOT / "qualitygraph.py"), str(EXAMPLE), "QC-017"],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(process.stdout)
        self.assertEqual(
            [item["batch"]["batch_id"] for item in report["upstream"]],
            ["RAW-100", "RAW-200"],
        )
        downstream = report["downstream"]
        self.assertEqual(
            [item["batch"]["batch_id"] for item in downstream],
            ["FG-010", "FG-011"],
        )
        self.assertEqual(
            [edge["source"]["record"] for edge in downstream[1]["path"]],
            [4, 5],
        )
        self.assertEqual([row["event_id"] for row in report["events"]], ["DEV-001", "DEV-002"])
        self.assertEqual(
            [row["batch_id"] for row in report["coverage_warnings"]], ["FG-011"]
        )
        self.assertEqual(len(report["input_sha256"]["lineage.csv"]), 64)

    def test_pass_result_does_not_trigger_investigation(self):
        with self.assertRaisesRegex(ValueError, "no OOS flag"):
            investigate(EXAMPLE, "QC-001")

    def test_invalid_genealogy_is_rejected(self):
        cases = [
            ("FG-011,RAW-100,BAD-01\n", "cycle"),
            ("UNKNOWN,FG-011,BAD-02\n", "unknown batch"),
        ]
        for edge, error in cases:
            with self.subTest(edge=edge), TemporaryDirectory() as temporary:
                directory = Path(temporary) / "exports"
                shutil.copytree(EXAMPLE, directory)
                with (directory / "lineage.csv").open("a", encoding="utf-8") as lineage:
                    lineage.write(edge)
                with self.assertRaisesRegex(ValueError, error):
                    investigate(directory, "QC-017")


if __name__ == "__main__":
    unittest.main()
