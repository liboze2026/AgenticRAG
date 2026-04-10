import json
import os
import sqlite3
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExperimentService:
    """Persists experiment evaluation runs for later comparison."""

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
                CREATE TABLE IF NOT EXISTS experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    pipeline_config TEXT NOT NULL,
                    metrics TEXT NOT NULL,
                    total_queries INTEGER NOT NULL,
                    note TEXT DEFAULT '',
                    dataset_id INTEGER
                )
            """)
            cols = [r[1] for r in conn.execute("PRAGMA table_info(experiments)").fetchall()]
            if "dataset_id" not in cols:
                conn.execute("ALTER TABLE experiments ADD COLUMN dataset_id INTEGER")
            conn.commit()

    def record(
        self,
        pipeline_config: Dict[str, Any],
        metrics: Dict[str, Any],
        total_queries: int,
        note: str = "",
        dataset_id: Optional[int] = None,
    ) -> int:
        """Insert a new experiment record. Returns the new ID."""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO experiments (created_at, pipeline_config, metrics, total_queries, note, dataset_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    json.dumps(pipeline_config, ensure_ascii=False),
                    json.dumps(metrics, ensure_ascii=False),
                    total_queries,
                    note,
                    dataset_id,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def list_experiments(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, created_at, pipeline_config, metrics, total_queries, note, dataset_id "
                "FROM experiments ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_experiment(self, exp_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, created_at, pipeline_config, metrics, total_queries, note, dataset_id "
                "FROM experiments WHERE id = ?",
                (exp_id,),
            ).fetchone()
            return self._row_to_dict(row) if row else None

    def delete_experiment(self, exp_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM experiments WHERE id = ?", (exp_id,))
            conn.commit()
            return cursor.rowcount > 0

    def _row_to_dict(self, row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "pipeline_config": json.loads(row["pipeline_config"]),
            "metrics": json.loads(row["metrics"]),
            "total_queries": row["total_queries"],
            "note": row["note"],
            "dataset_id": row["dataset_id"] if "dataset_id" in row.keys() else None,
        }
