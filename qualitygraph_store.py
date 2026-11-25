"""Store validated imports and their source references in SQLite."""

from contextlib import closing
from hashlib import sha256
import json
import sqlite3


FILE_FIELDS = {
    "batches.csv": ("batch_id", "material", "coverage"),
    "lineage.csv": ("parent_batch", "child_batch", "operation_id"),
    "results.csv": ("result_id", "batch_id", "analyte", "value", "unit", "status"),
    "events.csv": ("event_id", "batch_id", "description"),
}
APPLICATION_ID = 0x51475246
SCHEMA_VERSION = 1


def ensure_schema(connection, create=False):
    app_id = connection.execute("PRAGMA application_id").fetchone()[0]
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if app_id == APPLICATION_ID:
        if version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported QualityGraph database schema {version}")
        return

    has_objects = connection.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()
    if not create or app_id != 0 or version != 0 or has_objects:
        raise ValueError("Not a QualityGraph database")

    connection.execute("""
        CREATE TABLE snapshots (
            id INTEGER PRIMARY KEY,
            fingerprint TEXT NOT NULL UNIQUE
        )
    """)
    connection.execute("""
        CREATE TABLE sources (
            snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
            filename TEXT NOT NULL,
            digest TEXT NOT NULL,
            PRIMARY KEY (snapshot_id, filename)
        )
    """)
    for filename, fields in FILE_FIELDS.items():
        table = filename.removesuffix(".csv")
        columns = ", ".join(f"{field} TEXT NOT NULL" for field in fields)
        connection.execute(f"""
            CREATE TABLE {table} (
                snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
                record INTEGER NOT NULL,
                {columns},
                PRIMARY KEY (snapshot_id, record)
            )
        """)
    connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def save_snapshot(database, tables, digests):
    manifest = json.dumps(digests, sort_keys=True, separators=(",", ":"))
    fingerprint = sha256(manifest.encode("utf-8")).hexdigest()

    with closing(sqlite3.connect(database)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        # Lock before looking up the fingerprint so concurrent imports deduplicate.
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            ensure_schema(connection, create=True)
            existing = connection.execute(
                "SELECT id FROM snapshots WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
            if existing is not None:
                return fingerprint, False

            cursor = connection.execute(
                "INSERT INTO snapshots (fingerprint) VALUES (?)", (fingerprint,)
            )
            snapshot = cursor.lastrowid
            connection.executemany(
                "INSERT INTO sources (snapshot_id, filename, digest) VALUES (?, ?, ?)",
                ((snapshot, filename, digest) for filename, digest in digests.items()),
            )
            for filename, fields in FILE_FIELDS.items():
                table = filename.removesuffix(".csv")
                columns = ", ".join(fields)
                placeholders = ", ".join("?" for _ in fields)
                rows = (
                    (snapshot, row["source"]["record"], *(row[field] for field in fields))
                    for row in tables[filename]
                )
                connection.executemany(
                    f"INSERT INTO {table} (snapshot_id, record, {columns}) "
                    f"VALUES (?, ?, {placeholders})",
                    rows,
                )
    return fingerprint, True


def load_snapshot(database, fingerprint=None):
    uri = database.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        # Keep selection and all reads on the same view of the database.
        with connection:
            connection.execute("BEGIN")
            ensure_schema(connection)
            if fingerprint is None:
                snapshot = connection.execute(
                    "SELECT id FROM snapshots ORDER BY id DESC LIMIT 1"
                ).fetchone()
            else:
                snapshot = connection.execute(
                    "SELECT id FROM snapshots WHERE fingerprint = ?", (fingerprint,)
                ).fetchone()
            if snapshot is None:
                if fingerprint is not None:
                    raise ValueError(f"Unknown snapshot {fingerprint!r}")
                raise ValueError("The QualityGraph database has no imports")

            stored_digests = dict(connection.execute(
                "SELECT filename, digest FROM sources WHERE snapshot_id = ?", snapshot
            ))
            if stored_digests.keys() != FILE_FIELDS.keys():
                raise ValueError("The snapshot is missing its complete source manifest")
            tables = {}
            digests = {}
            for filename, fields in FILE_FIELDS.items():
                digests[filename] = stored_digests[filename]
                table = filename.removesuffix(".csv")
                columns = ", ".join(fields)
                rows = connection.execute(
                    f"SELECT record, {columns} FROM {table} "
                    "WHERE snapshot_id = ? ORDER BY record",
                    snapshot,
                )
                tables[filename] = []
                for record, *values in rows:
                    row = dict(zip(fields, values))
                    row["source"] = {"file": filename, "record": record}
                    tables[filename].append(row)
    return tables, digests
