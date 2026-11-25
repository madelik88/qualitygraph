"""Explicit mappings for importing CSV exports with different conventions."""

from hashlib import sha256
import json

from qualitygraph_store import FILE_FIELDS

BATCH_FIELDS = {
    "lineage.csv": ("parent_batch", "child_batch"),
    "results.csv": ("batch_id",),
    "events.csv": ("batch_id",),
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Profile contains duplicate key {key!r}")
        result[key] = value
    return result


def load_profile(path):
    raw = path.read_bytes()
    profile = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object)
    if not isinstance(profile, dict) or set(profile) != {"version", "files"}:
        raise ValueError("Expected profile keys version and files")
    if type(profile["version"]) is not int or profile["version"] != 1:
        raise ValueError("Unsupported import profile version")
    files = profile["files"]
    if not isinstance(files, dict) or not files.keys() <= FILE_FIELDS.keys():
        raise ValueError("Profile contains invalid file names")
    for filename, settings in files.items():
        if not isinstance(settings, dict) or not settings.keys() <= {"columns", "batch_aliases"}:
            raise ValueError(f"{filename}: invalid profile settings")
        columns = settings.get("columns", {})
        aliases = settings.get("batch_aliases", {})
        if not isinstance(columns, dict) or not columns.keys() <= set(FILE_FIELDS[filename]):
            raise ValueError(f"{filename}: invalid canonical columns")
        if not isinstance(aliases, dict) or ("batch_aliases" in settings and filename not in BATCH_FIELDS):
            raise ValueError(f"{filename}: aliases are allowed only for batch references")
        names = [*columns.values(), *aliases.keys(), *aliases.values()]
        if any(not isinstance(value, str) or not value or value != value.strip()
               for value in names):
            raise ValueError(f"{filename}: mappings must use nonempty strings without surrounding spaces")
    return files, sha256(raw).hexdigest()


def reconcile_batches(tables, profile):
    canonical = {row["batch_id"] for row in tables["batches.csv"]}
    mapped = []
    errors = []
    for filename, fields in BATCH_FIELDS.items():
        aliases = profile.get(filename, {}).get("batch_aliases", {})
        invalid = set()
        for source, target in aliases.items():
            if source in canonical and source != target:
                errors.append({"file": filename, "error": f"Ambiguous batch {source!r}: both canonical and alias for {target!r}"})
                invalid.add(source)
            elif target not in canonical:
                errors.append({"file": filename, "error": f"Alias {source!r} targets unknown batch {target!r}"})
                invalid.add(source)
        for row in tables[filename]:
            for field in fields:
                source = row[field]
                target = aliases.get(source, source)
                reference = {**row["source"], "field": field, "source_batch": source}
                if source in invalid or target not in canonical:
                    errors.append({**reference, "error": f"Unresolved batch {source!r}"})
                elif target != source:
                    row[field] = target
                    mapped.append({**reference, "batch_id": target})
    return mapped, errors
