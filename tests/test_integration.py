"""Integration test: assemble a full pipeline with stubs, test end-to-end via API."""
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock

from backend.core.registry import Registry
from backend.core.pipeline import Pipeline, PipelineManager
from backend.services.document_service import DocumentService
from backend.main import create_app
from backend.interfaces import BaseProcessor, BaseEncoder, BaseRetriever, BaseGenerator
from backend.models.schemas import PageImage, Embedding, RetrievalResult, Answer


class StubProcessor(BaseProcessor):
    async def process(self, pdf_path, document_id):
        return [PageImage(document_id=document_id, page_number=1, image_path="/stub/p1.png")]


class StubEncoder(BaseEncoder):
    async def encode_documents(self, pages):
        return [Embedding(document_id=p.document_id, page_number=p.page_number, vectors=[[0.1]]) for p in pages]

    async def encode_query(self, query):
        return [[0.1]]


class StubRetriever(BaseRetriever):
    def __init__(self):
        self._store = []

    async def index(self, document_id, page_number, vectors, image_path):
        self._store.append({"document_id": document_id, "page_number": page_number, "image_path": image_path})

    async def retrieve(self, query_vectors, top_k=5):
        return [
            RetrievalResult(
                document_id=s["document_id"], page_number=s["page_number"],
                score=0.9, image_path=s["image_path"],
            )
            for s in self._store[:top_k]
        ]

    async def delete(self, document_id):
        self._store = [s for s in self._store if s["document_id"] != document_id]


class StubGenerator(BaseGenerator):
    async def generate(self, query, context):
        return Answer(text=f"Answer to: {query}", sources=context)


@pytest.fixture
def app_with_stubs(tmp_path):
    retriever = StubRetriever()
    pipeline = Pipeline(
        processor=StubProcessor(),
        document_encoder=StubEncoder(),
        query_encoder=StubEncoder(),
        retriever=retriever,
        reranker=None,
        generator=StubGenerator(),
    )

    registries = {
        "processor": Registry("processor"),
        "document_encoder": Registry("document_encoder"),
        "query_encoder": Registry("query_encoder"),
        "retriever": Registry("retriever"),
        "reranker": Registry("reranker"),
        "generator": Registry("generator"),
    }
    manager = PipelineManager(registries)
    manager.pipeline = pipeline
    manager._current_config = {
        "processor": "stub", "document_encoder": "stub",
        "query_encoder": "stub", "retriever": "stub",
        "reranker": None, "generator": "stub",
    }

    doc_service = DocumentService(upload_dir=str(tmp_path / "uploads"), pipeline=pipeline)

    mock_worker = MagicMock()
    mock_worker.health = AsyncMock(return_value={"status": "ok", "model": "stub"})

    return create_app(
        worker_client=mock_worker,
        pipeline_manager=manager,
        document_service=doc_service,
    )


@pytest.mark.asyncio
async def test_upload_and_query_flow(app_with_stubs):
    transport = ASGITransport(app=app_with_stubs)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Upload
        resp = await client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", b"%PDF fake", "application/pdf")},
        )
        assert resp.status_code == 200
        doc_id = resp.json()["id"]

        # Wait for background indexing
        await asyncio.sleep(0.2)

        # Query
        resp = await client.post("/api/query", json={"query": "what is this?", "top_k": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert "Answer to:" in data["answer"]
        assert len(data["sources"]) >= 1

        # Retrieve only
        resp = await client.post("/api/retrieve", json={"query": "test", "top_k": 3})
        assert resp.status_code == 200
        assert len(resp.json()["results"]) >= 1

        # Health
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["worker"]["status"] == "ok"

        # Pipelines
        resp = await client.get("/api/pipelines")
        assert resp.status_code == 200
        assert resp.json()["current"]["processor"] == "stub"

        # Documents list
        resp = await client.get("/api/documents")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
