from abc import ABC, abstractmethod
from typing import List, Optional
from backend.models.schemas import PageLayout, RetrievalResult


class BaseRetriever(ABC):
    @abstractmethod
    async def retrieve(self, query_vectors: List[List[float]], top_k: int = 5) -> List[RetrievalResult]:
        ...

    @abstractmethod
    async def index(
        self,
        document_id: str,
        page_number: int,
        vectors: List[List[float]],
        image_path: str,
        layout_metadata: Optional[PageLayout] = None,
    ) -> None:
        ...

    @abstractmethod
    async def delete(self, document_id: str) -> None:
        ...
