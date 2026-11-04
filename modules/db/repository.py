import json
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Dict, List, Optional, Sequence

from modules.crypto.fingerprint import key_fingerprint
from modules.experiment.storage import to_json

SCHEMA = """
CREATE TABLE IF NOT EXISTS keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL UNIQUE,
    algorithm TEXT NOT NULL,
    key_size INTEGER NOT NULL,
    public_key TEXT NOT NULL,
    seed_hex TEXT NOT NULL,
    derived_seed_hex TEXT NOT NULL,
    ai TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    key_size INTEGER NOT NULL,
    key_id INTEGER NOT NULL,
    ai TEXT,
    doc_count INTEGER NOT NULL,
    package_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS signed_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    key_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    format TEXT,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    signature_hex TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_signed_batch ON signed_documents(batch_id);
CREATE TABLE IF NOT EXISTS verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_name TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    document_name TEXT,
    algorithm TEXT,
    sha256 TEXT,
    hash_match INTEGER,
    signature_valid INTEGER,
    key_registered INTEGER,
    key_id INTEGER,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    summary TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_results_kind ON results(kind);
"""


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _flag(value) -> Optional[int]:
    return None if value is None else int(bool(value))


class Repository:
    def __init__(self, path: str):
        self.path = path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def register_key(
        self,
        export,
        algorithm: str,
        key_size: int,
        seed_hex: str,
        derived_seed_hex: str,
        ai: Optional[str],
    ) -> int:
        fingerprint = key_fingerprint(export)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM keys WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
            if row:
                return int(row["id"])
            cursor = connection.execute(
                "INSERT INTO keys (fingerprint, algorithm, key_size, public_key, seed_hex, "
                "derived_seed_hex, ai, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    fingerprint,
                    algorithm,
                    int(key_size),
                    json.dumps(export),
                    seed_hex,
                    derived_seed_hex,
                    ai,
                    _now(),
                ),
            )
            return int(cursor.lastrowid)

    def find_key(self, fingerprint: str) -> Optional[dict]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM keys WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
        return dict(row) if row else None

    def list_keys(self, limit: int = 200) -> List[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, algorithm, key_size, ai, fingerprint, created_at "
                "FROM keys ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def add_batch(
        self,
        kind: str,
        algorithm: str,
        key_size: int,
        key_id: int,
        ai: Optional[str],
        doc_count: int,
        package_path: str,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO batches (kind, algorithm, key_size, key_id, ai, doc_count, "
                "package_path, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (kind, algorithm, int(key_size), key_id, ai, doc_count, package_path, _now()),
            )
            return int(cursor.lastrowid)

    def add_signed_documents(self, batch_id: int, key_id: int, rows: Sequence[dict]) -> None:
        created = _now()
        with self._connect() as connection:
            connection.executemany(
                "INSERT INTO signed_documents (batch_id, key_id, name, format, size_bytes, "
                "sha256, signature_hex, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        batch_id,
                        key_id,
                        r["name"],
                        r["format"],
                        r["size_bytes"],
                        r["sha256"],
                        r["signature_hex"],
                        created,
                    )
                    for r in rows
                ],
            )

    def list_batches(self, limit: int = 200) -> List[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM batches ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_batch(self, batch_id: int) -> Optional[dict]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
        return dict(row) if row else None

    def list_signed_documents(self, batch_id: int, limit: int = 500) -> List[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT name, format, size_bytes, sha256, substr(signature_hex, 1, 32) AS signature_preview "
                "FROM signed_documents WHERE batch_id = ? ORDER BY id LIMIT ?",
                (batch_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def add_verification(self, package_name: str, outcome: Dict) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO verifications (package_name, status, reason, document_name, "
                "algorithm, sha256, hash_match, signature_valid, key_registered, key_id, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    package_name,
                    outcome["status"],
                    outcome["reason"],
                    outcome.get("document_name"),
                    outcome.get("algorithm"),
                    outcome.get("sha256"),
                    _flag(outcome.get("hash_match")),
                    _flag(outcome.get("signature_valid")),
                    _flag(outcome.get("key_registered")),
                    outcome.get("key_id"),
                    _now(),
                ),
            )
            return int(cursor.lastrowid)

    def list_verifications(self, limit: int = 500) -> List[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM verifications ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def save_result(self, kind: str, payload: dict, summary: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO results (kind, summary, payload, created_at) VALUES (?, ?, ?, ?)",
                (kind, summary, to_json(payload), _now()),
            )
            return int(cursor.lastrowid)

    def list_results(self, kind: Optional[str] = None, limit: int = 200) -> List[dict]:
        query = "SELECT id, kind, summary, created_at FROM results"
        params: tuple = ()
        if kind:
            query += " WHERE kind = ?"
            params = (kind,)
        query += " ORDER BY id DESC LIMIT ?"
        with self._connect() as connection:
            rows = connection.execute(query, params + (limit,)).fetchall()
        return [dict(r) for r in rows]

    def load_result(self, result_id: int) -> Optional[dict]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM results WHERE id = ?", (result_id,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def latest_result(self, kind: str) -> Optional[dict]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM results WHERE kind = ? ORDER BY id DESC LIMIT 1", (kind,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def counts(self) -> Dict[str, int]:
        tables = ("keys", "batches", "signed_documents", "verifications", "results")
        with self._connect() as connection:
            return {
                t: int(connection.execute("SELECT COUNT(*) AS c FROM %s" % t).fetchone()["c"])
                for t in tables
            }