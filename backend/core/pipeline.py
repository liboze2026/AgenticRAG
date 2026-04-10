import inspect
from typing import Any, Dict, List, Optional

from backend.core.registry import Registry
from backend.interfaces import (
    BaseProcessor, BaseEncoder, BaseRetriever, BaseReranker, BaseGenerator,
)
from backend.models.schemas import Answer, PageImage, Embedding, RetrievalResult


def _parse_strategy_spec(value):
    """Parse a strategy spec which can be string or {name, options} dict."""
    if value is None:
        return None, {}
    if isinstance(value, str):
        return value, {}
    return value["name"], value.get("options", {})


def _instantiate(cls, options: Dict[str, Any], deps: Dict[str, Any]):
    """Instantiate cls passing only kwargs that match its __init__ signature.
    Options take priority over deps for the same parameter name."""
    sig = inspect.signature(cls.__init__)
    kwargs = {}
    for pname, _ in sig.parameters.items():
        if pname == "self":
            continue
        if pname in options:
            kwargs[pname] = options[pname]
        elif pname in deps:
            kwargs[pname] = deps[pname]
    return cls(**kwargs)


class Pipeline:
    def __init__(
        self,
        processor: BaseProcessor,
        document_encoder: BaseEncoder,
        query_encoder: BaseEncoder,
        retriever: BaseRetriever,
        reranker: Optional[BaseReranker],
        generator: BaseGenerator,
    ):
        self.processor = processor
        self.document_encoder = document_encoder
        self.query_encoder = query_encoder
        self.retriever = retriever
        self.reranker = reranker
        self.generator = generator

    @classmethod
    def from_config(cls, config: dict, registries: Dict[str, Registry], deps: Optional[Dict[str, Any]] = None) -> "Pipeline":
        deps = deps or {}

        def build(category: str, value):
            name, options = _parse_strategy_spec(value)
            if name is None:
                return None
            strategy_cls = registries[category].get(name)
            return _instantiate(strategy_cls, options, deps)

        return cls(
            processor=build("processor", config["processor"]),
            document_encoder=build("document_encoder", config["document_encoder"]),
            query_encoder=build("query_encoder", config["query_encoder"]),
            retriever=build("retriever", config["retriever"]),
            reranker=build("reranker", config.get("reranker")),
            generator=build("generator", config["generator"]),
        )

    async def index_document(self, pdf_path: str, document_id: str) -> List[PageImage]:
        pages = await self.processor.process(pdf_path, document_id)
        embeddings = await self.document_encoder.encode_documents(pages)
        for page, emb in zip(pages, embeddings):
            await self.retriever.index(
                document_id=emb.document_id, page_number=emb.page_number,
                vectors=emb.vectors, image_path=page.image_path,
            )
        return pages

    async def retrieve(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        query_vectors = await self.query_encoder.encode_query(query)
        results = await self.retriever.retrieve(query_vectors, top_k=top_k)
        if self.reranker:
            results = await self.reranker.rerank(query, results, top_k=top_k)
        return results

    async def query(self, query: str, top_k: int = 5) -> Answer:
        results = await self.retrieve(query, top_k=top_k)
        answer = await self.generator.generate(query, results)
        return answer


class PipelineManager:
    def __init__(self, registries: Dict[str, Registry], deps: Optional[Dict[str, Any]] = None):
        self.registries = registries
        self.deps = deps or {}
        self.pipeline: Optional[Pipeline] = None
        self._current_config: Optional[dict] = None

    def set_pipeline(self, config: dict) -> Pipeline:
        self.pipeline = Pipeline.from_config(config, self.registries, self.deps)
        self._current_config = config
        return self.pipeline

    def get_current_config(self) -> Optional[dict]:
        return self._current_config

    def list_available(self) -> Dict[str, List[str]]:
        return {name: reg.list() for name, reg in self.registries.items()}
