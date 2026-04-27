from abc import ABC, abstractmethod
from typing import List
from backend.models.schemas import Answer, RetrievalResult


class BaseGenerator(ABC):
    @abstractmethod
    async def generate(self, query: str, context: List[RetrievalResult]) -> Answer:
        ...

    async def generate_chat(
        self,
        messages: List[dict],
        context: List[RetrievalResult],
    ) -> Answer:
        """Multi-turn chat generation. Default: extract last user message and call generate()."""
        last = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
        )
        return await self.generate(last, context)
