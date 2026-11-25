"""Build an evidence report for an out-of-specification result."""

import argparse
from collections import defaultdict, deque
import csv
from graphlib import CycleError, TopologicalSorter
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path


SCHEMA = {
    "batches.csv": ("batch_id", "material", "coverage"),
    "lineage.csv": ("parent_batch", "child_batch", "operation_id"),
    "results.csv": ("result_id", "batch_id", "analyte", "value", "unit", "status"),
    "events.csv": ("event_id", "batch_id", "description"),
}


def read_table(path, fields):
    snapshot = path.read_bytes()
    reader = csv.reader(StringIO(snapshot.decode("utf-8-sig"), newline=""), strict=True)
    headers = next(reader, [])
    if len(headers) != len(fields) or set(headers) != set(fields):
        raise ValueError(f"{path.name}: expected columns {', '.join(fields)}")

    rows = []
    for record, values in enumerate(reader, start=2):
        if len(values) != len(headers) or any(not value.strip() for value in values):
            raise ValueError(f"{path.name}: invalid fields in record {record}")
        row = dict(zip(headers, (value.strip() for value in values)))
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


def investigate(directory, result_id):
    tables = {}
    digests = {}
    for filename, fields in SCHEMA.items():
        tables[filename], digests[filename] = read_table(directory / filename, fields)

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Directory with the four CSV exports")
    parser.add_argument("result_id", help="Identifier of the OOS result")
    args = parser.parse_args()
    try:
        report = investigate(args.directory, args.result_id)
    except (OSError, ValueError, csv.Error) as error:
        parser.exit(2, f"qualitygraph: {error}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
