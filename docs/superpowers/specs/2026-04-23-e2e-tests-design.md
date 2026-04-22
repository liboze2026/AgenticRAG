# E2E Test Suite Design Spec
Date: 2026-04-23
Context: Master's thesis defense demo — Agentic RAG system full coverage

## Goal

Add a real-service end-to-end (e2e) test layer that exercises all API endpoints and simulates realistic user workflows. Tests hit live backend + worker + Qdrant — no stubs. Existing stub-based unit/integration tests are preserved unchanged.

## Architecture

Two-tier test structure:

```
tests/
  (existing stub tests — unchanged)
  test_integration.py
  backend/...
  worker/...

  e2e/                          ← NEW
    __init__.py
    conftest.py                 # fixtures: base_url, require_services, clean_docs, minimal_pdf
    test_document_flow.py       # upload → index → status → delete lifecycle
    test_query_flow.py          # query, retrieve, cache, empty-index
    test_chat_flow.py           # session create, multi-turn, history, delete
    test_experiment_flow.py     # eval queries, metrics, history, hard negatives
    test_long_chain.py          # full demo path combining all subsystems
    test_edge_cases.py          # error paths, boundary values, 4xx/5xx contracts
```

pytest.ini registers `e2e` marker. Run e2e: `pytest -m e2e`. Run fast only: `pytest -m "not e2e"`.

## conftest.py Design

### Service health gate
```python
@pytest.fixture(scope="session", autouse=True)
def require_services(base_url):
    try:
        r = httpx.get(f"{base_url}/api/health", timeout=10)
        health = r.json()
    except Exception:
        pytest.skip("Backend not reachable — start services before running e2e tests")
    if health.get("worker", {}).get("status") != "ok":
        pytest.skip("Worker not available")
    if health.get("qdrant", {}).get("status") != "ok":
        pytest.skip("Qdrant not available")
```

### Minimal valid PDF fixture
Generates a 1-page PDF in memory — no external file dependency.

### Polling helper
```python
async def wait_indexed(client, doc_id, timeout=120) -> dict:
    for _ in range(timeout):
        r = await client.get(f"/api/documents/{doc_id}/status")
        status = r.json()["status"]
        if status == "completed":
            return r.json()
        if status == "failed":
            pytest.fail(f"Document indexing failed: {r.json()}")
        await asyncio.sleep(1)
    pytest.fail("Document indexing timeout after 120s")
```

### Clean-up fixtures
- `clean_all_docs` (session scope): deletes all documents after the full e2e suite
- `clean_all_sessions` (session scope): deletes all chat sessions after suite
- `uploaded_doc` (module scope): uploads + indexes one document, shared across tests in a module

## Test Scenarios

### test_document_flow.py

| Test | Action | White-box assertion |
|------|--------|-------------------|
| `test_upload_returns_pending` | POST /api/documents/upload | status in (pending, indexing), id non-empty |
| `test_index_completes` | poll until indexed | status=completed, indexed_pages == total_pages |
| `test_list_contains_doc` | GET /api/documents | doc appears in list |
| `test_get_status_endpoint` | GET /api/documents/{id}/status | same as GET /api/documents/{id} |
| `test_delete_removes_doc` | DELETE then GET | 404 on get, not in list |
| `test_delete_nonexistent` | DELETE unknown id | 404 |
| `test_retry_queues_failed` | force status=failed then POST retry | status becomes queued/indexing |

### test_query_flow.py

| Test | Action | White-box assertion |
|------|--------|-------------------|
| `test_query_returns_answer` | POST /api/query | answer non-empty, sources ≥ 1, timing.total_ms > 0 |
| `test_retrieve_returns_results` | POST /api/retrieve | results non-empty, each has score ∈ (0,1] |
| `test_cache_hit_on_repeat` | same query twice | second response ≤ first response time OR cache_hit=true |
| `test_query_empty_index` | query before any upload | returns 200, answer may be empty but no 500 |
| `test_top_k_respected` | query top_k=1 | len(sources) ≤ 1 |

### test_chat_flow.py

| Test | Action | White-box assertion |
|------|--------|-------------------|
| `test_create_session_implicit` | POST /api/chat (no session_id) | response contains session_id |
| `test_session_persists_messages` | 3-turn conversation | GET session has 6 messages (3 user + 3 assistant) |
| `test_session_appears_in_list` | GET /api/chat/sessions | session_id present |
| `test_get_session_detail` | GET /api/chat/sessions/{id} | messages match what was sent |
| `test_delete_session` | DELETE then GET | 404 on get |
| `test_no_user_message_400` | POST /api/chat with only assistant messages | 400 |
| `test_document_scope_filter` | chat with document_ids=[specific_id] | sources only from that document |

### test_experiment_flow.py

| Test | Action | White-box assertion |
|------|--------|-------------------|
| `test_evaluate_returns_metrics` | POST /api/experiments/evaluate | recall_at_1 ≤ recall_at_5 ≤ recall_at_10, mrr ∈ [0,1] |
| `test_experiment_recorded_in_history` | evaluate then GET /api/experiments/history | experiment_id in history |
| `test_get_experiment_detail` | GET /api/experiments/{id} | pipeline_config and metrics present |
| `test_delete_experiment` | DELETE then GET | 404 |
| `test_hard_negatives_augment` | POST /api/experiments/hard_negatives | result has hard_negatives field |
| `test_metrics_monotone` | recall values | recall@1 ≤ recall@5 ≤ recall@10 always |

### test_long_chain.py

**Scenario: Full demo path**
```
upload doc → wait indexed → query (verify answer) →
create chat session → 3 turns → verify history →
run experiment → verify metrics → delete session →
delete doc → verify all cleaned up
```
- No 5xx at any step
- Final state: document list empty, session list empty, experiment recorded

**Scenario: Multi-document retrieval**
```
upload 2 docs → wait both indexed →
query that spans both → verify sources from ≥ 1 doc →
delete both
```

### test_edge_cases.py

| Test | Expected |
|------|---------|
| Upload 0-byte file | 400 or 422 |
| Upload text/plain file | 400 or 422 |
| GET /api/documents/nonexistent | 404 |
| GET /api/chat/sessions/nonexistent | 404 |
| POST /api/query with empty string | 200 or 422 (not 500) |
| POST /api/experiments/evaluate with 0 queries | graceful, total_queries=0 |
| Pipeline switch to invalid retriever | 400 or 422 |

## Bug Detection Focus

Known risky areas identified from code review:

1. **`generate_chat` fallback** — `BaseGenerator.generate_chat` has a default implementation, all three generators also override it. Not a bug — but multi-turn context is only used by Claude/OpenAI/Zhipu overrides. Test verifies assistant response uses conversation history, not just last message.

2. **Session/document_ids association** — `chat.py:38`: if session_id provided but session not found, a new session is created but uses the body's `document_ids`. The old session_id is lost. Test `test_session_id_reuse` will catch this.

3. **Background indexing race** — `documents.py:18`: status polling test catches if indexing completes with wrong `indexed_pages` count.

4. **Hard negatives eval_data type** — `experiments.py:150`: `body.eval_data` is `List[dict]` — augment_eval_set may expect specific keys. Test with minimal valid structure.

5. **Cache invalidation** — if same query returns cached result after document deletion, results will reference deleted documents.

## Constraints

- No new pip dependencies beyond `pytest`, `pytest-asyncio`, `httpx` (already in requirements)
- `BASE_URL` env var (default `http://localhost:8000`)
- Timeout for indexing: 120s (ColPali is slow)
- Tests must be idempotent: repeated runs leave system in same state
- All e2e tests marked `@pytest.mark.e2e`
