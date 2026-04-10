import os
import sqlite3
import logging
from datetime import datetime
from typing import List, Optional

from backend.models.schemas import DatasetInfo

logger = logging.getLogger(__name__)


class DatasetService:
    """Manage named document datasets for reproducible experiments."""

    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS datasets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def create(self, name: str, description: str = "") -> DatasetInfo:
        with self._connect() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO datasets (name, description, created_at) VALUES (?, ?, ?)",
                    (name, description, datetime.utcnow().isoformat(timespec="seconds") + "Z"),
                )
                conn.commit()
                ds_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                raise ValueError(f"Dataset '{name}' already exists")
        return self.get(ds_id)

    def get(self, ds_id: int) -> Optional[DatasetInfo]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, description, created_at FROM datasets WHERE id = ?", (ds_id,)
            ).fetchone()
            if not row:
                return None
            return DatasetInfo(
                id=row["id"], name=row["name"], description=row["description"],
                created_at=row["created_at"], document_count=0,
            )

    def list_all(self, document_counts: Optional[dict] = None) -> List[DatasetInfo]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, description, created_at FROM datasets ORDER BY id"
            ).fetchall()
        counts = document_counts or {}
        return [
            DatasetInfo(
                id=r["id"], name=r["name"], description=r["description"],
                created_at=r["created_at"], document_count=counts.get(r["id"], 0),
            )
            for r in rows
        ]

    def delete(self, ds_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM datasets WHERE id = ?", (ds_id,))
            conn.commit()
            return cursor.rowcount > 0
