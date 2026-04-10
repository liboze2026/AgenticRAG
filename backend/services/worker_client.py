from typing import List
import httpx


class WorkerClient:
    def __init__(self, host: str, port: int, timeout: int = 120):
        self.base_url = f"http://{host}:{port}"
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(timeout))

    async def encode_documents(self, image_paths: List[str]) -> List[dict]:
        response = await self._client.post("/encode/documents", json={"image_paths": image_paths})
        response.raise_for_status()
        return response.json()["embeddings"]

    async def encode_query(self, query: str) -> List[List[float]]:
        response = await self._client.post("/encode/query", json={"query": query})
        response.raise_for_status()
        return response.json()["vectors"]

    async def health(self) -> dict:
        response = await self._client.get("/health")
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self._client.aclose()
