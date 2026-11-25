"""Benchmark synthetic SQLite imports and QualityGraph page generation."""

import argparse
import csv
from itertools import islice
import json
from pathlib import Path
import platform
import resource
from statistics import median
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from urllib.parse import urlencode

from qualitygraph import build_report, index_snapshot, load_csv
from qualitygraph_store import list_snapshots, load_snapshot, save_snapshot
from qualitygraph_web import QualityGraphServer, render_page


def write_csv(directory, name, headers, rows):
    with (directory / name).open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)


def batch_id(index):
    return f"B-{index:06d}"


def edges_for(size, count, topology):
    spine = min(256, size // 4, count) if topology == "deep" else 0
    if count > spine + (size - spine) * (size - spine - 1) // 2:
        raise ValueError("Too many relations for this topology and batch count")

    # Keep the chain attached to the origin and the other component reachable
    # through a separate branch when enough relations are requested.
    def candidates():
        for child in range(1, spine + 1):
            yield (0 if child == 1 else child - 1), child

        first = spine + 1
        if first < size:
            yield 0, first

        last = size - spine
        powers = {1 << bit for bit in range(last.bit_length())}
        for offsets in (sorted(powers), (d for d in range(1, last) if d not in powers)):
            for offset in offsets:
                for parent in range(first, size - offset):
                    yield parent, parent + offset

        for child in range(first + 1, size):
            yield 0, child

    return islice(candidates(), count)


def generate(directory, size, count, topology):
    write_csv(
        directory, "batches.csv", ("batch_id", "material", "coverage"),
        ((batch_id(i), "Materiale sintetico", "known_gap" if i == 1 else "no_known_gap")
         for i in range(size)),
    )
    write_csv(
        directory, "lineage.csv", ("parent_batch", "child_batch", "operation_id"),
        ((batch_id(parent), batch_id(child), f"OP-{i}")
         for i, (parent, child) in enumerate(edges_for(size, count, topology), start=1)),
    )
    write_csv(
        directory, "results.csv", ("result_id", "batch_id", "analyte", "value", "unit", "status"),
        [("QC-BENCH", batch_id(0), "Viscosity", "640", "mPa·s", "OOS")],
    )
    write_csv(directory, "events.csv", ("event_id", "batch_id", "description"), [])


def measure(phase, directory):
    database = directory / "benchmark.db"
    start = perf_counter()
    details = {}
    if phase == "import":
        tables, digests = load_csv(directory)
        index_snapshot(tables)
        save_snapshot(database, tables, digests)
    else:
        snapshots = list_snapshots(database)
        fingerprint = snapshots[0][1]
        tables, digests = load_snapshot(database, fingerprint)
        report = build_report(tables, digests, "QC-BENCH")
        page = render_page(
            snapshots, fingerprint, tables["results.csv"], "QC-BENCH", report
        ).encode("utf-8")
        details = {
            "html_bytes": len(page),
            "downstream_batches": len(report["downstream"]),
            "coverage_warnings": len(report["coverage_warnings"]),
        }
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        peak *= 1024
    return {
        "seconds": round(perf_counter() - start, 4),
        "peak_rss_bytes": peak,
        **details,
    }


def worker(phase, directory):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--worker", phase, str(directory)],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batches", type=int, default=10_000)
    parser.add_argument("--relations", type=int, default=100_000)
    parser.add_argument("--topology", choices=["wide", "deep"], default="wide")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--serve", action="store_true", help="Open a local browser benchmark on port 8766")
    parser.add_argument("--worker", choices=["import", "page"], help=argparse.SUPPRESS)
    parser.add_argument("directory", nargs="?", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(measure(args.worker, args.directory)))
        return
    if args.batches < 2 or args.relations < 1 or args.runs < 1:
        parser.error("Use at least two batches, one relation and one run")

    with TemporaryDirectory(prefix="qualitygraph-bench-") as temporary:
        directory = Path(temporary)
        try:
            generate(directory, args.batches, args.relations, args.topology)
            imported = worker("import", directory)
            if args.serve:
                database = directory / "benchmark.db"
                snapshot = list_snapshots(database)[0][1]
                query = urlencode({"snapshot": snapshot, "result": "QC-BENCH"})
                with QualityGraphServer(database, 8766) as server:
                    print(f"QualityGraph: http://127.0.0.1:8766/?{query}", flush=True)
                    try:
                        server.serve_forever()
                    except KeyboardInterrupt:
                        return
            samples = [worker("page", directory) for _ in range(args.runs)]
        except (OSError, ValueError) as error:
            parser.error(str(error))
        except subprocess.CalledProcessError as error:
            parser.exit(2, error.stderr)

    page_time = median(sample["seconds"] for sample in samples)
    peak = max(sample["peak_rss_bytes"] for sample in [imported, *samples])
    print(json.dumps({
        "platform": platform.platform(),
        "python": platform.python_version(),
        "batches": args.batches,
        "relations": args.relations,
        "topology": args.topology,
        "import": imported,
        "page_samples": samples,
        "page_median_seconds": page_time,
        "peak_rss_bytes": peak,
        "targets": {"page_under_2_seconds": page_time < 2, "peak_under_1_gb": peak < 10**9},
    }, indent=2))


if __name__ == "__main__":
    main()
