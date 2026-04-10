from abc import ABC, abstractmethod
from typing import List
from backend.models.schemas import Embedding, PageImage


class BaseEncoder(ABC):
    @abstractmethod
    async def encode_documents(self, pages: List[PageImage]) -> List[Embedding]:
        ...

    @abstractmethod
    async def encode_query(self, query: str) -> List[List[float]]:
        ...
