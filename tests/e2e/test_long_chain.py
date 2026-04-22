"""E2E tests: full demo user flows combining all subsystems."""
import time
import pytest
from tests.e2e.conftest import wait_indexed

pytestmark = pytest.mark.e2e


def test_full_demo_path(client, minimal_pdf):
    """
    Full demo flow:
    upload → wait indexed → query → chat (3 turns) → experiment → cleanup
    No 5xx at any step.
    """
    # 1. Upload document
    r = client.post(
        "/api/documents/upload",
        files={"file": ("demo.pdf", minimal_pdf, "application/pdf")},
    )
    assert r.status_code == 200, f"Upload failed: {r.text}"
    doc_id = r.json()["id"]

    # 2. Wait for indexing
    doc = wait_indexed(client, doc_id)
    assert doc["status"] == "completed"

    # 3. Query
    r_query = client.post("/api/query", json={"query": "What is in this document?", "top_k": 3})
    assert r_query.status_code == 200, f"Query failed: {r_query.text}"
    answer_text = r_query.json()["answer"]
    assert len(answer_text) > 0

    # 4. Chat — 3 turns
    session_id = None
    turns = [
        "Tell me about this document.",
        "Can you give more detail?",
        "What are the key points?",
    ]
    for i, user_msg in enumerate(turns):
        if session_id is None:
            messages = [{"role": "user", "content": user_msg}]
        else:
            # append new user message (client manages history by sending full messages list)
            prev = client.get(f"/api/chat/sessions/{session_id}").json()["messages"]
            messages = [{"role": m["role"], "content": m["content"]} for m in prev]
            messages.append({"role": "user", "content": user_msg})

        body = {"messages": messages, "top_k": 3}
        if session_id:
            body["session_id"] = session_id

        r_chat = client.post("/api/chat", json=body)
        assert r_chat.status_code == 200, f"Chat turn {i+1} failed: {r_chat.text}"
        session_id = r_chat.json()["session_id"]

    # White-box: 6 messages stored
    r_sess = client.get(f"/api/chat/sessions/{session_id}")
    assert r_sess.status_code == 200
    assert len(r_sess.json()["messages"]) == 6

    # 5. Experiment evaluation
    r_eval = client.post(
        "/api/experiments/evaluate",
        json={
            "queries": [{"query": "test query", "relevant": [f"{doc_id}:1"]}],
            "top_k": 5,
            "note": "demo chain test",
        },
    )
    assert r_eval.status_code == 200, f"Eval failed: {r_eval.text}"
    exp_id = r_eval.json()["experiment_id"]

    # 6. Cleanup — all state cleared
    client.delete(f"/api/chat/sessions/{session_id}")
    client.delete(f"/api/documents/{doc_id}")
    client.delete(f"/api/experiments/{exp_id}")

    # Verify cleanup
    assert client.get(f"/api/documents/{doc_id}").status_code == 404
    assert client.get(f"/api/chat/sessions/{session_id}").status_code == 404
    assert client.get(f"/api/experiments/{exp_id}").status_code == 404


def test_multi_document_retrieval(client, minimal_pdf):
    """Upload 2 docs, query should return sources from at least 1 doc."""
    # Upload doc A
    rA = client.post(
        "/api/documents/upload",
        files={"file": ("doc_a.pdf", minimal_pdf, "application/pdf")},
    )
    assert rA.status_code == 200
    id_a = rA.json()["id"]

    # Upload doc B
    rB = client.post(
        "/api/documents/upload",
        files={"file": ("doc_b.pdf", minimal_pdf, "application/pdf")},
    )
    assert rB.status_code == 200
    id_b = rB.json()["id"]

    # Wait for both
    wait_indexed(client, id_a)
    wait_indexed(client, id_b)

    # Query — sources should exist
    r = client.post("/api/query", json={"query": "document content", "top_k": 5})
    assert r.status_code == 200
    sources = r.json()["sources"]
    assert len(sources) >= 1

    # Cleanup
    client.delete(f"/api/documents/{id_a}")
    client.delete(f"/api/documents/{id_b}")
