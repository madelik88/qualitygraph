from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "synthetic"


class SQLiteTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        self.database = directory / "investigation #1.db"
        self.exports = directory / "exports"
        shutil.copytree(EXAMPLE, self.exports)

    def command(self, *args, check=True):
        return subprocess.run(
            [sys.executable, str(ROOT / "qualitygraph.py"), *args],
            check=check,
            capture_output=True,
            text=True,
        )

    def import_snapshot(self):
        return json.loads(self.command("--import-db", self.database, self.exports).stdout)

    def report(self, *args):
        return self.command("--from-db", self.database, *args, "QC-017").stdout

    def test_same_report_and_selectable_history(self):
        csv_report = self.command(self.exports, "QC-017").stdout
        first = self.import_snapshot()
        self.assertTrue(first["created"])
        self.assertEqual(self.report(), csv_report)

        events = self.exports / "events.csv"
        with events.open("a", encoding="utf-8") as output:
            output.write("DEV-003,FG-010,Nuovo evento\n")
        second = self.import_snapshot()
        self.assertNotEqual(first["snapshot_id"], second["snapshot_id"])
        self.assertTrue(second["created"])
        latest_report = self.report()
        self.assertIn("DEV-003", latest_report)
        self.assertEqual(self.report("--snapshot", first["snapshot_id"]), csv_report)

        shutil.copyfile(EXAMPLE / "events.csv", events)
        self.assertEqual(
            self.import_snapshot(), {"snapshot_id": first["snapshot_id"], "created": False}
        )
        shutil.rmtree(self.exports)
        self.assertEqual(self.report(), latest_report)

    def test_concurrent_imports_share_one_snapshot(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(self.import_snapshot)
            second = executor.submit(self.import_snapshot)
            outcomes = [first.result(), second.result()]
        self.assertEqual(outcomes[0]["snapshot_id"], outcomes[1]["snapshot_id"])
        self.assertEqual(sorted(outcome["created"] for outcome in outcomes), [False, True])

    def test_invalid_import_does_not_change_existing_report(self):
        self.import_snapshot()
        before = self.report()
        with (self.exports / "events.csv").open("a", encoding="utf-8") as output:
            output.write("DEV-003,UNKNOWN,Evento non collegato\n")
        failure = self.command("--import-db", self.database, self.exports, check=False)
        self.assertEqual(failure.returncode, 2)
        self.assertIn("unknown batch", failure.stderr)
        self.assertEqual(self.report(), before)

    def test_write_failure_rolls_back_whole_snapshot(self):
        self.import_snapshot()
        before = self.report()
        with (self.exports / "events.csv").open("a", encoding="utf-8") as output:
            output.write("DEV-003,FG-010,Nuovo evento\n")
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("""
                CREATE TRIGGER reject_event BEFORE INSERT ON events
                BEGIN
                    SELECT RAISE(ABORT, 'simulated write failure');
                END
            """)
        failure = self.command("--import-db", self.database, self.exports, check=False)
        self.assertEqual(failure.returncode, 2)
        self.assertIn("simulated write failure", failure.stderr)
        self.assertEqual(self.report(), before)
        with closing(sqlite3.connect(self.database)) as connection:
            counts = connection.execute(
                "SELECT (SELECT COUNT(*) FROM snapshots), (SELECT COUNT(*) FROM sources)"
            ).fetchone()
        self.assertEqual(counts, (1, 4))

    def test_unrelated_database_is_not_overwritten(self):
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("CREATE TABLE unrelated (value TEXT)")
        original = self.database.read_bytes()
        failure = self.command("--import-db", self.database, self.exports, check=False)
        self.assertEqual(failure.returncode, 2)
        self.assertIn("Not a QualityGraph database", failure.stderr)
        self.assertEqual(self.database.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
