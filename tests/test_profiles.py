import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from qualitygraph import investigate


ROOT = Path(__file__).resolve().parents[1]
PROFILED = ROOT / "examples" / "profiled"


class ProfileTests(unittest.TestCase):
    def run_cli(self, *args, check=True):
        return subprocess.run(
            [sys.executable, str(ROOT / "qualitygraph.py"), *args],
            text=True, capture_output=True, check=check,
        )

    def test_preview_and_import_preserve_evidence(self):
        profile = PROFILED / "profile.json"
        with TemporaryDirectory() as directory:
            database = Path(directory) / "qualitygraph.db"
            preview = json.loads(self.run_cli("--preview", "--profile", profile, PROFILED).stdout)
            self.assertTrue(preview["ready"])
            self.assertFalse(database.exists())
            self.assertIn({
                "file": "results.csv", "record": 3, "field": "batch_id",
                "source_batch": "L-001", "batch_id": "INT-001",
            }, preview["mapped_references"])
            imported = json.loads(self.run_cli(
                "--import-db", database, "--profile", profile, PROFILED,
            ).stdout)
            report = json.loads(self.run_cli(
                "--from-db", database, "--snapshot", imported["snapshot_id"], "QC-017",
            ).stdout)
            self.assertEqual(len(report.pop("input_sha256")["@profile"]), 64)
            expected = investigate(ROOT / "examples" / "synthetic", "QC-017")
            expected.pop("input_sha256")
            self.assertEqual(report, expected)

            revised = Path(directory) / "revised.json"
            configuration = json.loads(profile.read_text(encoding="utf-8"))
            configuration["files"]["results.csv"]["batch_aliases"]["L-001"] = "FG-010"
            revised.write_text(json.dumps(configuration), encoding="utf-8")
            second = json.loads(self.run_cli(
                "--import-db", database, "--profile", revised, PROFILED,
            ).stdout)
            self.assertNotEqual(imported["snapshot_id"], second["snapshot_id"])

    def test_ambiguity_blocks_import(self):
        with TemporaryDirectory() as directory:
            profile = Path(directory) / "ambiguous.json"
            configuration = json.loads((PROFILED / "profile.json").read_text(encoding="utf-8"))
            aliases = configuration["files"]["results.csv"]["batch_aliases"]
            aliases["FG-010"] = "INT-001"
            profile.write_text(json.dumps(configuration), encoding="utf-8")
            attempt = self.run_cli("--preview", "--profile", profile, PROFILED, check=False)
            self.assertEqual(attempt.returncode, 2)
            self.assertFalse(json.loads(attempt.stdout)["ready"])
            database = Path(directory) / "qualitygraph.db"
            attempt = self.run_cli("--import-db", database, "--profile", profile, PROFILED, check=False)
            self.assertEqual(attempt.returncode, 2)
            self.assertIn("Ambiguous batch", attempt.stderr)
            self.assertFalse(database.exists())


if __name__ == "__main__":
    unittest.main()
