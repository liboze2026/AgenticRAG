from typing import List, Optional

from backend.interfaces.retriever import BaseRetriever
from backend.models.schemas import RetrievalResult
from backend.strategies import retriever_registry


@retriever_registry.register("hybrid_rrf")
class HybridRRFRetriever(BaseRetriever):
    """Combine results from two retrievers via Reciprocal Rank Fusion.

    RRF score: sum over retrievers of 1/(k + rank).

    Both retrievers must be wired via DI as `dense_retriever` and `sparse_retriever`.
    The query string is passed through `last_query` (set by the pipeline before retrieve).
    Since BaseRetriever.retrieve only takes query_vectors, we use the convention that
    sparse retrievers expose a `retrieve_text(query, top_k)` method.
    """

    def __init__(
        self,
        dense_retriever: Optional[BaseRetriever] = None,
        sparse_retriever: Optional[BaseRetriever] = None,
        rrf_k: int = 60,
        candidates: int = 50,
    ):
        self.dense_retriever = dense_retriever
        self.sparse_retriever = sparse_retriever
        self.rrf_k = rrf_k
        self.candidates = candidates
        self._last_query: str = ""

    def set_query(self, query: str):
        self._last_query = query

    async def index(self, document_id: str, page_number: int, vectors, image_path: str, pdf_path=None, layout_metadata=None) -> None:
        if self.dense_retriever:
            await _safe_index(self.dense_retriever, document_id, page_number, vectors, image_path, pdf_path, layout_metadata)
        if self.sparse_retriever:
            await _safe_index(self.sparse_retriever, document_id, page_number, vectors, image_path, pdf_path, layout_metadata)

    async def retrieve(self, query_vectors, top_k: int = 5) -> List[RetrievalResult]:
        dense_results = []
        sparse_results = []
        if self.dense_retriever:
            dense_results = await self.dense_retriever.retrieve(query_vectors, top_k=self.candidates)
        if self.sparse_retriever and hasattr(self.sparse_retriever, "retrieve_text") and self._last_query:
            sparse_results = await self.sparse_retriever.retrieve_text(self._last_query, top_k=self.candidates)

        return _rrf_fuse(dense_results, sparse_results, k=self.rrf_k, top_k=top_k)

    async def delete(self, document_id: str) -> None:
        if self.dense_retriever:
            await self.dense_retriever.delete(document_id)
        if self.sparse_retriever:
            await self.sparse_retriever.delete(document_id)


async def _safe_index(retriever, document_id, page_number, vectors, image_path, pdf_path, layout_metadata=None):
    """Call retriever.index passing optional kwargs only when accepted."""
    import inspect
    sig = inspect.signature(retriever.index)
    kwargs = {"document_id": document_id, "page_number": page_number, "vectors": vectors, "image_path": image_path}
    if "pdf_path" in sig.parameters:
        kwargs["pdf_path"] = pdf_path
    if "layout_metadata" in sig.parameters:
        kwargs["layout_metadata"] = layout_metadata
    await retriever.index(**kwargs)


def _rrf_fuse(dense, sparse, k: int, top_k: int) -> List[RetrievalResult]:
    """Reciprocal Rank Fusion."""
    scores: dict = {}
    info: dict = {}
    for rank, r in enumerate(dense):
        key = (r.document_id, r.page_number)
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        info[key] = r
    for rank, r in enumerate(sparse):
        key = (r.document_id, r.page_number)
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        if key not in info:
            info[key] = r

    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [
        RetrievalResult(
            document_id=info[k_].document_id,
            page_number=info[k_].page_number,
            score=score,
            image_path=info[k_].image_path,
            layout=info[k_].layout,
        )
        for k_, score in fused
    ]
