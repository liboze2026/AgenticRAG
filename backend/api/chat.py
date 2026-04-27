"""Multi-turn chat API with RAG retrieval and provenance."""

import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.models.schemas import ChatMessage

router = APIRouter()


class ChatRequest(BaseModel):
    messages: List[dict]            # [{role, content}] full history from client
    document_ids: List[str] = []
    session_id: Optional[str] = None
    top_k: int = 5


class ChatResponse(BaseModel):
    message: dict                   # {role: "assistant", content: "..."}
    sources: List[dict]
    session_id: str
    timing: dict = {}


@router.post("/chat")
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    chat_service = request.app.state.chat_service
    pipeline = request.app.state.pipeline_manager.pipeline

    # Get or create session
    session = None
    if body.session_id:
        session = chat_service.get_session(body.session_id)
    if session is None:
        session = chat_service.create_session(body.document_ids)

    # Extract last user message for retrieval
    last_user_msg = next(
        (m for m in reversed(body.messages) if m.get("role") == "user"), None
    )
    if not last_user_msg:
        raise HTTPException(status_code=400, detail="No user message found in messages")

    # Retrieve relevant pages from the query
    t0 = time.perf_counter()
    try:
        bundle = await pipeline.retrieve(last_user_msg["content"], top_k=body.top_k)
    except Exception as exc:
        msg = str(exc)
        if "502" in msg or "503" in msg or "Connection refused" in msg:
            raise HTTPException(status_code=503, detail="Remote worker/Qdrant not available. Check SSH tunnel.")
        raise HTTPException(status_code=500, detail=msg)

    # Filter by document scope if specified
    results = bundle.results
    if body.document_ids:
        results = [r for r in results if r.document_id in body.document_ids]

    # Generate answer with full conversation history
    try:
        answer = await pipeline.generator.generate_chat(
            messages=body.messages,
            context=results,
        )
    except Exception as exc:
        msg = str(exc)
        raise HTTPException(status_code=503, detail=f"Generation failed: {msg}")
    timing = dict(bundle.timing)
    timing["generate_ms"] = (time.perf_counter() - t0) * 1000 - timing.get("total_ms", 0)
    timing["total_ms"] = (time.perf_counter() - t0) * 1000

    # Persist both turns to session
    user_msg = ChatMessage(role="user", content=last_user_msg["content"])
    assistant_msg = ChatMessage(
        role="assistant",
        content=answer.text,
        sources=results,
    )
    chat_service.append_message(session.session_id, user_msg)
    chat_service.append_message(session.session_id, assistant_msg)

    return ChatResponse(
        message={"role": "assistant", "content": answer.text},
        sources=[r.model_dump() for r in results],
        session_id=session.session_id,
        timing=timing,
    )


@router.get("/chat/sessions")
async def list_sessions(request: Request):
    chat_service = request.app.state.chat_service
    sessions = chat_service.list_sessions()
    return [s.model_dump() for s in sessions]


@router.get("/chat/sessions/{session_id}")
async def get_session(request: Request, session_id: str):
    chat_service = request.app.state.chat_service
    session = chat_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump()


@router.delete("/chat/sessions/{session_id}")
async def delete_session(request: Request, session_id: str):
    chat_service = request.app.state.chat_service
    chat_service.delete_session(session_id)
    return {"ok": True}
