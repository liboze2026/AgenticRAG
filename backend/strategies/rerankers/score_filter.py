from typing import List

from backend.interfaces.reranker import BaseReranker
from backend.models.schemas import RetrievalResult
from backend.strategies import reranker_registry


@reranker_registry.register("score_filter")
class ScoreFilterReranker(BaseReranker):
    """Filter results below a score threshold, then truncate to top_k."""

    def __init__(self, threshold: float = 0.0):
        self.threshold = threshold

    async def rerank(self, query: str, results: List[RetrievalResult], top_k: int = 5) -> List[RetrievalResult]:
        filtered = [r for r in results if r.score >= self.threshold]
        return filtered[:top_k]
