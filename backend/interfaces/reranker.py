from abc import ABC, abstractmethod
from typing import List
from backend.models.schemas import RetrievalResult


class BaseReranker(ABC):
    @abstractmethod
    async def rerank(self, query: str, results: List[RetrievalResult], top_k: int = 5) -> List[RetrievalResult]:
        ...
