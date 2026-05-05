"""Run registry: SQLite primary + JSONL mirror.

Append-only audit trail. Idempotent metric upsert. Survives crashes;
re-running with the same config + git sha can be detected via the
config_json column.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, List

import aiosqlite

from backend.sota.error_envelope import ErrorKind, SotaError
from backend.sota.schemas import (
    MethodResult, MethodStatus, MetricCell, RunConfig, RunStatus, RunSummary,
)


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  created_at INTEGER NOT NULL,
  status TEXT NOT NULL,
  config_json TEXT NOT NULL,
  duration_ms INTEGER,
  notes TEXT
);
CREATE TABLE IF NOT EXISTS methods (
  run_id TEXT,
  method_name TEXT,
  status TEXT,
  duration_ms INTEGER,
  error_kind TEXT,
  PRIMARY KEY (run_id, method_name)
);
CREATE TABLE IF NOT EXISTS metrics (
  run_id TEXT,
  method_name TEXT,
  subset TEXT,
  metric TEXT,
  value REAL,
  ci_low REAL,
  ci_high REAL,
  n_queries INTEGER,
  PRIMARY KEY (run_id, method_name, subset, metric)
);
CREATE TABLE IF NOT EXISTS errors (
  run_id TEXT,
  method_name TEXT,
  query_id TEXT,
  kind TEXT,
  message TEXT,
  ts INTEGER
);
"""


class RunRegistry:
    """Single source of truth for SOTA run state."""

    def __init__(self, root: str):
        self.root = root
        os.makedirs(root, exist_ok=True)
        self.db_path = os.path.join(root, "runs.db")
        self._initialized = False

    async def _ensure_init(self) -> None:
        if self._initialized:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(_SCHEMA_SQL)
            await db.commit()
        self._initialized = True

    def _run_dir(self, run_id: str) -> str:
        d = os.path.join(self.root, run_id)
        os.makedirs(d, exist_ok=True)
        return d

    async def create_run(self, config: RunConfig) -> str:
        await self._ensure_init()
        run_id = uuid.uuid4().hex[:12]
        now = int(time.time() * 1000)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO runs (id, created_at, status, config_json, notes) VALUES (?, ?, ?, ?, ?)",
                (run_id, now, RunStatus.QUEUED.value, config.model_dump_json(), config.notes),
            )
            await db.commit()
        rd = self._run_dir(run_id)
        with open(os.path.join(rd, "config.json"), "w", encoding="utf-8") as f:
            json.dump(
                {"id": run_id, "created_at": now, "config": config.model_dump()},
                f, ensure_ascii=False, indent=2,
            )
        return run_id

    async def set_run_status(
        self, run_id: str, status: RunStatus, duration_ms: int | None = None,
    ) -> None:
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            if duration_ms is None:
                await db.execute(
                    "UPDATE runs SET status=? WHERE id=?",
                    (status.value, run_id),
                )
            else:
                await db.execute(
                    "UPDATE runs SET status=?, duration_ms=? WHERE id=?",
                    (status.value, duration_ms, run_id),
                )
            await db.commit()

    async def upsert_method_result(self, run_id: str, result: MethodResult) -> None:
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO methods (run_id, method_name, status, "
                "duration_ms, error_kind) VALUES (?, ?, ?, ?, ?)",
                (run_id, result.method, result.status.value,
                 result.duration_ms, result.error_kind),
            )
            await db.commit()

    async def append_metric(self, run_id: str, cell: MetricCell) -> None:
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO metrics "
                "(run_id, method_name, subset, metric, value, ci_low, ci_high, n_queries) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, cell.method, cell.subset, cell.metric,
                 cell.value, cell.ci_low, cell.ci_high, cell.n_queries),
            )
            await db.commit()

    async def append_error(
        self, run_id: str, method: str, query_id: str | None,
        kind: str, message: str,
    ) -> None:
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO errors (run_id, method_name, query_id, kind, message, ts) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, method, query_id, kind, message[:1000],
                 int(time.time() * 1000)),
            )
            await db.commit()
        with open(os.path.join(self._run_dir(run_id), "errors.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(
                {"method": method, "query_id": query_id,
                 "kind": kind, "message": message[:1000]},
                ensure_ascii=False,
            ) + "\n")

    async def append_query_trace(self, run_id: str, trace: Dict[str, Any]) -> None:
        with open(os.path.join(self._run_dir(run_id), "queries.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

    async def get_run(self, run_id: str) -> RunSummary:
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM runs WHERE id=?", (run_id,)) as cur:
                row = await cur.fetchone()
            if not row:
                raise SotaError(ErrorKind.RUN_NOT_FOUND, f"run {run_id} not found")
            async with db.execute(
                "SELECT * FROM methods WHERE run_id=?", (run_id,),
            ) as cur:
                m_rows = await cur.fetchall()
            async with db.execute(
                "SELECT * FROM metrics WHERE run_id=?", (run_id,),
            ) as cur:
                me_rows = await cur.fetchall()
        config = RunConfig.model_validate_json(row["config_json"])
        methods = [
            MethodResult(
                method=m["method_name"], status=MethodStatus(m["status"]),
                duration_ms=m["duration_ms"] or 0, error_kind=m["error_kind"],
            )
            for m in m_rows
        ]
        metrics = [
            MetricCell(
                method=me["method_name"], subset=me["subset"], metric=me["metric"],
                value=me["value"], ci_low=me["ci_low"], ci_high=me["ci_high"],
                n_queries=me["n_queries"],
            )
            for me in me_rows
        ]
        return RunSummary(
            id=row["id"], created_at=row["created_at"], status=RunStatus(row["status"]),
            config=config, duration_ms=row["duration_ms"],
            methods=methods, metrics=metrics, notes=row["notes"] or "",
        )

    async def list_runs(self, limit: int = 50) -> List[RunSummary]:
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id FROM runs ORDER BY created_at DESC LIMIT ?", (limit,),
            ) as cur:
                ids = [r["id"] for r in await cur.fetchall()]
        return [await self.get_run(rid) for rid in ids]
