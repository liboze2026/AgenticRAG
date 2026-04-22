"""E2E tests: chat session lifecycle, multi-turn conversation, session persistence."""
import pytest

pytestmark = pytest.mark.e2e


def _send(client, messages, session_id=None, top_k=3):
    body = {"messages": messages, "top_k": top_k}
    if session_id:
        body["session_id"] = session_id
    return client.post("/api/chat", json=body)


def test_chat_creates_session_id(client, indexed_doc):
    messages = [{"role": "user", "content": "What is in this document?"}]
    r = _send(client, messages)
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert len(data["session_id"]) > 0
    assert "message" in data
    assert data["message"]["role"] == "assistant"
    assert len(data["message"]["content"]) > 0
    # Cleanup
    client.delete(f"/api/chat/sessions/{data['session_id']}")


def test_multi_turn_chat_persists_messages(client, indexed_doc):
    # Turn 1
    msgs1 = [{"role": "user", "content": "Tell me about this document."}]
    r1 = _send(client, msgs1)
    assert r1.status_code == 200
    session_id = r1.json()["session_id"]

    # Turn 2 — pass full history so far
    msgs2 = [
        {"role": "user", "content": "Tell me about this document."},
        {"role": "assistant", "content": r1.json()["message"]["content"]},
        {"role": "user", "content": "Can you summarize?"},
    ]
    r2 = _send(client, msgs2, session_id=session_id)
    assert r2.status_code == 200
    assert r2.json()["session_id"] == session_id

    # Turn 3 — pass full history so far
    msgs3 = msgs2 + [
        {"role": "assistant", "content": r2.json()["message"]["content"]},
        {"role": "user", "content": "What keywords does it contain?"},
    ]
    r3 = _send(client, msgs3, session_id=session_id)
    assert r3.status_code == 200

    # White-box: session should have 6 messages (3 user + 3 assistant).
    # The backend appends exactly one user msg + one assistant msg per POST /api/chat call,
    # so 3 turns => 6 stored messages.
    r_session = client.get(f"/api/chat/sessions/{session_id}")
    assert r_session.status_code == 200
    session_data = r_session.json()
    messages_stored = session_data["messages"]
    assert len(messages_stored) == 6, f"Expected 6 messages, got {len(messages_stored)}"
    roles = [m["role"] for m in messages_stored]
    assert roles == ["user", "assistant", "user", "assistant", "user", "assistant"]

    client.delete(f"/api/chat/sessions/{session_id}")


def test_session_appears_in_list(client, indexed_doc):
    messages = [{"role": "user", "content": "Hello"}]
    r = _send(client, messages)
    assert r.status_code == 200
    session_id = r.json()["session_id"]

    r_list = client.get("/api/chat/sessions")
    assert r_list.status_code == 200
    session_ids = [s["session_id"] for s in r_list.json()]
    assert session_id in session_ids

    client.delete(f"/api/chat/sessions/{session_id}")


def test_get_session_detail(client, indexed_doc):
    messages = [{"role": "user", "content": "Detail test"}]
    r = _send(client, messages)
    session_id = r.json()["session_id"]

    r_detail = client.get(f"/api/chat/sessions/{session_id}")
    assert r_detail.status_code == 200
    data = r_detail.json()
    assert data["session_id"] == session_id
    assert "messages" in data
    assert "created_at" in data

    client.delete(f"/api/chat/sessions/{session_id}")


def test_delete_session(client, indexed_doc):
    messages = [{"role": "user", "content": "Delete test"}]
    r = _send(client, messages)
    session_id = r.json()["session_id"]

    del_r = client.delete(f"/api/chat/sessions/{session_id}")
    assert del_r.status_code == 200

    get_r = client.get(f"/api/chat/sessions/{session_id}")
    assert get_r.status_code == 404


def test_no_user_message_returns_400(client):
    messages = [{"role": "assistant", "content": "I said something"}]
    r = _send(client, messages)
    assert r.status_code == 400


def test_get_nonexistent_session_returns_404(client):
    r = client.get("/api/chat/sessions/nonexistent-session-xyz")
    assert r.status_code == 404
