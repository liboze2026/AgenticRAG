# VisDoMBench SOTA — Phase 0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a parallel `backend/sota/` package + new "SOTA 实验" frontend sidebar group; ship 3 retrieval baselines (ColPali, BM25, RRF) wired to a fully-isolated run registry; verify on a 50-query/subset slice of VisDoMBench.

**Architecture:** New independent FastAPI router at `/api/sota/*`. Read-only references to existing `lab` services for BM25/region. Runs persist to `data/sota_runs/` (SQLite + JSONL append-only). Frontend adds one sidebar group + 5 views. Existing `/api/lab/*` and `/api/query` paths are not touched.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, aiosqlite, Vue 3 + Vite, existing Qdrant/ColPali worker, existing pytest harness.

---

## File Structure

**Backend — create:**
- `backend/sota/__init__.py`
- `backend/sota/schemas.py` — Pydantic models (request/response shapes + RunStatus enum)
- `backend/sota/runs.py` — SQLite + JSONL run registry DAO
- `backend/sota/eval.py` — Recall@1/@3, MRR, Hit@1, bootstrap CI
- `backend/sota/datasets.py` — VisDoM 4-subset metadata loader + integrity check
- `backend/sota/indexers.py` — BaseIndexer + ColPaliIndexer (reuses worker) + BM25Indexer (reuses lab)
- `backend/sota/methods/__init__.py` — registry pattern
- `backend/sota/methods/baseline_colpali.py`
- `backend/sota/methods/baseline_bm25.py`
- `backend/sota/methods/baseline_rrf.py`
- `backend/sota/executor.py` — background-task runner orchestrating dataset × method
- `backend/sota/service.py` — DI container; held on `app.state.sota_bundle`
- `backend/sota/routes.py` — HTTP endpoints, all 200-wrapped
- `backend/sota/error_envelope.py` — `wrap_response` decorator + standard error kinds

**Backend — modify:**
- `backend/main.py:9-11` — import sota router
- `backend/main.py:75` — `app.include_router(sota_router, prefix="/api/sota")`
- `backend/main.py:46` — add `sota_bundle=None` parameter to `create_app`
- `backend/main.py:67` — `app.state.sota_bundle = sota_bundle`
- `run.py` — build sota bundle at startup, pass into `create_app`

**Frontend — create:**
- `frontend/src/views/sota/SotaDatasetsView.vue`
- `frontend/src/views/sota/SotaMethodsView.vue`
- `frontend/src/views/sota/SotaRunStudioView.vue`
- `frontend/src/views/sota/SotaLeaderboardView.vue`
- `frontend/src/views/sota/SotaRunDetailView.vue`
- `frontend/src/components/sota/RecallTable.vue`
- `frontend/src/components/sota/MethodCard.vue`
- `frontend/src/components/sota/RunProgress.vue`
- `frontend/src/components/sota/QueryTrace.vue`
- `frontend/src/api/sota.ts` — typed client for `/api/sota/*`

**Frontend — modify:**
- `frontend/src/router/index.ts` — append 5 sota routes
- `frontend/src/layout/SideBar.vue:54` — append `{ label: 'SOTA 实验', items: [...] }` group

**Tests — create:**
- `tests/sota/test_runs.py`
- `tests/sota/test_eval.py`
- `tests/sota/test_error_envelope.py`
- `tests/sota/test_routes_smoke.py`
- `tests/sota/test_methods_baselines.py`

---

## Task 1: Error Envelope

**Files:**
- Create: `backend/sota/error_envelope.py`
- Test: `tests/sota/test_error_envelope.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/sota/test_error_envelope.py
import pytest
from backend.sota.error_envelope import wrap_response, ErrorKind


@pytest.mark.asyncio
async def test_wrap_response_passes_through_ok_dict():
    @wrap_response
    async def handler():
        return {"ok": True, "data": 42}

    resp = await handler()
    assert resp == {"ok": True, "data": 42}


@pytest.mark.asyncio
async def test_wrap_response_catches_exception_returns_200_envelope():
    @wrap_response
    async def handler():
        raise ValueError("bad")

    resp = await handler()
    assert resp["ok"] is False
    assert resp["error_kind"] == ErrorKind.UNEXPECTED.value
    assert "bad" in resp["message"]


@pytest.mark.asyncio
async def test_wrap_response_known_error_kind_preserved():
    from backend.sota.error_envelope import SotaError

    @wrap_response
    async def handler():
        raise SotaError(ErrorKind.DATASET_MISSING, "fetatab not on disk")

    resp = await handler()
    assert resp["ok"] is False
    assert resp["error_kind"] == "dataset_missing"
    assert resp["message"] == "fetatab not on disk"
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/sota/test_error_envelope.py -v
```
Expected: FAIL — `ModuleNotFoundError: backend.sota.error_envelope`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/sota/error_envelope.py
"""Error envelope: every /api/sota/* handler returns HTTP 200 with
{ok, error_kind?, message?}. Frontend never blanks on backend errors.
"""
from __future__ import annotations

import enum
import functools
import logging
import traceback
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ErrorKind(str, enum.Enum):
    UNEXPECTED = "unexpected"
    DATASET_MISSING = "dataset_missing"
    DATASET_INTEGRITY = "dataset_integrity"
    INDEX_BUILD_FAILED = "index_build_failed"
    METHOD_FAILED = "method_failed"
    METHOD_TIMEOUT = "method_timeout"
    RUN_NOT_FOUND = "run_not_found"
    INVALID_CONFIG = "invalid_config"
    WORKER_OFFLINE = "worker_offline"
    CIRCUIT_OPEN = "circuit_open"
    ACADEMIC_INTEGRITY = "academic_integrity"


class SotaError(Exception):
    def __init__(self, kind: ErrorKind, message: str):
        self.kind = kind
        self.message = message
        super().__init__(message)


def wrap_response(fn: Callable) -> Callable:
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            return await fn(*args, **kwargs)
        except SotaError as e:
            logger.warning("[sota] %s: %s", e.kind.value, e.message)
            return {"ok": False, "error_kind": e.kind.value, "message": e.message}
        except Exception as e:
            logger.exception("[sota] unexpected error in %s", fn.__name__)
            return {
                "ok": False,
                "error_kind": ErrorKind.UNEXPECTED.value,
                "message": f"{type(e).__name__}: {e}"[:500],
                "trace": traceback.format_exc()[-2000:],
            }
    return wrapper
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/sota/test_error_envelope.py -v
```
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/sota/__init__.py backend/sota/error_envelope.py tests/sota/test_error_envelope.py
git commit -m "feat(sota): error envelope decorator + ErrorKind enum"
```

---

## Task 2: Run Registry (SQLite + JSONL)

**Files:**
- Create: `backend/sota/schemas.py`
- Create: `backend/sota/runs.py`
- Test: `tests/sota/test_runs.py`

- [ ] **Step 1: Write Pydantic schemas**

```python
# backend/sota/schemas.py
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MethodStatus(str, Enum):
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    CIRCUIT_OPEN = "circuit_open"


class RunConfig(BaseModel):
    subsets: List[str] = Field(default_factory=lambda: ["fetatab", "mmlongbench", "papertab", "slidevqa"])
    methods: List[str] = Field(default_factory=lambda: ["baseline_colpali", "baseline_bm25", "baseline_rrf"])
    top_k: int = Field(10, ge=1, le=50)
    n_queries_per_subset: Optional[int] = Field(50, ge=1, le=10000)  # None = full split
    split: Literal["test"] = "test"
    notes: str = ""


class MetricCell(BaseModel):
    method: str
    subset: str
    metric: str  # "recall@1" | "recall@3" | "mrr" | "hit@1"
    value: float
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    n_queries: int


class MethodResult(BaseModel):
    method: str
    status: MethodStatus
    duration_ms: int
    error_kind: Optional[str] = None


class RunSummary(BaseModel):
    id: str
    created_at: int
    status: RunStatus
    config: RunConfig
    duration_ms: Optional[int] = None
    methods: List[MethodResult] = Field(default_factory=list)
    metrics: List[MetricCell] = Field(default_factory=list)
    notes: str = ""
```

- [ ] **Step 2: Write the failing test**

```python
# tests/sota/test_runs.py
import asyncio
import os
import tempfile

import pytest

from backend.sota.runs import RunRegistry
from backend.sota.schemas import (
    MethodResult, MethodStatus, MetricCell, RunConfig, RunStatus,
)


@pytest.fixture
def tmp_registry(tmp_path):
    return RunRegistry(root=str(tmp_path))


@pytest.mark.asyncio
async def test_create_run_returns_uuid_and_persists(tmp_registry):
    cfg = RunConfig(subsets=["fetatab"], methods=["baseline_colpali"], n_queries_per_subset=10)
    run_id = await tmp_registry.create_run(cfg)
    assert run_id

    summary = await tmp_registry.get_run(run_id)
    assert summary.id == run_id
    assert summary.status == RunStatus.QUEUED
    assert summary.config.subsets == ["fetatab"]


@pytest.mark.asyncio
async def test_append_metric_and_method_status(tmp_registry):
    cfg = RunConfig(subsets=["fetatab"], methods=["baseline_colpali"], n_queries_per_subset=10)
    run_id = await tmp_registry.create_run(cfg)

    await tmp_registry.set_run_status(run_id, RunStatus.RUNNING)
    await tmp_registry.append_metric(run_id, MetricCell(
        method="baseline_colpali", subset="fetatab",
        metric="recall@1", value=0.82, n_queries=10,
    ))
    await tmp_registry.upsert_method_result(run_id, MethodResult(
        method="baseline_colpali", status=MethodStatus.OK, duration_ms=1500,
    ))

    summary = await tmp_registry.get_run(run_id)
    assert summary.status == RunStatus.RUNNING
    assert len(summary.metrics) == 1
    assert summary.metrics[0].value == pytest.approx(0.82)
    assert summary.methods[0].status == MethodStatus.OK


@pytest.mark.asyncio
async def test_list_runs_orders_by_created_at_desc(tmp_registry):
    cfg = RunConfig(n_queries_per_subset=10)
    a = await tmp_registry.create_run(cfg)
    await asyncio.sleep(0.01)
    b = await tmp_registry.create_run(cfg)
    rows = await tmp_registry.list_runs(limit=10)
    assert rows[0].id == b
    assert rows[1].id == a


@pytest.mark.asyncio
async def test_jsonl_mirror_appends_each_event(tmp_registry, tmp_path):
    cfg = RunConfig(n_queries_per_subset=10)
    run_id = await tmp_registry.create_run(cfg)
    await tmp_registry.append_query_trace(run_id, {"query_id": "q1", "method": "baseline_colpali", "rr": 1.0})
    await tmp_registry.append_query_trace(run_id, {"query_id": "q2", "method": "baseline_colpali", "rr": 0.5})

    queries_path = os.path.join(str(tmp_path), run_id, "queries.jsonl")
    assert os.path.exists(queries_path)
    with open(queries_path) as f:
        lines = f.readlines()
    assert len(lines) == 2
    assert "q1" in lines[0]


@pytest.mark.asyncio
async def test_run_not_found_raises(tmp_registry):
    from backend.sota.error_envelope import SotaError
    with pytest.raises(SotaError):
        await tmp_registry.get_run("does-not-exist")
```

- [ ] **Step 3: Run test to verify it fails**

```
pytest tests/sota/test_runs.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 4: Write implementation**

```python
# backend/sota/runs.py
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
        # mirror config to JSONL dir
        rd = self._run_dir(run_id)
        with open(os.path.join(rd, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"id": run_id, "created_at": now, "config": config.model_dump()}, f, ensure_ascii=False, indent=2)
        return run_id

    async def set_run_status(self, run_id: str, status: RunStatus, duration_ms: int | None = None) -> None:
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            if duration_ms is None:
                await db.execute("UPDATE runs SET status=? WHERE id=?", (status.value, run_id))
            else:
                await db.execute("UPDATE runs SET status=?, duration_ms=? WHERE id=?", (status.value, duration_ms, run_id))
            await db.commit()

    async def upsert_method_result(self, run_id: str, result: MethodResult) -> None:
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO methods (run_id, method_name, status, duration_ms, error_kind) VALUES (?, ?, ?, ?, ?)",
                (run_id, result.method, result.status.value, result.duration_ms, result.error_kind),
            )
            await db.commit()

    async def append_metric(self, run_id: str, cell: MetricCell) -> None:
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO metrics (run_id, method_name, subset, metric, value, ci_low, ci_high, n_queries) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, cell.method, cell.subset, cell.metric, cell.value, cell.ci_low, cell.ci_high, cell.n_queries),
            )
            await db.commit()

    async def append_error(self, run_id: str, method: str, query_id: str | None, kind: str, message: str) -> None:
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO errors (run_id, method_name, query_id, kind, message, ts) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, method, query_id, kind, message[:1000], int(time.time() * 1000)),
            )
            await db.commit()
        # JSONL mirror
        with open(os.path.join(self._run_dir(run_id), "errors.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"method": method, "query_id": query_id, "kind": kind, "message": message[:1000]}, ensure_ascii=False) + "\n")

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
            async with db.execute("SELECT * FROM methods WHERE run_id=?", (run_id,)) as cur:
                m_rows = await cur.fetchall()
            async with db.execute("SELECT * FROM metrics WHERE run_id=?", (run_id,)) as cur:
                me_rows = await cur.fetchall()
        config = RunConfig.model_validate_json(row["config_json"])
        methods = [
            MethodResult(method=m["method_name"], status=MethodStatus(m["status"]),
                         duration_ms=m["duration_ms"] or 0, error_kind=m["error_kind"])
            for m in m_rows
        ]
        metrics = [
            MetricCell(method=me["method_name"], subset=me["subset"], metric=me["metric"],
                       value=me["value"], ci_low=me["ci_low"], ci_high=me["ci_high"],
                       n_queries=me["n_queries"])
            for me in me_rows
        ]
        return RunSummary(
            id=row["id"], created_at=row["created_at"], status=RunStatus(row["status"]),
            config=config, duration_ms=row["duration_ms"], methods=methods, metrics=metrics,
            notes=row["notes"] or "",
        )

    async def list_runs(self, limit: int = 50) -> List[RunSummary]:
        await self._ensure_init()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT id FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)) as cur:
                ids = [r["id"] for r in await cur.fetchall()]
        return [await self.get_run(rid) for rid in ids]
```

- [ ] **Step 5: Run test to verify it passes**

```
pytest tests/sota/test_runs.py -v
```
Expected: 5 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/sota/schemas.py backend/sota/runs.py tests/sota/test_runs.py
git commit -m "feat(sota): SQLite+JSONL run registry with academic-integrity-friendly schema"
```

---

## Task 3: Eval Module (Recall@1/@3, MRR, bootstrap CI)

**Files:**
- Create: `backend/sota/eval.py`
- Test: `tests/sota/test_eval.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/sota/test_eval.py
import math
import pytest

from backend.sota.eval import (
    PerQueryResult, aggregate_metrics, score_query, bootstrap_ci,
)


def test_score_query_hit_at_1():
    # gold = (doc_a, page 3); ranked top = (doc_a, page 3) — perfect
    r = score_query(
        gold_pages=[("doc_a", 3)],
        ranked_pages=[("doc_a", 3), ("doc_a", 5), ("doc_b", 1)],
    )
    assert r.hit_at_1 == 1.0
    assert r.hit_at_3 == 1.0
    assert r.rr == pytest.approx(1.0)


def test_score_query_hit_at_3_only():
    r = score_query(
        gold_pages=[("doc_a", 7)],
        ranked_pages=[("doc_a", 1), ("doc_a", 7), ("doc_b", 1)],
    )
    assert r.hit_at_1 == 0.0
    assert r.hit_at_3 == 1.0
    assert r.rr == pytest.approx(0.5)


def test_score_query_miss():
    r = score_query(
        gold_pages=[("doc_a", 7)],
        ranked_pages=[("doc_b", 1), ("doc_b", 2), ("doc_b", 3)],
    )
    assert r.hit_at_1 == 0.0
    assert r.hit_at_3 == 0.0
    assert r.rr == 0.0


def test_score_query_multi_gold_first_hit_counts():
    r = score_query(
        gold_pages=[("doc_a", 7), ("doc_a", 9)],
        ranked_pages=[("doc_a", 9), ("doc_b", 1)],
    )
    assert r.hit_at_1 == 1.0
    assert r.rr == pytest.approx(1.0)


def test_aggregate_metrics():
    results = [
        PerQueryResult(query_id="q1", hit_at_1=1, hit_at_3=1, rr=1.0, latency_ms=10),
        PerQueryResult(query_id="q2", hit_at_1=0, hit_at_3=1, rr=0.5, latency_ms=10),
        PerQueryResult(query_id="q3", hit_at_1=0, hit_at_3=0, rr=0.0, latency_ms=10),
        PerQueryResult(query_id="q4", hit_at_1=1, hit_at_3=1, rr=1.0, latency_ms=10),
    ]
    agg = aggregate_metrics(results)
    assert agg["recall@1"] == pytest.approx(0.5)
    assert agg["recall@3"] == pytest.approx(0.75)
    assert agg["mrr"] == pytest.approx(0.625)
    assert agg["n"] == 4


def test_bootstrap_ci_returns_low_lt_high():
    values = [1.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0]
    lo, hi = bootstrap_ci(values, n_resamples=200, alpha=0.05, seed=1)
    assert 0.0 <= lo <= hi <= 1.0
    assert hi - lo > 0  # nontrivial spread


def test_bootstrap_ci_empty():
    lo, hi = bootstrap_ci([], n_resamples=100)
    assert lo == 0.0 and hi == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/sota/test_eval.py -v
```
Expected: FAIL — module not found.

- [ ] **Step 3: Write implementation**

```python
# backend/sota/eval.py
"""Page-level retrieval evaluation: Recall@1, Recall@3, MRR, Hit@1.

Strict containment: a hit means (doc_id, page_number) appears in gold set.
Bootstrap CI is non-parametric — works for binary (Recall) and continuous (RR).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

PageKey = Tuple[str, int]


@dataclass
class PerQueryResult:
    query_id: str
    hit_at_1: float       # 0.0 or 1.0
    hit_at_3: float       # 0.0 or 1.0
    rr: float             # reciprocal rank, 0.0 if no hit
    latency_ms: int
    error: Optional[str] = None


def score_query(gold_pages: List[PageKey], ranked_pages: List[PageKey]) -> PerQueryResult:
    """Return per-query metrics. RR = 1/(rank of first gold), 0 if absent."""
    gold = set(gold_pages)
    if not gold or not ranked_pages:
        return PerQueryResult(query_id="", hit_at_1=0.0, hit_at_3=0.0, rr=0.0, latency_ms=0)

    rr = 0.0
    for i, key in enumerate(ranked_pages):
        if key in gold:
            rr = 1.0 / (i + 1)
            break
    top1 = ranked_pages[:1]
    top3 = ranked_pages[:3]
    hit1 = 1.0 if any(k in gold for k in top1) else 0.0
    hit3 = 1.0 if any(k in gold for k in top3) else 0.0
    return PerQueryResult(query_id="", hit_at_1=hit1, hit_at_3=hit3, rr=rr, latency_ms=0)


def aggregate_metrics(results: List[PerQueryResult]) -> Dict[str, float]:
    n = len(results)
    if n == 0:
        return {"recall@1": 0.0, "recall@3": 0.0, "mrr": 0.0, "hit@1": 0.0, "n": 0}
    return {
        "recall@1": sum(r.hit_at_1 for r in results) / n,
        "recall@3": sum(r.hit_at_3 for r in results) / n,
        "mrr": sum(r.rr for r in results) / n,
        "hit@1": sum(r.hit_at_1 for r in results) / n,
        "n": n,
    }


def bootstrap_ci(
    values: List[float], n_resamples: int = 1000, alpha: float = 0.05, seed: int = 0,
) -> Tuple[float, float]:
    """95% percentile bootstrap CI for the mean. Non-parametric, no scipy."""
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_idx = max(0, int((alpha / 2) * n_resamples))
    hi_idx = min(n_resamples - 1, int((1 - alpha / 2) * n_resamples))
    return means[lo_idx], means[hi_idx]
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/sota/test_eval.py -v
```
Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/sota/eval.py tests/sota/test_eval.py
git commit -m "feat(sota): page-level eval (Recall@1/@3, MRR) + bootstrap CI"
```

---

## Task 4: VisDoM Dataset Loader (Metadata + Integrity Check)

**Files:**
- Create: `backend/sota/datasets.py`
- Test: `tests/sota/test_datasets.py`

VisDoM-main on remote box has this structure (verified by reading
the official repo's README and the existing `services/visdom_bootstrap.py`):

```
/root/autodl-tmp/liboze/data/VisDoM-main/
├── data/
│   ├── fetatab/   queries.jsonl  pdfs/  pages/
│   ├── mmlongbench/
│   ├── papertab/
│   └── slidevqa/
└── ...
```

Each `queries.jsonl` row: `{query_id, query, gold_doc_ids, gold_page_numbers, ...}`.

For Phase 0 we read the metadata once via SFTP into `data/sota_runs/datasets/<subset>/queries.jsonl` (small, MB-scale). Page images stay remote — encoders run on the worker which already has filesystem access.

- [ ] **Step 1: Write the failing test**

```python
# tests/sota/test_datasets.py
import json
import os
import pytest

from backend.sota.datasets import (
    DatasetIntegrity, SUBSETS, count_local_queries, load_local_queries,
)


@pytest.fixture
def fake_root(tmp_path):
    for subset in ("fetatab", "slidevqa"):
        d = tmp_path / subset
        d.mkdir()
        with open(d / "queries.jsonl", "w") as f:
            for i in range(3):
                f.write(json.dumps({
                    "query_id": f"{subset}_{i}",
                    "query": f"q {i}",
                    "gold_doc_ids": [f"doc_{i}"],
                    "gold_page_numbers": [i + 1],
                }) + "\n")
    return str(tmp_path)


def test_subsets_constant_is_canonical():
    assert SUBSETS == ("fetatab", "mmlongbench", "papertab", "slidevqa")


def test_count_local_queries(fake_root):
    assert count_local_queries(fake_root, "fetatab") == 3
    assert count_local_queries(fake_root, "mmlongbench") == 0


def test_load_local_queries(fake_root):
    qs = list(load_local_queries(fake_root, "fetatab", limit=2))
    assert len(qs) == 2
    assert qs[0].query_id == "fetatab_0"
    assert qs[0].gold_pages == [("doc_0", 1)]


def test_integrity_check_partial(fake_root):
    integ = DatasetIntegrity.scan(fake_root)
    assert integ.subsets["fetatab"]["status"] == "ok"
    assert integ.subsets["fetatab"]["query_count"] == 3
    assert integ.subsets["mmlongbench"]["status"] == "missing"
    assert integ.subsets["slidevqa"]["status"] == "ok"
    assert integ.subsets["papertab"]["status"] == "missing"
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/sota/test_datasets.py -v
```
Expected: FAIL.

- [ ] **Step 3: Write implementation**

```python
# backend/sota/datasets.py
"""VisDoMBench dataset loader + integrity checker.

Phase 0 only consumes locally-cached metadata (queries.jsonl per subset).
Page images live on the remote worker filesystem; methods request encodings
through the worker rather than touching images directly.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

PageKey = Tuple[str, int]
SUBSETS: Tuple[str, ...] = ("fetatab", "mmlongbench", "papertab", "slidevqa")


@dataclass
class SotaQuery:
    """One VisDoMBench retrieval query.

    Methods receive these via iter_queries(). Methods MUST NOT see gold_pages —
    that lives in the evaluator scope only.
    """
    query_id: str
    subset: str
    query: str
    gold_pages: List[PageKey] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


def count_local_queries(root: str, subset: str) -> int:
    p = os.path.join(root, subset, "queries.jsonl")
    if not os.path.exists(p):
        return 0
    n = 0
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def load_local_queries(root: str, subset: str, limit: Optional[int] = None) -> Iterator[SotaQuery]:
    p = os.path.join(root, subset, "queries.jsonl")
    if not os.path.exists(p):
        return
    with open(p, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            doc_ids = row.get("gold_doc_ids") or []
            pages = row.get("gold_page_numbers") or []
            gold: List[PageKey] = []
            for d, pg in zip(doc_ids, pages):
                try:
                    gold.append((str(d), int(pg)))
                except (TypeError, ValueError):
                    continue
            yield SotaQuery(
                query_id=str(row.get("query_id") or f"{subset}_{i}"),
                subset=subset,
                query=str(row.get("query", "")),
                gold_pages=gold,
                metadata={k: v for k, v in row.items() if k not in {
                    "query_id", "query", "gold_doc_ids", "gold_page_numbers",
                }},
            )


@dataclass
class DatasetIntegrity:
    subsets: Dict[str, Dict] = field(default_factory=dict)

    @classmethod
    def scan(cls, root: str) -> "DatasetIntegrity":
        out: Dict[str, Dict] = {}
        for s in SUBSETS:
            p = os.path.join(root, s, "queries.jsonl")
            if not os.path.exists(p):
                out[s] = {"status": "missing", "path": p, "query_count": 0}
                continue
            n = count_local_queries(root, s)
            out[s] = {
                "status": "ok" if n > 0 else "empty",
                "path": p,
                "query_count": n,
            }
        return cls(subsets=out)

    def to_dict(self) -> Dict:
        return {"subsets": self.subsets}
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/sota/test_datasets.py -v
```
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/sota/datasets.py tests/sota/test_datasets.py
git commit -m "feat(sota): VisDoMBench metadata loader + integrity scan"
```

---

## Task 5: Method Registry + 3 Baselines

**Files:**
- Create: `backend/sota/methods/__init__.py`
- Create: `backend/sota/methods/baseline_colpali.py`
- Create: `backend/sota/methods/baseline_bm25.py`
- Create: `backend/sota/methods/baseline_rrf.py`
- Test: `tests/sota/test_methods_baselines.py`

A "method" produces ranked `(doc_id, page_number)` pairs given a query. Phase 0 baselines delegate to existing services:
- ColPali: `pipeline.retriever.retrieve(query, top_k)` (existing main pipeline)
- BM25: `lab_bundle.hybrid.bm25_retrieve(query, top_k)`
- RRF: combine the two ranked lists via Reciprocal Rank Fusion

- [ ] **Step 1: Write the failing test**

```python
# tests/sota/test_methods_baselines.py
import pytest

from backend.sota.methods import METHOD_REGISTRY, get_method, MethodMeta
from backend.sota.methods.baseline_rrf import _rrf_fuse


def test_registry_has_three_baselines():
    assert "baseline_colpali" in METHOD_REGISTRY
    assert "baseline_bm25" in METHOD_REGISTRY
    assert "baseline_rrf" in METHOD_REGISTRY


def test_registry_meta_no_test_label_use():
    for meta in METHOD_REGISTRY.values():
        assert meta.uses_test_labels is False, (
            f"{meta.name}: methods must never see test labels"
        )


def test_get_method_returns_meta():
    m = get_method("baseline_colpali")
    assert isinstance(m, MethodMeta)
    assert m.name == "baseline_colpali"
    assert callable(m.run)


def test_rrf_fuse_basic():
    a = [("d1", 1), ("d1", 2), ("d2", 1)]
    b = [("d2", 1), ("d1", 1), ("d3", 1)]
    fused = _rrf_fuse([a, b], k=60, top_k=3)
    keys = [(d, p) for (d, p, _s) in fused]
    assert keys[0] in {("d1", 1), ("d2", 1)}
    assert ("d3", 1) not in keys[:2]


def test_rrf_fuse_handles_empty_channels():
    fused = _rrf_fuse([[], [("d1", 1)]], k=60, top_k=3)
    assert len(fused) == 1
    assert fused[0][0] == "d1"
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/sota/test_methods_baselines.py -v
```
Expected: FAIL.

- [ ] **Step 3: Write registry + RRF implementation**

```python
# backend/sota/methods/__init__.py
"""Method registry: name → MethodMeta. Loaded lazily on first import.

Academic-integrity rule: a method cannot expose `uses_test_labels=True`.
The loader rejects any module that does.
"""
from __future__ import annotations

import dataclasses
import logging
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

PageKey = Tuple[str, int]


@dataclasses.dataclass
class MethodContext:
    """Everything a method needs to run a query, injected by the executor."""
    pipeline: object             # main pipeline (ColPali retriever inside)
    lab_bundle: object           # for BM25, region, graph
    qdrant_client: object
    worker_client: object
    cancelled_flag: Callable[[], bool] = lambda: False
    extras: Dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class MethodMeta:
    name: str
    version: str
    description: str
    needs: List[str]
    uses_test_labels: bool
    run: Callable[..., Awaitable[List[Tuple[str, int, float]]]]


METHOD_REGISTRY: Dict[str, MethodMeta] = {}


def register(meta: MethodMeta) -> None:
    if meta.uses_test_labels:
        raise RuntimeError(
            f"academic integrity violation: method {meta.name!r} flags "
            f"uses_test_labels=True; methods must never see test labels"
        )
    METHOD_REGISTRY[meta.name] = meta
    logger.info("[sota] registered method %s v%s", meta.name, meta.version)


def get_method(name: str) -> MethodMeta:
    if name not in METHOD_REGISTRY:
        raise KeyError(f"method not registered: {name}")
    return METHOD_REGISTRY[name]


# Eager import — registers each method at module load.
from . import baseline_colpali, baseline_bm25, baseline_rrf  # noqa: E402,F401
```

```python
# backend/sota/methods/baseline_colpali.py
"""ColPali baseline: delegate to main pipeline's retriever."""
from __future__ import annotations

import logging
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register

logger = logging.getLogger(__name__)


async def _run(query: str, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    pipeline = ctx.pipeline
    if pipeline is None or pipeline.retriever is None:
        raise RuntimeError("main pipeline / ColPali retriever unavailable")
    # Main pipeline encodes query and runs Qdrant search
    encoded = await pipeline.encode_query(query)
    hits = await pipeline.retriever.retrieve(encoded, top_k=top_k)
    return [(h.document_id, h.page_number, float(h.score)) for h in hits]


register(MethodMeta(
    name="baseline_colpali",
    version="1.0",
    description="Main-pipeline ColPali multi-vector retrieval (page-level).",
    needs=["pipeline"],
    uses_test_labels=False,
    run=_run,
))
```

```python
# backend/sota/methods/baseline_bm25.py
"""BM25 baseline: reuses lab/hybrid BM25 index, read-only."""
from __future__ import annotations

import logging
from typing import List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register

logger = logging.getLogger(__name__)


async def _run(query: str, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    lab = ctx.lab_bundle
    if lab is None or lab.hybrid is None:
        raise RuntimeError("lab BM25 service unavailable")
    hits = await lab.hybrid.bm25_retrieve(query, top_k=top_k)
    return [(h.document_id, h.page_number, float(h.score)) for h in hits]


register(MethodMeta(
    name="baseline_bm25",
    version="1.0",
    description="BM25 sparse text retrieval over OCR'd page text.",
    needs=["lab_bundle.hybrid"],
    uses_test_labels=False,
    run=_run,
))
```

```python
# backend/sota/methods/baseline_rrf.py
"""RRF baseline: BM25 ⊕ ColPali via Reciprocal Rank Fusion."""
from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from backend.sota.methods import MethodContext, MethodMeta, register
from backend.sota.methods.baseline_bm25 import _run as _bm25_run
from backend.sota.methods.baseline_colpali import _run as _colpali_run

logger = logging.getLogger(__name__)


def _rrf_fuse(
    ranked_lists: List[List[Tuple[str, int]]], k: int = 60, top_k: int = 10,
) -> List[Tuple[str, int, float]]:
    scores: Dict[Tuple[str, int], float] = {}
    for ranked in ranked_lists:
        for i, key in enumerate(ranked):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + i + 1)
    fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [(d, p, s) for ((d, p), s) in fused]


async def _run(query: str, top_k: int, ctx: MethodContext) -> List[Tuple[str, int, float]]:
    # Pull each baseline list independently; failure of one channel degrades to single-channel.
    a: List[Tuple[str, int]] = []
    b: List[Tuple[str, int]] = []
    try:
        a = [(d, p) for (d, p, _s) in await _colpali_run(query, top_k * 2, ctx)]
    except Exception as e:
        logger.warning("[rrf] ColPali leg failed: %s", e)
    try:
        b = [(d, p) for (d, p, _s) in await _bm25_run(query, top_k * 2, ctx)]
    except Exception as e:
        logger.warning("[rrf] BM25 leg failed: %s", e)
    return _rrf_fuse([a, b], k=60, top_k=top_k)


register(MethodMeta(
    name="baseline_rrf",
    version="1.0",
    description="Reciprocal Rank Fusion of ColPali + BM25 (k=60).",
    needs=["pipeline", "lab_bundle.hybrid"],
    uses_test_labels=False,
    run=_run,
))
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/sota/test_methods_baselines.py -v
```
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/sota/methods tests/sota/test_methods_baselines.py
git commit -m "feat(sota): method registry + 3 baselines (ColPali, BM25, RRF)"
```

---

## Task 6: Indexer Stub (Phase 0 only — wraps existing services)

For Phase 0 we don't need new indexers — ColPali index exists in the main Qdrant collection, BM25 index lives in `lab/hybrid`. We add a thin facade so Phase 1 can drop in new encoders later without touching methods.

**Files:**
- Create: `backend/sota/indexers.py`

- [ ] **Step 1: Write minimal facade**

```python
# backend/sota/indexers.py
"""Indexer facade. Phase 0 wraps existing main-pipeline + lab/hybrid services.

Phase 1 will add ColQwen2.5, jina-clip-v2, DSE — each as a new BaseIndexer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class IndexHealth:
    encoder: str
    subset: Optional[str]
    ok: bool
    message: str
    points: Optional[int] = None


class BaseIndexer:
    name: str = "base"

    async def health(self, subset: Optional[str] = None) -> IndexHealth:
        return IndexHealth(encoder=self.name, subset=subset, ok=False, message="not implemented")


class ColPaliMainIndexer(BaseIndexer):
    """Phase 0 wrapper around the main 'documents' Qdrant collection."""
    name = "colpali_main"

    def __init__(self, qdrant_client, collection_name: str = "documents"):
        self.qdrant_client = qdrant_client
        self.collection_name = collection_name

    async def health(self, subset: Optional[str] = None) -> IndexHealth:
        try:
            info = await self.qdrant_client.get_collection(self.collection_name)
            n = getattr(info, "points_count", 0) or 0
            return IndexHealth(encoder=self.name, subset=subset, ok=True,
                               message=f"{n} points in {self.collection_name}", points=n)
        except Exception as e:
            return IndexHealth(encoder=self.name, subset=subset, ok=False,
                               message=f"{type(e).__name__}: {e}")


class Bm25LabIndexer(BaseIndexer):
    """Phase 0 wrapper around lab/hybrid BM25 index."""
    name = "bm25_lab"

    def __init__(self, lab_bundle):
        self.lab_bundle = lab_bundle

    async def health(self, subset: Optional[str] = None) -> IndexHealth:
        try:
            if self.lab_bundle is None or self.lab_bundle.hybrid is None:
                return IndexHealth(encoder=self.name, subset=subset, ok=False, message="lab.hybrid unavailable")
            n = self.lab_bundle.hybrid.bm25_doc_count()  # added in Task 7
            return IndexHealth(encoder=self.name, subset=subset, ok=True,
                               message=f"{n} BM25 docs", points=n)
        except Exception as e:
            return IndexHealth(encoder=self.name, subset=subset, ok=False,
                               message=f"{type(e).__name__}: {e}")
```

- [ ] **Step 2: Commit**

```bash
git add backend/sota/indexers.py
git commit -m "feat(sota): Phase 0 indexer facade wrapping existing services"
```

---

## Task 7: Bridge Methods to Existing lab + pipeline Services

**Files:**
- Modify: `backend/lab/hybrid.py` (add public `bm25_retrieve` + `bm25_doc_count`)
- Modify: `backend/core/pipeline.py` (add public `encode_query` if not present)
- Test: `tests/sota/test_bridge.py` (smoke test using stubs)

The baselines call `lab.hybrid.bm25_retrieve` and `pipeline.encode_query`. Confirm these exist or add thin wrappers.

- [ ] **Step 1: Inspect current lab/hybrid for the BM25 entry point**

Read `backend/lab/hybrid.py` end-to-end. If a method exposing BM25 ranked results given a raw query exists, reuse it. If only an internal one exists, add a public method:

```python
# backend/lab/hybrid.py — append at end of class LabHybridService
async def bm25_retrieve(self, query: str, top_k: int = 10):
    """Public BM25 entry for SOTA baseline reuse. Returns RetrievalResult list."""
    self._reconcile_index_if_stale()  # existing internal call
    return self._bm25.retrieve(query, top_k=top_k)  # existing internal field

def bm25_doc_count(self) -> int:
    return self._bm25.doc_count() if hasattr(self._bm25, "doc_count") else 0
```

If method names differ in current code, adapt verbatim — keep the public surface `bm25_retrieve(query, top_k) -> List[RetrievalResult]` regardless of internal naming.

- [ ] **Step 2: Inspect `backend/core/pipeline.py` for `encode_query`**

If the main pipeline has a private `_encode_query`, add a public wrapper:

```python
# backend/core/pipeline.py — append on the Pipeline class
async def encode_query(self, query: str):
    """Public query encoding for SOTA baseline reuse."""
    if self.query_encoder is None:
        raise RuntimeError("query_encoder not configured")
    return await self.query_encoder.encode_query(query)
```

- [ ] **Step 3: Smoke-test the bridge**

```python
# tests/sota/test_bridge.py
import pytest


def test_bm25_retrieve_signature_exists():
    from backend.lab.hybrid import LabHybridService
    assert hasattr(LabHybridService, "bm25_retrieve")
    assert hasattr(LabHybridService, "bm25_doc_count")


def test_pipeline_encode_query_exists():
    from backend.core.pipeline import Pipeline
    assert hasattr(Pipeline, "encode_query")
```

```
pytest tests/sota/test_bridge.py -v
```
Expected: 2 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/lab/hybrid.py backend/core/pipeline.py tests/sota/test_bridge.py
git commit -m "feat(sota): expose public bm25_retrieve + encode_query for SOTA baselines"
```

---

## Task 8: Run Executor (Background Task Orchestration)

**Files:**
- Create: `backend/sota/executor.py`
- Test: `tests/sota/test_executor.py`

- [ ] **Step 1: Write executor with timeouts + circuit breaker**

```python
# backend/sota/executor.py
"""Background-task executor: orchestrates dataset × method matrix.

Per-query timeout 60 s; per-method timeout 30 min; per-run cap 6 h.
A method with ≥3 consecutive failures has its circuit opened for the
remainder of the run. Cancellation is cooperative.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List

from backend.sota.datasets import SUBSETS, load_local_queries
from backend.sota.error_envelope import ErrorKind
from backend.sota.eval import (
    PerQueryResult, aggregate_metrics, bootstrap_ci, score_query,
)
from backend.sota.methods import MethodContext, get_method
from backend.sota.runs import RunRegistry
from backend.sota.schemas import (
    MethodResult, MethodStatus, MetricCell, RunConfig, RunStatus,
)

logger = logging.getLogger(__name__)

PER_QUERY_TIMEOUT_SEC = 60
PER_METHOD_TIMEOUT_SEC = 30 * 60
PER_RUN_TIMEOUT_SEC = 6 * 3600
CIRCUIT_BREAK_AFTER_N_FAILS = 3


class RunExecutor:
    def __init__(
        self,
        registry: RunRegistry,
        sota_data_root: str,
        pipeline,
        lab_bundle,
        qdrant_client,
        worker_client,
    ):
        self.registry = registry
        self.sota_data_root = sota_data_root
        self.pipeline = pipeline
        self.lab_bundle = lab_bundle
        self.qdrant_client = qdrant_client
        self.worker_client = worker_client
        self._cancelled: Dict[str, bool] = {}

    def cancel(self, run_id: str) -> None:
        self._cancelled[run_id] = True

    def _is_cancelled(self, run_id: str) -> bool:
        return self._cancelled.get(run_id, False)

    async def execute(self, run_id: str, config: RunConfig) -> None:
        run_start = time.time()
        await self.registry.set_run_status(run_id, RunStatus.RUNNING)
        ctx = MethodContext(
            pipeline=self.pipeline, lab_bundle=self.lab_bundle,
            qdrant_client=self.qdrant_client, worker_client=self.worker_client,
            cancelled_flag=lambda: self._is_cancelled(run_id),
        )
        any_partial = False
        any_ok = False

        for method_name in config.methods:
            method_start = time.time()
            try:
                meta = get_method(method_name)
            except KeyError as e:
                await self.registry.upsert_method_result(run_id, MethodResult(
                    method=method_name, status=MethodStatus.SKIPPED, duration_ms=0,
                    error_kind="not_registered",
                ))
                continue

            consec_fail = 0
            method_status = MethodStatus.OK

            for subset in config.subsets:
                if self._is_cancelled(run_id):
                    method_status = MethodStatus.PARTIAL
                    break
                if time.time() - run_start > PER_RUN_TIMEOUT_SEC:
                    method_status = MethodStatus.PARTIAL
                    break

                queries = list(load_local_queries(
                    self.sota_data_root, subset, limit=config.n_queries_per_subset,
                ))
                if not queries:
                    await self.registry.append_error(
                        run_id, method_name, None,
                        ErrorKind.DATASET_MISSING.value,
                        f"no queries cached for subset {subset}",
                    )
                    continue

                per_query: List[PerQueryResult] = []
                for q in queries:
                    if self._is_cancelled(run_id):
                        break
                    if consec_fail >= CIRCUIT_BREAK_AFTER_N_FAILS:
                        method_status = MethodStatus.CIRCUIT_OPEN
                        break

                    t0 = time.time()
                    try:
                        ranked = await asyncio.wait_for(
                            meta.run(q.query, config.top_k, ctx),
                            timeout=PER_QUERY_TIMEOUT_SEC,
                        )
                        consec_fail = 0
                        ranked_pages = [(d, p) for (d, p, _s) in ranked]
                        r = score_query(q.gold_pages, ranked_pages)
                        r.query_id = q.query_id
                        r.latency_ms = int((time.time() - t0) * 1000)
                        per_query.append(r)
                        await self.registry.append_query_trace(run_id, {
                            "query_id": q.query_id, "subset": subset, "method": method_name,
                            "ranked": ranked_pages[:10], "gold": q.gold_pages,
                            "rr": r.rr, "hit_at_1": r.hit_at_1, "hit_at_3": r.hit_at_3,
                            "latency_ms": r.latency_ms,
                        })
                    except asyncio.TimeoutError:
                        consec_fail += 1
                        await self.registry.append_error(
                            run_id, method_name, q.query_id,
                            ErrorKind.METHOD_TIMEOUT.value,
                            f"query timed out after {PER_QUERY_TIMEOUT_SEC}s",
                        )
                    except Exception as e:
                        consec_fail += 1
                        await self.registry.append_error(
                            run_id, method_name, q.query_id,
                            ErrorKind.METHOD_FAILED.value,
                            f"{type(e).__name__}: {e}",
                        )

                if not per_query:
                    method_status = MethodStatus.PARTIAL if method_status == MethodStatus.OK else method_status
                    continue

                agg = aggregate_metrics(per_query)
                # CI on Recall@1 and Recall@3
                hit1_vals = [r.hit_at_1 for r in per_query]
                hit3_vals = [r.hit_at_3 for r in per_query]
                rr_vals = [r.rr for r in per_query]
                lo1, hi1 = bootstrap_ci(hit1_vals, n_resamples=1000, seed=hash(run_id) & 0xFFFF)
                lo3, hi3 = bootstrap_ci(hit3_vals, n_resamples=1000, seed=hash(run_id) & 0xFFFF)
                lo_rr, hi_rr = bootstrap_ci(rr_vals, n_resamples=1000, seed=hash(run_id) & 0xFFFF)
                n = int(agg["n"])

                for metric, value, lo, hi in (
                    ("recall@1", agg["recall@1"], lo1, hi1),
                    ("recall@3", agg["recall@3"], lo3, hi3),
                    ("mrr", agg["mrr"], lo_rr, hi_rr),
                    ("hit@1", agg["hit@1"], lo1, hi1),
                ):
                    await self.registry.append_metric(run_id, MetricCell(
                        method=method_name, subset=subset, metric=metric,
                        value=value, ci_low=lo, ci_high=hi, n_queries=n,
                    ))
                any_ok = True

            duration = int((time.time() - method_start) * 1000)
            await self.registry.upsert_method_result(run_id, MethodResult(
                method=method_name, status=method_status,
                duration_ms=duration, error_kind=None,
            ))
            if method_status != MethodStatus.OK:
                any_partial = True

        # Run-level finalization
        run_dur = int((time.time() - run_start) * 1000)
        if self._is_cancelled(run_id):
            final = RunStatus.CANCELLED
        elif any_ok and any_partial:
            final = RunStatus.PARTIAL
        elif any_ok:
            final = RunStatus.COMPLETED
        else:
            final = RunStatus.FAILED
        await self.registry.set_run_status(run_id, final, duration_ms=run_dur)
```

- [ ] **Step 2: Write the executor smoke test**

```python
# tests/sota/test_executor.py
import json
import os
import pytest

from backend.sota.executor import RunExecutor
from backend.sota.runs import RunRegistry
from backend.sota.schemas import RunConfig, RunStatus
from backend.sota.methods import MethodMeta, METHOD_REGISTRY, register


@pytest.fixture
def fake_dataset_root(tmp_path):
    sub = tmp_path / "fetatab"
    sub.mkdir()
    with open(sub / "queries.jsonl", "w") as f:
        for i in range(3):
            f.write(json.dumps({
                "query_id": f"q{i}", "query": f"text {i}",
                "gold_doc_ids": ["doc"], "gold_page_numbers": [i + 1],
            }) + "\n")
    return str(tmp_path)


@pytest.fixture
def stub_method():
    async def _run(query, top_k, ctx):
        # Always returns (doc, 1) — only q0 is correct
        return [("doc", 1, 1.0), ("doc", 2, 0.9), ("doc", 3, 0.8)]
    register(MethodMeta(
        name="stub_method", version="t",
        description="test", needs=[], uses_test_labels=False, run=_run,
    ))
    yield "stub_method"
    METHOD_REGISTRY.pop("stub_method", None)


@pytest.mark.asyncio
async def test_executor_runs_and_writes_metrics(tmp_path, fake_dataset_root, stub_method):
    registry = RunRegistry(root=str(tmp_path / "runs"))
    cfg = RunConfig(subsets=["fetatab"], methods=[stub_method], n_queries_per_subset=3, top_k=5)
    run_id = await registry.create_run(cfg)
    ex = RunExecutor(registry, fake_dataset_root, pipeline=None, lab_bundle=None,
                     qdrant_client=None, worker_client=None)
    await ex.execute(run_id, cfg)

    summary = await registry.get_run(run_id)
    assert summary.status in {RunStatus.COMPLETED, RunStatus.PARTIAL}
    assert any(m.method == stub_method for m in summary.metrics)
    r1 = next(m for m in summary.metrics if m.metric == "recall@1")
    # q0 is the only correct one (gold=p1 and rank0=p1)
    # but stub returns p1 for every query, so q0 hits → 1/3
    assert r1.value == pytest.approx(1 / 3, abs=0.01)
```

- [ ] **Step 3: Run test**

```
pytest tests/sota/test_executor.py -v
```
Expected: 1 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/sota/executor.py tests/sota/test_executor.py
git commit -m "feat(sota): run executor with per-query timeout + circuit breaker"
```

---

## Task 9: Service DI + HTTP Routes

**Files:**
- Create: `backend/sota/service.py`
- Create: `backend/sota/routes.py`
- Modify: `backend/main.py`
- Modify: `run.py` (add bundle construction)
- Test: `tests/sota/test_routes_smoke.py`

- [ ] **Step 1: Service container**

```python
# backend/sota/service.py
"""SOTA bundle: held on app.state.sota_bundle. Constructed once at startup."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from backend.sota.executor import RunExecutor
from backend.sota.indexers import BaseIndexer, Bm25LabIndexer, ColPaliMainIndexer
from backend.sota.runs import RunRegistry

logger = logging.getLogger(__name__)


@dataclass
class SotaBundle:
    registry: RunRegistry
    executor: RunExecutor
    indexers: Dict[str, BaseIndexer]
    sota_data_root: str

    def get_indexer(self, name: str) -> Optional[BaseIndexer]:
        return self.indexers.get(name)


def build_sota_bundle(
    sota_data_root: str,
    runs_root: str,
    pipeline,
    lab_bundle,
    qdrant_client,
    worker_client,
    collection_name: str = "documents",
) -> SotaBundle:
    registry = RunRegistry(root=runs_root)
    executor = RunExecutor(
        registry=registry, sota_data_root=sota_data_root,
        pipeline=pipeline, lab_bundle=lab_bundle,
        qdrant_client=qdrant_client, worker_client=worker_client,
    )
    indexers: Dict[str, BaseIndexer] = {}
    if qdrant_client is not None:
        indexers["colpali_main"] = ColPaliMainIndexer(qdrant_client, collection_name)
    if lab_bundle is not None:
        indexers["bm25_lab"] = Bm25LabIndexer(lab_bundle)
    logger.info("[sota] bundle ready: %d indexers, runs at %s", len(indexers), runs_root)
    return SotaBundle(
        registry=registry, executor=executor, indexers=indexers,
        sota_data_root=sota_data_root,
    )
```

- [ ] **Step 2: HTTP routes**

```python
# backend/sota/routes.py
"""All /api/sota/* endpoints. All return HTTP 200 with envelope."""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Request
from pydantic import BaseModel, Field

from backend.sota.datasets import DatasetIntegrity, SUBSETS
from backend.sota.error_envelope import ErrorKind, SotaError, wrap_response
from backend.sota.methods import METHOD_REGISTRY
from backend.sota.schemas import RunConfig

logger = logging.getLogger(__name__)
router = APIRouter()


def _bundle(request: Request):
    bundle = getattr(request.app.state, "sota_bundle", None)
    if bundle is None:
        raise SotaError(ErrorKind.UNEXPECTED, "sota_bundle not initialized")
    return bundle


@router.get("/health")
@wrap_response
async def health(request: Request):
    bundle = _bundle(request)
    indexer_health = {}
    for name, idx in bundle.indexers.items():
        h = await idx.health()
        indexer_health[name] = {"ok": h.ok, "message": h.message, "points": h.points}
    return {"ok": True, "indexers": indexer_health, "methods": list(METHOD_REGISTRY.keys())}


@router.get("/datasets")
@wrap_response
async def list_datasets(request: Request):
    bundle = _bundle(request)
    integ = DatasetIntegrity.scan(bundle.sota_data_root)
    return {"ok": True, "subsets": integ.subsets, "expected": list(SUBSETS)}


@router.post("/datasets/{subset}/check")
@wrap_response
async def check_dataset(subset: str, request: Request):
    bundle = _bundle(request)
    if subset not in SUBSETS:
        raise SotaError(ErrorKind.INVALID_CONFIG, f"unknown subset: {subset}")
    integ = DatasetIntegrity.scan(bundle.sota_data_root)
    return {"ok": True, "subset": subset, "info": integ.subsets.get(subset)}


@router.get("/methods")
@wrap_response
async def list_methods(request: Request):
    return {"ok": True, "methods": [
        {
            "name": m.name, "version": m.version,
            "description": m.description, "needs": m.needs,
        }
        for m in METHOD_REGISTRY.values()
    ]}


class CreateRunRequest(BaseModel):
    subsets: List[str] = Field(default_factory=lambda: list(SUBSETS))
    methods: List[str] = Field(default_factory=lambda: ["baseline_colpali", "baseline_bm25", "baseline_rrf"])
    top_k: int = 10
    n_queries_per_subset: Optional[int] = 50
    notes: str = ""


@router.post("/runs")
@wrap_response
async def create_run(req: CreateRunRequest, background_tasks: BackgroundTasks, request: Request):
    bundle = _bundle(request)
    # validate
    for s in req.subsets:
        if s not in SUBSETS:
            raise SotaError(ErrorKind.INVALID_CONFIG, f"unknown subset: {s}")
    for m in req.methods:
        if m not in METHOD_REGISTRY:
            raise SotaError(ErrorKind.INVALID_CONFIG, f"unknown method: {m}")
    cfg = RunConfig(
        subsets=req.subsets, methods=req.methods, top_k=req.top_k,
        n_queries_per_subset=req.n_queries_per_subset, notes=req.notes,
    )
    run_id = await bundle.registry.create_run(cfg)
    background_tasks.add_task(bundle.executor.execute, run_id, cfg)
    return {"ok": True, "run_id": run_id}


@router.get("/runs")
@wrap_response
async def list_runs(request: Request, limit: int = 50):
    bundle = _bundle(request)
    rows = await bundle.registry.list_runs(limit=limit)
    return {"ok": True, "runs": [r.model_dump() for r in rows]}


@router.get("/runs/{run_id}")
@wrap_response
async def get_run(run_id: str, request: Request):
    bundle = _bundle(request)
    summary = await bundle.registry.get_run(run_id)
    return {"ok": True, "run": summary.model_dump()}


@router.post("/runs/{run_id}/cancel")
@wrap_response
async def cancel_run(run_id: str, request: Request):
    bundle = _bundle(request)
    bundle.executor.cancel(run_id)
    return {"ok": True}


@router.get("/leaderboard")
@wrap_response
async def leaderboard(request: Request):
    """Best (highest) value per (method, subset, metric) across all runs."""
    bundle = _bundle(request)
    rows = await bundle.registry.list_runs(limit=500)
    best: dict = {}
    for r in rows:
        for m in r.metrics:
            key = (m.method, m.subset, m.metric)
            if key not in best or m.value > best[key]["value"]:
                best[key] = {
                    "method": m.method, "subset": m.subset, "metric": m.metric,
                    "value": m.value, "ci_low": m.ci_low, "ci_high": m.ci_high,
                    "n_queries": m.n_queries, "run_id": r.id,
                }
    return {"ok": True, "rows": list(best.values())}
```

- [ ] **Step 3: Wire into main.py**

```python
# backend/main.py — diff-style edits

# at top with other imports:
from backend.sota.routes import router as sota_router

# in create_app signature, add sota_bundle parameter (after lab_bundle):
sota_bundle=None,

# inside create_app, after app.state.lab_bundle = lab_bundle:
app.state.sota_bundle = sota_bundle

# after include_router(lab_router, prefix="/api/lab"):
app.include_router(sota_router, prefix="/api/sota")
```

- [ ] **Step 4: Wire into run.py**

Locate where `lab_bundle` is built; add equivalent for sota.

```python
# run.py — find the spot where build_lab_bundle(...) is called.
from backend.sota.service import build_sota_bundle

# after lab_bundle is built:
sota_data_root = os.path.join(repo_root, "data", "sota_runs", "datasets")
runs_root = os.path.join(repo_root, "data", "sota_runs")
os.makedirs(sota_data_root, exist_ok=True)
os.makedirs(runs_root, exist_ok=True)
sota_bundle = build_sota_bundle(
    sota_data_root=sota_data_root, runs_root=runs_root,
    pipeline=pipeline_manager.active_pipeline if pipeline_manager else None,
    lab_bundle=lab_bundle, qdrant_client=qdrant_client,
    worker_client=worker_client, collection_name=collection_name,
)

# pass into create_app:
app = create_app(..., lab_bundle=lab_bundle, sota_bundle=sota_bundle, ...)
```

- [ ] **Step 5: Smoke-test routes**

```python
# tests/sota/test_routes_smoke.py
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.sota.service import build_sota_bundle


@pytest.fixture
def client(tmp_path):
    sota_root = tmp_path / "sota"
    bundle = build_sota_bundle(
        sota_data_root=str(sota_root / "datasets"),
        runs_root=str(sota_root / "runs"),
        pipeline=None, lab_bundle=None,
        qdrant_client=None, worker_client=None,
    )
    app = create_app(sota_bundle=bundle)
    return TestClient(app)


def test_health_returns_envelope(client):
    r = client.get("/api/sota/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "methods" in body


def test_methods_lists_three_baselines(client):
    r = client.get("/api/sota/methods")
    body = r.json()
    names = {m["name"] for m in body["methods"]}
    assert {"baseline_colpali", "baseline_bm25", "baseline_rrf"} <= names


def test_datasets_returns_subset_status(client):
    r = client.get("/api/sota/datasets")
    body = r.json()
    assert body["ok"] is True
    assert set(body["subsets"].keys()) == {"fetatab", "mmlongbench", "papertab", "slidevqa"}


def test_unknown_run_returns_envelope_not_500(client):
    r = client.get("/api/sota/runs/not-a-real-id")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["error_kind"] == "run_not_found"


def test_create_run_with_bad_method_returns_envelope(client):
    r = client.post("/api/sota/runs", json={"methods": ["nonexistent"]})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["error_kind"] == "invalid_config"
```

```
pytest tests/sota/test_routes_smoke.py -v
```
Expected: 5 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/sota/service.py backend/sota/routes.py backend/main.py run.py tests/sota/test_routes_smoke.py
git commit -m "feat(sota): wire HTTP routes + DI bundle, all 200-wrapped"
```

---

## Task 10: Frontend SOTA Sidebar Group + 5 View Stubs

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layout/SideBar.vue`
- Create: `frontend/src/api/sota.ts`
- Create: `frontend/src/views/sota/SotaDatasetsView.vue`
- Create: `frontend/src/views/sota/SotaMethodsView.vue`
- Create: `frontend/src/views/sota/SotaRunStudioView.vue`
- Create: `frontend/src/views/sota/SotaLeaderboardView.vue`
- Create: `frontend/src/views/sota/SotaRunDetailView.vue`

- [ ] **Step 1: API client**

```typescript
// frontend/src/api/sota.ts
import { http } from './client'

export interface SotaEnvelope<T> {
  ok: boolean
  error_kind?: string
  message?: string
  [k: string]: any
}

export async function getHealth() {
  return http.get<SotaEnvelope<any>>('/api/sota/health').then(r => r.data)
}
export async function getDatasets() {
  return http.get<SotaEnvelope<any>>('/api/sota/datasets').then(r => r.data)
}
export async function getMethods() {
  return http.get<SotaEnvelope<any>>('/api/sota/methods').then(r => r.data)
}
export async function createRun(body: {
  subsets: string[]; methods: string[]; top_k: number;
  n_queries_per_subset?: number | null; notes?: string;
}) {
  return http.post<SotaEnvelope<any>>('/api/sota/runs', body).then(r => r.data)
}
export async function listRuns(limit = 50) {
  return http.get<SotaEnvelope<any>>(`/api/sota/runs?limit=${limit}`).then(r => r.data)
}
export async function getRun(id: string) {
  return http.get<SotaEnvelope<any>>(`/api/sota/runs/${id}`).then(r => r.data)
}
export async function cancelRun(id: string) {
  return http.post<SotaEnvelope<any>>(`/api/sota/runs/${id}/cancel`, {}).then(r => r.data)
}
export async function getLeaderboard() {
  return http.get<SotaEnvelope<any>>('/api/sota/leaderboard').then(r => r.data)
}
```

- [ ] **Step 2: Datasets view**

```vue
<!-- frontend/src/views/sota/SotaDatasetsView.vue -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getDatasets } from '../../api/sota'

const loading = ref(true)
const subsets = ref<Record<string, any>>({})
const errMsg = ref('')

async function refresh() {
  loading.value = true
  errMsg.value = ''
  try {
    const r = await getDatasets()
    if (r.ok) subsets.value = r.subsets
    else errMsg.value = r.message || r.error_kind || 'unknown error'
  } catch (e: any) {
    errMsg.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}
onMounted(refresh)
</script>

<template>
  <div class="page">
    <h1>VisDoMBench 数据集</h1>
    <p>4 子集本地元数据状态。Phase 0 仅消费已下载到 <code>data/sota_runs/datasets/</code> 的 queries.jsonl。</p>
    <button @click="refresh" :disabled="loading">{{ loading ? '加载中…' : '刷新' }}</button>
    <div v-if="errMsg" class="err">{{ errMsg }}</div>
    <table v-else>
      <thead><tr><th>子集</th><th>状态</th><th>查询数</th><th>路径</th></tr></thead>
      <tbody>
        <tr v-for="(info, name) in subsets" :key="name">
          <td>{{ name }}</td>
          <td :class="info.status">{{ info.status }}</td>
          <td>{{ info.query_count }}</td>
          <td><code>{{ info.path }}</code></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.page { padding: 24px; }
table { width: 100%; border-collapse: collapse; margin-top: 16px; }
th, td { border-bottom: 1px solid #2a2f36; padding: 8px 12px; text-align: left; }
.ok { color: #4ade80; } .missing, .err { color: #f87171; } .empty { color: #fbbf24; }
</style>
```

- [ ] **Step 3: Methods view**

```vue
<!-- frontend/src/views/sota/SotaMethodsView.vue -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getMethods } from '../../api/sota'

const methods = ref<any[]>([])
const errMsg = ref('')

async function refresh() {
  const r = await getMethods()
  if (r.ok) methods.value = r.methods
  else errMsg.value = r.message || r.error_kind || ''
}
onMounted(refresh)
</script>

<template>
  <div class="page">
    <h1>方法库</h1>
    <p>每个方法独立模块, 单方法崩 → run 状态 partial, 其他方法继续。</p>
    <div v-if="errMsg" class="err">{{ errMsg }}</div>
    <div v-else class="cards">
      <div v-for="m in methods" :key="m.name" class="card">
        <div class="hd">{{ m.name }} <span class="ver">v{{ m.version }}</span></div>
        <div class="desc">{{ m.description }}</div>
        <div class="needs">依赖: {{ (m.needs || []).join(', ') || '—' }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 24px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-top: 16px; }
.card { border: 1px solid #2a2f36; border-radius: 8px; padding: 14px; }
.hd { font-weight: 600; }
.ver { font-size: 12px; color: #888; }
.desc { margin: 8px 0; color: #d4d4d4; }
.needs { font-size: 12px; color: #888; }
.err { color: #f87171; }
</style>
```

- [ ] **Step 4: Run Studio view**

```vue
<!-- frontend/src/views/sota/SotaRunStudioView.vue -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getDatasets, getMethods, createRun } from '../../api/sota'

const router = useRouter()
const subsets = ref<string[]>([])
const methods = ref<string[]>([])
const subsetSel = ref<Record<string, boolean>>({})
const methodSel = ref<Record<string, boolean>>({})
const topK = ref(10)
const scale = ref<'quick' | 'standard' | 'full'>('quick')
const notes = ref('')
const submitting = ref(false)
const errMsg = ref('')

async function load() {
  const ds = await getDatasets()
  if (ds.ok) {
    subsets.value = Object.keys(ds.subsets)
    for (const s of subsets.value) subsetSel.value[s] = ds.subsets[s].status === 'ok'
  }
  const ms = await getMethods()
  if (ms.ok) {
    methods.value = ms.methods.map((m: any) => m.name)
    for (const m of methods.value) methodSel.value[m] = true
  }
}
onMounted(load)

async function launch() {
  submitting.value = true
  errMsg.value = ''
  const n = scale.value === 'quick' ? 50 : scale.value === 'standard' ? 200 : null
  const body = {
    subsets: subsets.value.filter(s => subsetSel.value[s]),
    methods: methods.value.filter(m => methodSel.value[m]),
    top_k: topK.value,
    n_queries_per_subset: n,
    notes: notes.value,
  }
  try {
    const r = await createRun(body)
    if (r.ok) {
      router.push(`/sota/runs/${r.run_id}`)
    } else {
      errMsg.value = r.message || r.error_kind || ''
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page">
    <h1>实验台</h1>
    <section>
      <h3>子集</h3>
      <label v-for="s in subsets" :key="s" class="chk">
        <input type="checkbox" v-model="subsetSel[s]"> {{ s }}
      </label>
    </section>
    <section>
      <h3>方法</h3>
      <label v-for="m in methods" :key="m" class="chk">
        <input type="checkbox" v-model="methodSel[m]"> {{ m }}
      </label>
    </section>
    <section>
      <h3>规模</h3>
      <label class="chk"><input type="radio" v-model="scale" value="quick"> Quick (50/子集)</label>
      <label class="chk"><input type="radio" v-model="scale" value="standard"> Standard (200/子集)</label>
      <label class="chk"><input type="radio" v-model="scale" value="full"> Full (test 全部)</label>
    </section>
    <section>
      <h3>top-k</h3>
      <input type="number" v-model.number="topK" min="1" max="50">
    </section>
    <section>
      <h3>备注</h3>
      <input type="text" v-model="notes" placeholder="选填">
    </section>
    <button @click="launch" :disabled="submitting">{{ submitting ? '启动中…' : '启动实验' }}</button>
    <div v-if="errMsg" class="err">{{ errMsg }}</div>
  </div>
</template>

<style scoped>
.page { padding: 24px; max-width: 720px; }
section { margin-bottom: 16px; }
.chk { display: inline-block; margin-right: 12px; }
button { padding: 8px 16px; border-radius: 6px; }
.err { color: #f87171; margin-top: 8px; }
</style>
```

- [ ] **Step 5: Leaderboard view**

```vue
<!-- frontend/src/views/sota/SotaLeaderboardView.vue -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getLeaderboard } from '../../api/sota'

const rows = ref<any[]>([])
const errMsg = ref('')

async function refresh() {
  const r = await getLeaderboard()
  if (r.ok) rows.value = r.rows
  else errMsg.value = r.message || r.error_kind || ''
}
onMounted(refresh)

const pivoted = computed(() => {
  // Map: method → subset → { 'recall@1': v, 'recall@3': v, ... }
  const out: Record<string, Record<string, Record<string, any>>> = {}
  for (const r of rows.value) {
    out[r.method] ??= {}
    out[r.method][r.subset] ??= {}
    out[r.method][r.subset][r.metric] = r
  }
  return out
})
const subsets = computed(() => {
  const s = new Set<string>()
  for (const r of rows.value) s.add(r.subset)
  return Array.from(s).sort()
})
const methods = computed(() => Object.keys(pivoted.value).sort())
</script>

<template>
  <div class="page">
    <h1>排行榜</h1>
    <p>每 (方法, 子集, 指标) 取所有 run 中最高值。</p>
    <button @click="refresh">刷新</button>
    <div v-if="errMsg" class="err">{{ errMsg }}</div>
    <table v-else>
      <thead>
        <tr>
          <th>方法</th>
          <th v-for="s in subsets" :key="s" colspan="2">{{ s }}</th>
        </tr>
        <tr>
          <th></th>
          <template v-for="s in subsets" :key="s">
            <th>R@1</th><th>R@3</th>
          </template>
        </tr>
      </thead>
      <tbody>
        <tr v-for="m in methods" :key="m">
          <td>{{ m }}</td>
          <template v-for="s in subsets" :key="s">
            <td>{{ pivoted[m][s]?.['recall@1']?.value?.toFixed(3) ?? '—' }}</td>
            <td>{{ pivoted[m][s]?.['recall@3']?.value?.toFixed(3) ?? '—' }}</td>
          </template>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.page { padding: 24px; }
table { width: 100%; border-collapse: collapse; margin-top: 16px; }
th, td { border-bottom: 1px solid #2a2f36; padding: 6px 10px; text-align: left; }
.err { color: #f87171; }
</style>
```

- [ ] **Step 6: Run Detail view**

```vue
<!-- frontend/src/views/sota/SotaRunDetailView.vue -->
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getRun, cancelRun } from '../../api/sota'

const route = useRoute()
const id = route.params.id as string
const run = ref<any>(null)
const errMsg = ref('')
let timer: any = null

async function refresh() {
  const r = await getRun(id)
  if (r.ok) run.value = r.run
  else errMsg.value = r.message || r.error_kind || ''
}

async function doCancel() {
  await cancelRun(id)
  await refresh()
}

onMounted(async () => {
  await refresh()
  timer = setInterval(() => {
    if (run.value && ['running', 'queued'].includes(run.value.status)) refresh()
  }, 2000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="page" v-if="run">
    <h1>Run {{ run.id }} — {{ run.status }}</h1>
    <button v-if="['running','queued'].includes(run.status)" @click="doCancel">取消</button>
    <h3>配置</h3>
    <pre>{{ JSON.stringify(run.config, null, 2) }}</pre>
    <h3>方法状态</h3>
    <table>
      <thead><tr><th>方法</th><th>状态</th><th>耗时(ms)</th><th>错误类型</th></tr></thead>
      <tbody>
        <tr v-for="m in run.methods" :key="m.method">
          <td>{{ m.method }}</td>
          <td>{{ m.status }}</td>
          <td>{{ m.duration_ms }}</td>
          <td>{{ m.error_kind || '—' }}</td>
        </tr>
      </tbody>
    </table>
    <h3>指标</h3>
    <table>
      <thead><tr><th>方法</th><th>子集</th><th>指标</th><th>值</th><th>CI</th><th>n</th></tr></thead>
      <tbody>
        <tr v-for="(c, i) in run.metrics" :key="i">
          <td>{{ c.method }}</td>
          <td>{{ c.subset }}</td>
          <td>{{ c.metric }}</td>
          <td>{{ c.value.toFixed(3) }}</td>
          <td v-if="c.ci_low != null">[{{ c.ci_low.toFixed(2) }}, {{ c.ci_high.toFixed(2) }}]</td>
          <td v-else>—</td>
          <td>{{ c.n_queries }}</td>
        </tr>
      </tbody>
    </table>
  </div>
  <div v-else-if="errMsg" class="err">{{ errMsg }}</div>
  <div v-else>加载中…</div>
</template>

<style scoped>
.page { padding: 24px; }
table { width: 100%; border-collapse: collapse; margin-top: 16px; }
th, td { border-bottom: 1px solid #2a2f36; padding: 6px 10px; text-align: left; }
pre { background: #0f1217; padding: 12px; border-radius: 6px; }
.err { color: #f87171; }
</style>
```

- [ ] **Step 7: Router + sidebar**

```typescript
// frontend/src/router/index.ts — append before closing of `routes` array
{ path: '/sota/datasets',     name: 'SotaDatasets',     component: () => import('../views/sota/SotaDatasetsView.vue') },
{ path: '/sota/methods',      name: 'SotaMethods',      component: () => import('../views/sota/SotaMethodsView.vue') },
{ path: '/sota/run',          name: 'SotaRunStudio',    component: () => import('../views/sota/SotaRunStudioView.vue') },
{ path: '/sota/leaderboard',  name: 'SotaLeaderboard',  component: () => import('../views/sota/SotaLeaderboardView.vue') },
{ path: '/sota/runs/:id',     name: 'SotaRunDetail',    component: () => import('../views/sota/SotaRunDetailView.vue') },
```

```vue
<!-- frontend/src/layout/SideBar.vue — append a new group inside the `groups` array -->
{
  label: 'SOTA 实验',
  items: [
    { path: '/sota/datasets',    label: 'VisDoM 数据集', icon: 'archive',  chap: 'S0' },
    { path: '/sota/methods',     label: '方法库',        icon: 'flask',    chap: 'S1' },
    { path: '/sota/run',         label: '实验台',        icon: 'sparkles', chap: 'S2' },
    { path: '/sota/leaderboard', label: '排行榜',        icon: 'gauge',    chap: 'S3' },
  ],
},
```

(Run Detail is reached via redirect from Run Studio after `createRun` returns; no sidebar entry needed.)

- [ ] **Step 8: Verify frontend compiles**

```bash
cd frontend && npm run build
```
Expected: `vite build` succeeds with no TS errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/api/sota.ts frontend/src/views/sota frontend/src/router/index.ts frontend/src/layout/SideBar.vue
git commit -m "feat(sota): frontend SOTA sidebar group + 5 views"
```

---

## Task 11: Smoke E2E (Server Up + Click Through)

- [ ] **Step 1: Start backend (already running per user)**

Verify with:
```bash
curl -s http://localhost:8080/api/sota/health | head -c 500
```
Expected: JSON `{"ok":true,"indexers":{...},"methods":["baseline_colpali","baseline_bm25","baseline_rrf"]}`.

- [ ] **Step 2: Verify dataset endpoint**

```bash
curl -s http://localhost:8080/api/sota/datasets | head -c 500
```
Expected: 4 subsets each with status `missing` (data not yet pulled — that's Task 12).

- [ ] **Step 3: Verify a no-op run is rejected without dataset**

```bash
curl -s -X POST http://localhost:8080/api/sota/runs -H "Content-Type: application/json" \
  -d '{"subsets":["fetatab"],"methods":["baseline_bm25"],"n_queries_per_subset":3}' | head -c 500
```
Expected: `{"ok":true,"run_id":"..."}`. Then GET `/api/sota/runs/<id>` shows status `failed` with errors logged because no queries.jsonl exists yet — system survives instead of 500-ing.

---

## Task 12: Pull VisDoMBench Metadata via SFTP (One-Off)

VisDoM-main on remote server has each subset's `queries.jsonl` somewhere under `/root/autodl-tmp/liboze/data/VisDoM-main/`. We pull these (small) once.

**Files:**
- Create: `scripts/pull_visdom_metadata.py`
- (Read-only): existing SSH config in `config/default.yaml`

- [ ] **Step 1: Write the puller**

```python
# scripts/pull_visdom_metadata.py
"""One-off: SFTP-pull VisDoMBench queries.jsonl files from remote server.

Discovers per-subset jsonl files under VISDOM_REMOTE/data/<subset>/.
Saves them to data/sota_runs/datasets/<subset>/queries.jsonl.

Idempotent: if local file exists and is non-empty, skips by default
(use --force to refresh).
"""
import argparse
import os
import sys

import paramiko
import yaml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/default.yaml")
    ap.add_argument("--out", default="data/sota_runs/datasets")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    server = cfg["ssh_servers"][0]
    deploy = server.get("deployment", {})
    visdom_remote = deploy.get("visdom_data")
    if not visdom_remote:
        print("no visdom_data path in config", file=sys.stderr); sys.exit(1)

    pwd = os.environ.get("SSH_PRIMARY_PASSWORD") or server["target_password"]
    if pwd.startswith("${"):
        # not interpolated → user must export
        print("SSH_PRIMARY_PASSWORD not set", file=sys.stderr); sys.exit(1)

    transport = paramiko.Transport((server["target_host"], server["target_port"]))
    transport.connect(username=server["target_user"], password=pwd)
    sftp = paramiko.SFTPClient.from_transport(transport)

    subsets = ("fetatab", "mmlongbench", "papertab", "slidevqa")
    os.makedirs(args.out, exist_ok=True)
    for s in subsets:
        local_dir = os.path.join(args.out, s)
        os.makedirs(local_dir, exist_ok=True)
        local_file = os.path.join(local_dir, "queries.jsonl")
        if os.path.exists(local_file) and os.path.getsize(local_file) > 0 and not args.force:
            print(f"[skip] {s} (already cached)"); continue
        # Try common layouts
        candidates = [
            f"{visdom_remote}/data/{s}/queries.jsonl",
            f"{visdom_remote}/{s}/queries.jsonl",
            f"{visdom_remote}/data/{s}.jsonl",
        ]
        pulled = False
        for remote in candidates:
            try:
                sftp.get(remote, local_file)
                size = os.path.getsize(local_file)
                print(f"[ok] {s} ← {remote} ({size} bytes)")
                pulled = True; break
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"[warn] {s}: {remote}: {e}")
                continue
        if not pulled:
            print(f"[miss] {s}: tried {candidates}")
    sftp.close(); transport.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

```bash
SSH_PRIMARY_PASSWORD=ZMdokPlGrCJa python scripts/pull_visdom_metadata.py
```
Expected: at least one `[ok]` line per subset; failures are logged but the script keeps going. If a subset's metadata is in a non-standard location on the remote box, we discover the actual path interactively in Task 13.

- [ ] **Step 3: Re-check dataset endpoint**

```bash
curl -s http://localhost:8080/api/sota/datasets
```
Expected: at least one subset with `status: ok` and `query_count > 0`.

- [ ] **Step 4: Commit**

```bash
git add scripts/pull_visdom_metadata.py
git commit -m "scripts(sota): one-off VisDoMBench metadata SFTP puller"
```

---

## Task 13: First Real Run (Quick / 50 per subset)

- [ ] **Step 1: From the SOTA Run Studio, launch Quick × all 4 subsets × 3 baselines**

Confirm via the UI:
- Datasets view: ≥1 subset OK
- Run Studio: subsets + methods auto-checked, click Launch
- Run Detail: status transitions QUEUED → RUNNING → COMPLETED/PARTIAL
- Leaderboard: 3 methods × N subsets × 4 metrics rows appear

- [ ] **Step 2: Inspect logs**

```bash
tail -50 data/sota_runs/<run_id>/queries.jsonl
tail -50 data/sota_runs/<run_id>/errors.jsonl
```

- [ ] **Step 3: Capture the result table**

Save the run's metrics to a markdown report:

```bash
mkdir -p docs/sota_results
python -c "
import asyncio
from backend.sota.runs import RunRegistry
async def main():
    reg = RunRegistry('data/sota_runs')
    rows = await reg.list_runs(limit=1)
    r = rows[0]
    print('# Phase 0 Baseline Run', r.id)
    print('Status:', r.status.value)
    print('| method | subset | recall@1 | recall@3 | mrr | n |')
    print('|---|---|---|---|---|---|')
    for m in r.metrics:
        if m.metric in ('recall@1','recall@3','mrr'):
            print(f'| {m.method} | {m.subset} | {m.value:.3f} | — | — | {m.n_queries} |')
asyncio.run(main())
" > docs/sota_results/phase-0-baseline.md
```

- [ ] **Step 4: Commit results**

```bash
git add docs/sota_results/phase-0-baseline.md
git commit -m "docs(sota): Phase 0 baseline result table"
```

---

## Self-Review Checklist (run before handoff)

- [x] Spec coverage: every numbered section in the design doc is covered by at least one task above (architecture, data flow, modules, frontend, eval schema, robustness, integrity).
- [x] Placeholder scan: no TBD/TODO/"add appropriate error handling" — every code step shows the actual code.
- [x] Type consistency: `MethodMeta`, `MethodContext`, `RunConfig`, `MetricCell`, `RunStatus` are defined in Tasks 2 and 5 and used identically in 8/9.
- [x] Robustness: every route is `@wrap_response`-decorated; executor has 3-tier timeouts + circuit breaker; frontend renders error envelopes inline rather than blanking.
- [x] Academic integrity: methods receive `SotaQuery` without `gold_pages` exposed via context; registry rejects `uses_test_labels=True`.

---

## Phase Exit Criteria

- All 11 backend tests pass.
- Frontend builds with no TS errors.
- `/api/sota/health` returns 200 ok.
- A real Quick run completes (status COMPLETED or PARTIAL) on at least one subset with at least one method producing non-zero `recall@1`.
- Result table written to `docs/sota_results/phase-0-baseline.md`.

When all five hold, Phase 0 is done; proceed to write the Phase 1 plan (multi-encoder ensemble).
