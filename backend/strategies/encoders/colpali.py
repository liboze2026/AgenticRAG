from typing import List
from backend.interfaces.encoder import BaseEncoder
from backend.models.schemas import Embedding, PageImage
from backend.services.worker_client import WorkerClient
from backend.strategies import document_encoder_registry, query_encoder_registry


@document_encoder_registry.register("colpali")
@query_encoder_registry.register("colpali")
class ColPaliEncoder(BaseEncoder):
    def __init__(self, worker_client=None, batch_size: int = 8, model_name: str = "vidore/colpali-v1.2"):
        self.worker_client = worker_client
        self.batch_size = batch_size
        self.model_name = model_name

    async def encode_documents(self, pages: List[PageImage]) -> List[Embedding]:
        if not pages:
            return []
        embeddings = []
        for batch_start in range(0, len(pages), self.batch_size):
            batch = pages[batch_start:batch_start + self.batch_size]
            image_paths = [p.image_path for p in batch]
            raw = await self.worker_client.encode_documents(image_paths)
            for page, r in zip(batch, raw):
                embeddings.append(Embedding(
                    document_id=page.document_id,
                    page_number=page.page_number,
                    vectors=r["vectors"],
                ))
        return embeddings

    async def encode_query(self, query: str) -> List[List[float]]:
        return await self.worker_client.encode_query(query)
