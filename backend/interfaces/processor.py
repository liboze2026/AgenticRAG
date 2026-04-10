from abc import ABC, abstractmethod
from typing import List
from backend.models.schemas import PageImage


class BaseProcessor(ABC):
    @abstractmethod
    async def process(self, pdf_path: str, document_id: str) -> List[PageImage]:
        ...
