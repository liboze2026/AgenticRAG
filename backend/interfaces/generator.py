from abc import ABC, abstractmethod
from typing import List
from backend.models.schemas import Answer, RetrievalResult


class BaseGenerator(ABC):
    @abstractmethod
    async def generate(self, query: str, context: List[RetrievalResult]) -> Answer:
        ...
