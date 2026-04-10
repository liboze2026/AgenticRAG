import inspect
import time
from typing import Any, Dict, List, Optional

from backend.core.registry import Registry
from backend.interfaces import (
    BaseProcessor, BaseEncoder, BaseRetriever, BaseReranker, BaseGenerator,
)
from backend.models.schemas import Answer, PageImage, Embedding, RetrievalResult, RetrievalBundle


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
        # Inject pdf_path into each page (needed by text retrievers)
        for p in pages:
            if p.pdf_path is None:
                p.pdf_path = pdf_path
        embeddings = await self.document_encoder.encode_documents(pages)
        sig = inspect.signature(self.retriever.index)
        accepts_pdf = "pdf_path" in sig.parameters
        for page, emb in zip(pages, embeddings):
            kwargs = {
                "document_id": emb.document_id,
                "page_number": emb.page_number,
                "vectors": emb.vectors,
                "image_path": page.image_path,
            }
            if accepts_pdf:
                kwargs["pdf_path"] = pdf_path
            await self.retriever.index(**kwargs)
        return pages

    async def retrieve(self, query: str, top_k: int = 5) -> RetrievalBundle:
        timing = {}
        t0 = time.perf_counter()
        query_vectors = await self.query_encoder.encode_query(query)
        timing["encode_query_ms"] = (time.perf_counter() - t0) * 1000

        # Allow retrievers that need the raw query (e.g., hybrid) to receive it
        if hasattr(self.retriever, "set_query"):
            self.retriever.set_query(query)

        t1 = time.perf_counter()
        results = await self.retriever.retrieve(query_vectors, top_k=top_k)
        timing["retrieve_ms"] = (time.perf_counter() - t1) * 1000

        if self.reranker:
            t2 = time.perf_counter()
            results = await self.reranker.rerank(query, results, top_k=top_k)
            timing["rerank_ms"] = (time.perf_counter() - t2) * 1000

        timing["total_ms"] = (time.perf_counter() - t0) * 1000
        return RetrievalBundle(results=results, timing=timing)

    async def query(self, query: str, top_k: int = 5) -> Answer:
        t_start = time.perf_counter()
        bundle = await self.retrieve(query, top_k=top_k)
        t_gen = time.perf_counter()
        answer = await self.generator.generate(query, bundle.results)
        gen_ms = (time.perf_counter() - t_gen) * 1000
        total_ms = (time.perf_counter() - t_start) * 1000

        # Compose timing: include retrieval timings + generation
        merged_timing = dict(bundle.timing)
        merged_timing["generate_ms"] = gen_ms
        merged_timing["total_ms"] = total_ms
        answer.timing = merged_timing
        return answer

    def snapshot_config(self) -> dict:
        """Return the effective configuration of all strategies, including init params."""

        def snap(obj):
            if obj is None:
                return None
            cls_name = obj.__class__.__name__
            sig = inspect.signature(obj.__class__.__init__)
            options = {}
            for pname, _ in sig.parameters.items():
                if pname == "self":
                    continue
                if hasattr(obj, pname):
                    val = getattr(obj, pname)
                    # Only serialize JSON-safe primitives
                    if isinstance(val, (str, int, float, bool, list, dict, type(None))):
                        options[pname] = val
                    else:
                        options[pname] = repr(val)
            return {"class": cls_name, "options": options}

        return {
            "processor": snap(self.processor),
            "document_encoder": snap(self.document_encoder),
            "query_encoder": snap(self.query_encoder),
            "retriever": snap(self.retriever),
            "reranker": snap(self.reranker),
            "generator": snap(self.generator),
        }


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
