"""Chat session persistence backed by SQLite."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from backend.models.schemas import ChatMessage, ChatSession


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatService:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id   TEXT PRIMARY KEY,
                    document_ids TEXT NOT NULL DEFAULT '[]',
                    messages     TEXT NOT NULL DEFAULT '[]',
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL
                )
            """)

    def create_session(self, document_ids: List[str] = []) -> ChatSession:
        sid = str(uuid.uuid4())
        now = _now()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                (sid, json.dumps(document_ids), "[]", now, now),
            )
        return ChatSession(
            session_id=sid,
            document_ids=document_ids,
            messages=[],
            created_at=now,
            updated_at=now,
        )

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_session(row)

    def append_message(self, session_id: str, message: ChatMessage) -> None:
        now = _now()
        message.timestamp = now
        with self._conn() as conn:
            row = conn.execute(
                "SELECT messages FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if not row:
                return
            msgs = json.loads(row["messages"])
            msgs.append(message.model_dump())
            conn.execute(
                "UPDATE sessions SET messages = ?, updated_at = ? WHERE session_id = ?",
                (json.dumps(msgs), now, session_id),
            )

    def update_document_scope(self, session_id: str, document_ids: List[str]) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE sessions SET document_ids = ?, updated_at = ? WHERE session_id = ?",
                (json.dumps(document_ids), _now(), session_id),
            )

    def delete_session(self, session_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    def list_sessions(self, limit: int = 50) -> List[ChatSession]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_session(r) for r in rows]

    def _row_to_session(self, row) -> ChatSession:
        messages = []
        for m in json.loads(row["messages"]):
            try:
                messages.append(ChatMessage(**m))
            except Exception:
                pass
        return ChatSession(
            session_id=row["session_id"],
            document_ids=json.loads(row["document_ids"]),
            messages=messages,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
