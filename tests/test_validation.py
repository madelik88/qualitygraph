import csv
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from benchmark import edges_for
from qualitygraph import investigate


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


class ValidationTests(unittest.TestCase):
    def test_five_known_investigations(self):
        cases = [
            ("QC-017", ["RAW-100", "RAW-200"], ["FG-010", "FG-011"], ["FG-011"]),
            ("QC-RAW", [], ["FG-010", "FG-011", "FG-090", "INT-001"], ["FG-011"]),
            ("QC-FILL", ["INT-001", "RAW-100", "RAW-200"], ["FG-011"], ["FG-011"]),
            ("QC-GAP", ["FG-010", "INT-001", "RAW-100", "RAW-200"], [], ["FG-011"]),
            ("QC-ISO", [], [], []),
        ]
        with TemporaryDirectory() as temporary:
            exports = Path(temporary) / "exports"
            shutil.copytree(EXAMPLES / "synthetic", exports)
            with (EXAMPLES / "validation" / "results_extra.csv").open(
                encoding="utf-8", newline=""
            ) as extra, (exports / "results.csv").open(
                "a", encoding="utf-8", newline=""
            ) as results:
                rows = csv.reader(extra)
                next(rows)
                csv.writer(results).writerows(rows)
            for result, upstream, downstream, warnings in cases:
                with self.subTest(result=result):
                    report = investigate(exports, result)
                    self.assertEqual(
                        [item["batch"]["batch_id"] for item in report["upstream"]], upstream
                    )
                    self.assertEqual(
                        [item["batch"]["batch_id"] for item in report["downstream"]], downstream
                    )
                    self.assertEqual(
                        [item["batch_id"] for item in report["coverage_warnings"]], warnings
                    )

    def test_generator_produces_exact_unique_forward_edges(self):
        for topology, count in [("wide", 190), ("deep", 110)]:
            with self.subTest(topology=topology):
                edges = list(edges_for(20, count, topology))
                self.assertEqual(len(edges), count)
                self.assertEqual(len(set(edges)), count)
                self.assertTrue(all(0 <= parent < child < 20 for parent, child in edges))
                if topology == "deep":
                    self.assertEqual(
                        {parent for parent, child in edges if 1 <= child <= 5},
                        set(range(5)),
                    )


if __name__ == "__main__":
    unittest.main()
