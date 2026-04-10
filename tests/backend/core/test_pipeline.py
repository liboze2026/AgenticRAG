import pytest
from backend.core.pipeline import Pipeline, PipelineManager
from backend.core.registry import Registry
from backend.interfaces import BaseProcessor, BaseEncoder, BaseRetriever, BaseReranker, BaseGenerator
from backend.models.schemas import PageImage, Embedding, RetrievalResult, Answer


class FakeProcessor(BaseProcessor):
    async def process(self, pdf_path, document_id):
        return [PageImage(document_id=document_id, page_number=1, image_path="/fake/img.png")]


class FakeEncoder(BaseEncoder):
    async def encode_documents(self, pages):
        return [Embedding(document_id=p.document_id, page_number=p.page_number, vectors=[[0.1, 0.2]]) for p in pages]
    async def encode_query(self, query):
        return [[0.1, 0.2]]


class FakeRetriever(BaseRetriever):
    async def retrieve(self, query_vectors, top_k=5):
        return [RetrievalResult(document_id="doc1", page_number=1, score=0.95, image_path="/fake/img.png")]
    async def index(self, document_id, page_number, vectors, image_path):
        pass
    async def delete(self, document_id):
        pass


class FakeGenerator(BaseGenerator):
    async def generate(self, query, context):
        return Answer(text="fake answer", sources=context)


def _make_registries():
    processors = Registry("processor")
    doc_encoders = Registry("document_encoder")
    query_encoders = Registry("query_encoder")
    retrievers = Registry("retriever")
    rerankers = Registry("reranker")
    generators = Registry("generator")
    processors.register("fake")(FakeProcessor)
    doc_encoders.register("fake")(FakeEncoder)
    query_encoders.register("fake")(FakeEncoder)
    retrievers.register("fake")(FakeRetriever)
    generators.register("fake")(FakeGenerator)
    return {
        "processor": processors, "document_encoder": doc_encoders,
        "query_encoder": query_encoders, "retriever": retrievers,
        "reranker": rerankers, "generator": generators,
    }


def test_pipeline_assemble():
    registries = _make_registries()
    config = {"processor": "fake", "document_encoder": "fake", "query_encoder": "fake",
              "retriever": "fake", "reranker": None, "generator": "fake"}
    pipeline = Pipeline.from_config(config, registries)
    assert isinstance(pipeline.processor, FakeProcessor)
    assert isinstance(pipeline.generator, FakeGenerator)
    assert pipeline.reranker is None


@pytest.mark.asyncio
async def test_pipeline_query():
    registries = _make_registries()
    config = {"processor": "fake", "document_encoder": "fake", "query_encoder": "fake",
              "retriever": "fake", "reranker": None, "generator": "fake"}
    pipeline = Pipeline.from_config(config, registries)
    answer = await pipeline.query("test question", top_k=3)
    assert answer.text == "fake answer"
    assert len(answer.sources) == 1


@pytest.mark.asyncio
async def test_pipeline_retrieve_only():
    registries = _make_registries()
    config = {"processor": "fake", "document_encoder": "fake", "query_encoder": "fake",
              "retriever": "fake", "reranker": None, "generator": "fake"}
    pipeline = Pipeline.from_config(config, registries)
    results = await pipeline.retrieve("test question", top_k=3)
    assert len(results) == 1
    assert results[0].score == 0.95


def test_pipeline_manager_switch():
    registries = _make_registries()
    config = {"processor": "fake", "document_encoder": "fake", "query_encoder": "fake",
              "retriever": "fake", "reranker": None, "generator": "fake"}
    manager = PipelineManager(registries)
    manager.set_pipeline(config)
    assert manager.pipeline is not None
    available = manager.list_available()
    assert "processor" in available
    assert "fake" in available["processor"]
