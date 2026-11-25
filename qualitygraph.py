"""Build an evidence report for an out-of-specification result."""

import argparse
from collections import defaultdict, deque
import csv
from graphlib import CycleError, TopologicalSorter
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import sqlite3
from qualitygraph_profiles import load_profile, reconcile_batches
from qualitygraph_store import FILE_FIELDS, PROFILE_SOURCE, load_snapshot, save_snapshot


def read_table(path, fields, columns=None):
    snapshot = path.read_bytes()
    reader = csv.reader(StringIO(snapshot.decode("utf-8-sig"), newline=""), strict=True)
    headers = next(reader, [])
    if columns is None:
        if len(headers) != len(fields) or set(headers) != set(fields):
            raise ValueError(f"{path.name}: expected columns {', '.join(fields)}")
        positions = [(field, index) for index, field in enumerate(headers)]
    else:
        required = [columns.get(field, field) for field in fields]
        if len(set(required)) != len(required):
            raise ValueError(f"{path.name}: profile maps multiple fields to the same column")
        if len(set(headers)) != len(headers) or not set(required) <= set(headers):
            raise ValueError(f"{path.name}: expected unique columns including {', '.join(required)}")
        positions = [(field, headers.index(header)) for field, header in zip(fields, required)]

    rows = []
    for record, values in enumerate(reader, start=2):
        if len(values) != len(headers) or any(not values[index].strip() for _, index in positions):
            raise ValueError(f"{path.name}: invalid fields in record {record}")
        row = {field: values[index].strip() for field, index in positions}
        row["source"] = {"file": path.name, "record": record}
        rows.append(row)
    return rows, sha256(snapshot).hexdigest()


def index_by(rows, key):
    index = {}
    for row in rows:
        value = row[key]
        if value in index:
            raise ValueError(f"{row['source']}: duplicate {key} {value!r}")
        index[value] = row
    return index


def validate_batch(row, key, batches):
    if row[key] not in batches:
        raise ValueError(f"{row['source']}: unknown batch {row[key]!r}")


def walk(start, adjacency, target_key, batches):
    """Return one shortest evidence path per reachable batch."""
    previous = {start: None}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for edge in adjacency[current]:
            target = edge[target_key]
            if target in previous:
                continue
            previous[target] = edge
            queue.append(target)

    origin_key = "parent_batch" if target_key == "child_batch" else "child_batch"
    reached = []
    for batch_id in sorted(set(previous) - {start}):
        path = []
        current = batch_id
        while current != start:
            edge = previous[current]
            path.append(edge)
            current = edge[origin_key]
        reached.append({"batch": batches[batch_id], "path": path[::-1]})
    return reached


def load_csv(directory, profile=None):
    tables = {}
    digests = {}
    for filename, fields in FILE_FIELDS.items():
        settings = profile.get(filename, {}) if profile is not None else {}
        columns = settings.get("columns", {}) if profile is not None else None
        tables[filename], digests[filename] = read_table(directory / filename, fields, columns)
    return tables, digests


def index_snapshot(tables):
    batches = index_by(tables["batches.csv"], "batch_id")
    results = index_by(tables["results.csv"], "result_id")
    events = index_by(tables["events.csv"], "event_id")

    for batch in batches.values():
        if batch["coverage"] not in {"no_known_gap", "known_gap", "unknown"}:
            raise ValueError(f"{batch['source']}: invalid coverage")
    for row in results.values():
        validate_batch(row, "batch_id", batches)
        if row["status"] not in {"PASS", "OOS"}:
            raise ValueError(f"{row['source']}: expected status PASS or OOS")
    for row in events.values():
        validate_batch(row, "batch_id", batches)

    upstream = defaultdict(list)
    downstream = defaultdict(list)
    order = TopologicalSorter()
    for edge in tables["lineage.csv"]:
        validate_batch(edge, "parent_batch", batches)
        validate_batch(edge, "child_batch", batches)
        parent, child = edge["parent_batch"], edge["child_batch"]
        upstream[child].append(edge)
        downstream[parent].append(edge)
        order.add(child, parent)
    try:
        order.prepare()
    except CycleError as error:
        chain = " -> ".join(error.args[1])
        raise ValueError(f"lineage.csv: cycle in batch genealogy ({chain})") from error
    return batches, results, events, upstream, downstream


def build_report(tables, digests, result_id):
    batches, results, events, upstream, downstream = index_snapshot(tables)
    anchor = results.get(result_id)
    if anchor is None:
        raise ValueError(f"unknown result {result_id!r}")
    if anchor["status"] != "OOS":
        raise ValueError(f"result {result_id!r} has no OOS flag in the source data")

    origin = anchor["batch_id"]
    ancestors = walk(origin, upstream, "parent_batch", batches)
    descendants = walk(origin, downstream, "child_batch", batches)
    scope = {origin}
    scope.update(item["batch"]["batch_id"] for item in ancestors + descendants)
    return {
        "schema_version": 1,
        "input_sha256": digests,
        "trigger": anchor,
        "batch": batches[origin],
        "upstream": ancestors,
        "downstream": descendants,
        "results": [row for row in results.values() if row["batch_id"] in scope],
        "events": [row for row in events.values() if row["batch_id"] in scope],
        "coverage_warnings": [
            batches[batch_id] for batch_id in sorted(scope)
            if batches[batch_id]["coverage"] != "no_known_gap"
        ],
        "scope_note": "Observed lineage only. A path does not establish cause or disposition.",
    }


def investigate(directory, result_id):
    tables, digests = load_csv(directory)
    return build_report(tables, digests, result_id)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        usage=("%(prog)s DIRECTORY RESULT_ID\n"
               "       %(prog)s --import-db DATABASE [--profile FILE] DIRECTORY\n"
               "       %(prog)s --preview --profile FILE DIRECTORY\n"
               "       %(prog)s --from-db DATABASE [--snapshot ID] RESULT_ID"),
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--import-db", type=Path, metavar="DATABASE", help="Import validated CSVs")
    mode.add_argument("--from-db", type=Path, metavar="DATABASE", help="Investigate stored rows")
    mode.add_argument("--preview", action="store_true", help="Preview profile mappings without saving")
    parser.add_argument("--profile", type=Path, metavar="FILE", help="JSON import profile")
    parser.add_argument("--snapshot", metavar="ID", help="Select a stored import (default: latest)")
    parser.add_argument("source", metavar="DIRECTORY_OR_RESULT_ID")
    parser.add_argument("result_id", nargs="?")
    args = parser.parse_args()
    if args.snapshot is not None and args.from_db is None:
        parser.error("--snapshot requires --from-db")
    if args.preview and args.profile is None:
        parser.error("--preview requires --profile")
    if args.profile is not None and not (args.import_db or args.preview):
        parser.error("--profile requires --import-db or --preview")
    if (args.import_db or args.from_db or args.preview) and args.result_id is not None:
        parser.error("database modes accept exactly one positional argument")
    if not (args.import_db or args.from_db or args.preview) and args.result_id is None:
        parser.error("CSV investigation requires DIRECTORY and RESULT_ID")

    exit_code = 0
    try:
        if args.import_db or args.preview:
            profile = None
            if args.profile is not None:
                profile, profile_digest = load_profile(args.profile)
            tables, digests = load_csv(Path(args.source), profile)
            mappings, errors = [], []
            if profile is not None:
                digests[PROFILE_SOURCE] = profile_digest
                mappings, errors = reconcile_batches(tables, profile)
            if not errors:
                try:
                    index_snapshot(tables)
                except ValueError as error:
                    errors.append({"error": str(error)})
            if args.preview:
                output = {
                    "ready": not errors,
                    "rows": {filename: len(rows) for filename, rows in tables.items()},
                    "mapped_references": mappings,
                    "errors": errors,
                }
                exit_code = 2 if errors else 0
            else:
                if errors:
                    raise ValueError("; ".join(
                        f"{item['file']}: {item['error']}" if "file" in item else item["error"]
                        for item in errors
                    ))
                snapshot_id, created = save_snapshot(args.import_db, tables, digests)
                output = {"snapshot_id": snapshot_id, "created": created}
        elif args.from_db:
            tables, digests = load_snapshot(args.from_db, args.snapshot)
            output = build_report(tables, digests, args.source)
        else:
            output = investigate(Path(args.source), args.result_id)
    except (OSError, ValueError, csv.Error, sqlite3.Error) as error:
        parser.exit(2, f"qualitygraph: {error}\n")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
