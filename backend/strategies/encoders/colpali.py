from typing import List
from backend.interfaces.encoder import BaseEncoder
from backend.models.schemas import Embedding, PageImage
from backend.services.worker_client import WorkerClient
from backend.strategies import document_encoder_registry, query_encoder_registry


@document_encoder_registry.register("colpali")
@query_encoder_registry.register("colpali")
class ColPaliEncoder(BaseEncoder):
    def __init__(self, worker_client: WorkerClient = None):
        self.worker_client = worker_client

    async def encode_documents(self, pages: List[PageImage]) -> List[Embedding]:
        image_paths = [p.image_path for p in pages]
        raw = await self.worker_client.encode_documents(image_paths)
        return [Embedding(document_id=r["document_id"], page_number=r["page_number"], vectors=r["vectors"]) for r in raw]

    async def encode_query(self, query: str) -> List[List[float]]:
        return await self.worker_client.encode_query(query)
