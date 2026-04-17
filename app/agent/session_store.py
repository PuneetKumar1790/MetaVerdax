"""Session and scan-result persistence for MetaVerdax Agent."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any

from pymongo import DESCENDING, MongoClient
from pymongo.collection import Collection

from app.config.settings import settings


@dataclass
class SessionMessage:
    role: str
    content: str
    timestamp: str


class SessionStore:
    """In-memory + SQLite session store with Mongo scan persistence."""

    def __init__(self, sqlite_path: str | None = None):
        self.sqlite_path = sqlite_path or settings.sqlite_path
        self._lock = Lock()
        self._mem: dict[str, list[dict[str, str]]] = {}
        self._mongo_client: MongoClient | None = None
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS session_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_session_messages_sid ON session_messages(session_id);
                """
            )
            conn.commit()

    def _mongo_collection(self) -> Collection:
        if not settings.mongodb_uri:
            raise RuntimeError("MONGODB_URI is not configured")
        if self._mongo_client is None:
            self._mongo_client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
            # Validate connectivity once.
            self._mongo_client.admin.command("ping")
        db = self._mongo_client[settings.mongodb_db]
        collection = db[settings.mongodb_scans_collection]
        collection.create_index([("timestamp", DESCENDING)])
        collection.create_index([("risk_level", DESCENDING), ("timestamp", DESCENDING)])
        return collection

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._mem[session_id] = []
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute("DELETE FROM session_messages WHERE session_id = ?", (session_id,))
            conn.commit()

    def add_message(self, session_id: str, role: str, content: str) -> None:
        payload = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        with self._lock:
            self._mem.setdefault(session_id, []).append(payload)

        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                "INSERT INTO session_messages(session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, role, content, payload["timestamp"]),
            )
            conn.commit()

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        with self._lock:
            mem_history = list(self._mem.get(session_id, []))
        if mem_history:
            return mem_history

        with sqlite3.connect(self.sqlite_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT role, content, timestamp FROM session_messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        history = [
            {"role": str(row["role"]), "content": str(row["content"]), "timestamp": str(row["timestamp"])}
            for row in rows
        ]
        with self._lock:
            self._mem[session_id] = history
        return history

    def save_scan_result(self, result: dict[str, Any]) -> str:
        collection = self._mongo_collection()
        doc = dict(result)
        doc.setdefault("timestamp", datetime.now(UTC).isoformat())
        insert_result = collection.insert_one(doc)
        return str(insert_result.inserted_id)

    def get_recent_scan_results(self, limit: int = 50) -> list[dict[str, Any]]:
        collection = self._mongo_collection()
        docs = list(collection.find({}, {"_id": 0}).sort("timestamp", DESCENDING).limit(limit))
        return [self._json_safe(doc) for doc in docs]

    def get_blocked_retrains_last_30_days(self) -> list[dict[str, Any]]:
        collection = self._mongo_collection()
        cutoff = datetime.now(UTC) - timedelta(days=30)
        docs = list(
            collection.find(
                {
                    "risk_level": {"$in": ["CRITICAL", "REVIEW"]},
                    "timestamp": {"$gte": cutoff.isoformat()},
                },
                {"_id": 0},
            ).sort("timestamp", DESCENDING)
        )
        return [self._json_safe(doc) for doc in docs]

    @staticmethod
    def _json_safe(doc: dict[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(doc, default=str))
