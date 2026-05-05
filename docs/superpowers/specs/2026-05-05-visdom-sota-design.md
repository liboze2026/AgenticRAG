# VisDoMBench Page-Retrieval SOTA — Design Spec

**Date:** 2026-05-05
**Author:** liboze
**Status:** Approved (user delegated full autonomy)
**Target:** Page-level Recall@1 / Recall@3 SOTA on VisDoMBench (4 subsets: FetaTab, MMLongBench, PaperTab, SlideVQA)

## 0. Goal & Non-Goals

**Goal.** Beat the published VisDoMRAG retrieval numbers (Suri et al. 2025, Table 4) on every subset of VisDoMBench, measured by page-level Recall@1 and Recall@3 over the held-out test split. Iterate methods until SOTA is achieved or compute is exhausted; record every run.

**Non-Goals.**
- End-to-end QA accuracy (out of scope per user direction; only retrieval).
- Model training beyond LoRA-tier light fine-tuning on the official train split.
- Removal or modification of any existing `backend/lab/*` or `/api/query` functionality.

## 1. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Frontend: new sidebar group "SOTA 实验"                      │
│   ├─ Datasets    (VisDoM 4-subset health-check + index)      │
│   ├─ Methods     (method library; toggleable cards)          │
│   ├─ Run Studio  (build + launch a run)                      │
│   ├─ Leaderboard (cross-run comparison table)                │
│   └─ Run Detail  (config + per-query + error cases + plots)  │
├─────────────────────────────────────────────────────────────┤
│ HTTP: /api/sota/*  (independent of /api/lab/*  and /api/query)│
├─────────────────────────────────────────────────────────────┤
│ Backend: backend/sota/                                       │
│   datasets.py    VisDoM loader + integrity self-check        │
│   indexers.py    pluggable encoders (ColPali, ColQwen2.5,    │
│                  jina-clip-v2, DSE)                          │
│   methods/       one method per file                         │
│       baseline_colpali.py                                    │
│       baseline_bm25.py                                       │
│       baseline_rrf.py                                        │
│       ensemble_multi.py     (multi-encoder + weighted RRF)   │
│       learned_fusion.py     (LoRA-tier MLP head)             │
│       vlm_rerank.py         (small VLM judge)                │
│       prf_xmodal.py         (cross-modal pseudo-relevance)   │
│       qrouter.py            (zero-shot query-type routing)   │
│       graph_prop.py         (candidate graph propagation)    │
│       lora_colpali.py       (light encoder fine-tune)        │
│   eval.py        Recall@1/@3 + bootstrap CI + per-query log  │
│   runs.py        run registry: JSONL + SQLite                │
│   service.py     DI container (reuses lab BM25/region read-only)│
│   routes.py      HTTP entry; all errors caught + 200-wrapped │
├─────────────────────────────────────────────────────────────┤
│ Reuse (read-only) from backend/lab/:                         │
│   hybrid.LabHybridService.bm25_index_for_dataset             │
│   region.LabRegionService.crop_and_encode (when needed)      │
│   graph.* (similarity-graph construction)                    │
└─────────────────────────────────────────────────────────────┘
```

**Boundary rules.**
1. Every `/api/sota/*` handler returns HTTP 200 with `{ok, error_kind?, message?}`. No 4xx/5xx leaves the package — frontend never blanks.
2. Each method is an independent module exposing one async function `run(query, candidates, ctx) -> List[ScoredHit]`. A single-method failure marks that method's slice of the run `partial`; sibling methods continue.
3. Encoders / models are loaded lazily; failed model-load falls back to next encoder per the run's `encoder_priority` list.
4. `data/sota_runs/` is the only write target for SOTA work; never writes to `data/uploads/`, `data/cache/`, or any lab path.

## 2. Data Flow

```
[User clicks "Launch Run" on Run Studio]
        │
        ▼
POST /api/sota/runs                   ─→  runs.py creates run row, returns run_id
        │
        ▼ (background task)
        ▼
1. datasets.load(subset)             — yields Iterable[Query] + DocumentSet
2. indexers.ensure(encoder, doc_set) — idempotent index build per (encoder, subset)
3. methods.<name>.run(query, ctx)    — yields top-N hits per query
4. eval.score(hits, gold)            — Recall@1, Recall@3, MRR, per-query trace
5. runs.persist(run_id, results)     — JSONL append + SQLite upsert
        │
        ▼
GET /api/sota/runs/{run_id}          — frontend polls; renders progress + results
```

**Concurrency model.**
- One run = one background task; runs are serialized per encoder to avoid GPU contention.
- Per-query timeout 60s. Per-method timeout 30 min. Per-run hard cap 6 h (configurable).
- If the SSH tunnel drops mid-run, the run is paused (status `paused_tunnel_down`), worker reconnects via existing `qdrant_resilient` infra; resumes from last checkpoint.

## 3. Backend Module Breakdown

### 3.1 `datasets.py`
- Reads VisDoM data from `/root/autodl-tmp/liboze/data/VisDoM-main` via worker (image data sits on remote box).
- Self-check: file count + sha256 manifest of expected files; emits `health: {fetatab: ok, slidevqa: missing_pdfs[3], ...}`.
- Caches a manifest at `data/sota_runs/dataset_manifest.json` so re-runs skip re-download.
- Exports `iter_queries(subset, split)` + `iter_documents(subset)`.

### 3.2 `indexers.py`
- `BaseIndexer` interface: `build(subset)`, `query(query_text|image, top_k)`, `health()`.
- Concrete: `ColPaliIndexer` (reuses existing worker), `ColQwen2Indexer` (new), `JinaCLIPv2Indexer` (new), `DSEIndexer` (new).
- All indexes live under `data/sota_runs/index/<encoder>/<subset>/`.
- Lazy: a method requesting an index triggers a build if absent; build is idempotent (manifest hash check).

### 3.3 `methods/`
Each file exposes:
```python
async def run(query: SotaQuery, ctx: MethodContext) -> List[Hit]: ...
METHOD_META = {"name": ..., "version": ..., "needs": [...], "uses_test_labels": False}
```
`uses_test_labels` is checked at registry load — any method that flips it true raises an academic-integrity error.

### 3.4 `eval.py`
- Computes Recall@1, Recall@3, MRR, Hit@1.
- 95% bootstrap CI over per-query metrics (1000 resamples).
- Emits per-query JSONL: `{query_id, gold_pages, ranked_pages, hit_at_1, hit_at_3, rr, latency_ms, error?}`.

### 3.5 `runs.py`
- SQLite `data/sota_runs/runs.db` tables: `runs`, `methods`, `metrics`, `errors`.
- JSONL mirror at `data/sota_runs/<run_id>/*.jsonl` for append-only audit.
- Functions: `create_run`, `append_result`, `mark_method_status`, `list_runs`, `get_run`, `compare_runs`.

### 3.6 `service.py`
Holds: dataset registry, indexer registry, method registry, runs DAO. Wired in `backend/main.py` lifespan alongside the existing lab bundle. Read-only references to lab services (BM25 index path, region service) so they can be inspected but never mutated.

### 3.7 `routes.py`
Endpoints (all idempotent + 200-wrapped):
- `GET  /api/sota/health`                 — package health
- `GET  /api/sota/datasets`               — list subsets + integrity status
- `POST /api/sota/datasets/{subset}/check`— re-run integrity check
- `GET  /api/sota/methods`                — list registered methods + meta
- `POST /api/sota/runs`                   — create + start a run
- `GET  /api/sota/runs`                   — list runs
- `GET  /api/sota/runs/{id}`              — run detail + per-method status
- `GET  /api/sota/runs/{id}/queries`      — paginated per-query trace
- `GET  /api/sota/runs/{id}/errors`       — error log
- `GET  /api/sota/leaderboard`            — best run per (subset, method) pair

## 4. Frontend

New sidebar group "SOTA 实验" (after the existing "Lab 实验" group). All views live under `frontend/src/views/sota/`.

| View | Path | Component | Purpose |
|---|---|---|---|
| Datasets | `/sota/datasets` | `SotaDatasetsView.vue` | 4-subset cards w/ health badge + "Check / Index" buttons |
| Methods | `/sota/methods` | `SotaMethodsView.vue` | Cards: name, version, requires, status |
| Run Studio | `/sota/run` | `SotaRunStudioView.vue` | Form: subsets ☑ × methods ☑ × top-k × scale (50/200/full) |
| Leaderboard | `/sota/leaderboard` | `SotaLeaderboardView.vue` | Pivot: method × subset → Recall@1 / @3 + CI |
| Run Detail | `/sota/runs/:id` | `SotaRunDetailView.vue` | Config + progress + per-query table + error gallery |

Reusable subcomponents under `frontend/src/components/sota/`: `RecallTable.vue`, `MethodCard.vue`, `RunProgress.vue`, `QueryTrace.vue`, `ErrorGallery.vue`.

Sidebar entry added to `SideBar.vue` only (no rewrite). Existing groups untouched.

## 5. Eval Schema + Persistence

**SQLite schema.**
```sql
CREATE TABLE runs (
  id TEXT PRIMARY KEY,
  created_at INTEGER NOT NULL,
  status TEXT NOT NULL,        -- queued|running|completed|partial|failed|cancelled
  config_json TEXT NOT NULL,
  duration_ms INTEGER,
  notes TEXT
);
CREATE TABLE methods (
  run_id TEXT,
  method_name TEXT,
  status TEXT,                  -- ok|partial|failed|skipped
  duration_ms INTEGER,
  error_kind TEXT,
  PRIMARY KEY (run_id, method_name)
);
CREATE TABLE metrics (
  run_id TEXT,
  method_name TEXT,
  subset TEXT,
  metric TEXT,                  -- recall@1|recall@3|mrr|hit@1
  value REAL,
  ci_low REAL,
  ci_high REAL,
  n_queries INTEGER,
  PRIMARY KEY (run_id, method_name, subset, metric)
);
CREATE TABLE errors (
  run_id TEXT,
  method_name TEXT,
  query_id TEXT,
  kind TEXT,
  message TEXT,
  ts INTEGER
);
```

**JSONL files** (append-only, per run):
- `config.json` — full request config + git sha
- `queries.jsonl` — one line per (query, method) result
- `errors.jsonl` — one line per error event
- `summary.json` — final aggregated metrics (written once on run finalize)

## 6. Robustness Strategy

1. **Error envelope.** All routes use `wrap_response(handler)` decorator: catches `Exception`, logs full traceback to `errors.jsonl`, returns `{ok: false, error_kind: <class>, message: <safe>}` with HTTP 200.
2. **Partial-success runs.** A run with N methods and M subsets has N×M cells; each cell's status is independent. Frontend shows a heatmap, not a single pass/fail badge.
3. **Tunnel resilience.** Existing `qdrant_resilient` + `worker_client` retry policies are reused as-is. SOTA package adds a per-cell circuit-breaker: if the same encoder fails 3 cells in a row, the encoder is muted for the remainder of the run with status `circuit_open`.
4. **Live-demo guards.**
   - Buttons that launch a run show estimated cost (queries × methods × est_latency).
   - Cancel button on every running run; cancellation is cooperative (each method checks `ctx.cancelled` between queries).
   - Presets: `Quick (50/subset)`, `Standard (200/subset)`, `Full (test split)`.
5. **Schema migrations.** SQLite version pragma; if version < current, run `migrations/00X.sql` on startup.
6. **Memory bounds.** Per-method memory cap 4 GB (process-level via `resource.setrlimit` on Linux worker). Encoder caches use bounded LRU.

## 7. Experiment Roadmap

Each phase ends with a logged run + a frontend leaderboard entry. Move to next phase when the previous phase's small-scale (50/subset) run is green.

| Phase | Method | Hypothesis | Go/No-Go |
|---|---|---|---|
| 0 | Dataset integrity + 3 baselines (ColPali / BM25 / RRF) | Baselines reproduce within ±1 pt of literature | Required to unlock 1 |
| 1 | Multi-encoder ensemble (ColPali ⊕ ColQwen2.5 ⊕ jina-clip-v2 ⊕ DSE) + weighted RRF | Ensemble beats best-single by ≥ +2 Recall@1 on every subset | Required to unlock 2 |
| 2 | Learned fusion head (small MLP on score features, trained on VisDoM train split, no test leakage) | +1 over RRF ensemble | If +1 → keep; else fall back to RRF |
| 3 | VLM-as-Judge top-k rerank (small VLM, top-20 → top-3) | +2 Recall@1 vs phase 2 | Latency must stay < 1 s/query |
| 4 | Cross-modal pseudo-relevance feedback (top-1 OCR → query expansion → re-retrieve) | +1 Recall@3 (esp. on MMLongBench) | If diminishing return on FetaTab/SlideVQA, restrict to long-doc subsets |
| 5 | Zero-shot query-type router (LLM classifier picks channel weights) | +0.5–1 across subsets | Low-cost gain, always enabled if non-negative |
| 6 | Candidate-page graph propagation (similarity graph over top-50, PageRank-style) | +0.5–1 on cross-page-evidence subsets | Drop if neutral |
| 7 | LoRA fine-tune of best encoder on VisDoM train | +2 Recall@1 ceiling lift | Only if phases 1-6 still under SOTA |

After every phase: re-run small (50/subset), commit results to leaderboard, decide next phase from data.

**SOTA reference numbers** are pinned in `docs/sota_baseline_numbers.md` (filled in Phase 0).

## 8. Academic Integrity

- Test labels are hidden behind `iter_queries(subset, split="test")` returning queries only; gold pages are loaded into a separate evaluator scope and never returned to method modules.
- `methods/<x>.METHOD_META["uses_test_labels"]` defaults to `False`; the registry rejects modules where this is `True`.
- Every published run records: git sha, encoder versions, dataset manifest sha, exact config. Re-running with the same config must reproduce within bootstrap CI.
- Origin attribution: each method docstring cites the paper it derives from (or "novel" if genuinely original).
- Comparison table shows: our run, paper-reported number, delta. No cherry-picking allowed (frontend always shows all methods, including losing ones).

## 9. Out of Scope

- End-to-end QA generation
- Re-ranking with proprietary closed APIs at scale (cost reasons; allowed only as one optional method)
- Multi-machine training
- Modifying `/api/query`, `/api/lab/*`, or any frontend route outside `frontend/src/views/sota/` and one new sidebar entry

---

**Self-review:** Reviewed inline; no TBDs/contradictions found. Scope is wide but decomposed into 7 phased subprojects, each independently shippable. Phase 0 alone is a viable thesis demo if later phases stall.
