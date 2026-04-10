import uuid
from typing import List
from qdrant_client import models
from backend.interfaces.retriever import BaseRetriever
from backend.models.schemas import RetrievalResult
from backend.strategies import retriever_registry


@retriever_registry.register("multi_vector")
class MultiVectorRetriever(BaseRetriever):
    def __init__(self, qdrant_client=None, collection_name: str = "documents"):
        self.client = qdrant_client
        self.collection_name = collection_name

    async def index(self, document_id: str, page_number: int, vectors: List[List[float]], image_path: str) -> None:
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{document_id}:{page_number}"))
        point = models.PointStruct(
            id=point_id, vector=vectors,
            payload={"document_id": document_id, "page_number": page_number, "image_path": image_path},
        )
        await self.client.upsert(collection_name=self.collection_name, points=[point])

    async def retrieve(self, query_vectors: List[List[float]], top_k: int = 5) -> List[RetrievalResult]:
        response = await self.client.query_points(
            collection_name=self.collection_name, query=query_vectors, limit=top_k, with_payload=True,
        )
        results = []
        for point in response.points:
            results.append(RetrievalResult(
                document_id=point.payload["document_id"], page_number=point.payload["page_number"],
                score=point.score, image_path=point.payload["image_path"],
            ))
        return results

    async def delete(self, document_id: str) -> None:
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(must=[
                    models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id))
                ])
            ),
        )
