import asyncio
import base64
import logging
from typing import List

import httpx

logger = logging.getLogger(__name__)


# Retry on transient network/server errors, NOT on 4xx client errors
_RETRYABLE_HTTP_STATUS = {502, 503, 504}


class WorkerClient:
    """HTTP client for the remote ColPali worker, with automatic retry on
    connection drops and 5xx gateway errors. Retries use exponential backoff.
    """

    def __init__(
        self,
        host: str,
        port: int,
        timeout: int = 120,
        retry_attempts: int = 3,
        retry_backoff_sec: float = 0.5,
    ):
        self.base_url = f"http://{host}:{port}"
        # httpx HTTPTransport.retries handles only connection-establishment retries
        transport = httpx.AsyncHTTPTransport(retries=2)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            transport=transport,
        )
        self._retry_attempts = max(1, retry_attempts)
        self._retry_backoff_sec = max(0.0, retry_backoff_sec)

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Perform an HTTP request, retrying transient failures."""
        last_exc: Exception | None = None
        for attempt in range(1, self._retry_attempts + 1):
            try:
                response = await self._client.request(method, path, **kwargs)
                if response.status_code in _RETRYABLE_HTTP_STATUS and attempt < self._retry_attempts:
                    logger.warning(
                        "Worker %s %s -> %d, retrying (%d/%d)",
                        method, path, response.status_code, attempt, self._retry_attempts,
                    )
                    await asyncio.sleep(self._retry_backoff_sec * (2 ** (attempt - 1)))
                    continue
                response.raise_for_status()
                return response
            except (httpx.ConnectError, httpx.ReadError, httpx.WriteError,
                    httpx.RemoteProtocolError, httpx.PoolTimeout) as e:
                last_exc = e
                if attempt >= self._retry_attempts:
                    break
                delay = self._retry_backoff_sec * (2 ** (attempt - 1))
                logger.warning(
                    "Worker %s %s connection error: %s — retrying in %.1fs (%d/%d)",
                    method, path, e, delay, attempt, self._retry_attempts,
                )
                await asyncio.sleep(delay)
        # exhausted
        raise last_exc if last_exc else RuntimeError("worker request failed")

    async def encode_documents(self, image_paths: List[str]) -> List[dict]:
        images_b64 = []
        for p in image_paths:
            with open(p, "rb") as f:
                images_b64.append(base64.b64encode(f.read()).decode())
        response = await self._request("POST", "/encode/documents", json={"images_b64": images_b64})
        return response.json()["embeddings"]

    async def encode_query(self, query: str) -> List[List[float]]:
        response = await self._request("POST", "/encode/query", json={"query": query})
        return response.json()["vectors"]

    async def health(self) -> dict:
        # Health check uses a short timeout and a single attempt — callers
        # expect fast feedback, not a stalled response.
        response = await self._client.get("/health", timeout=5.0)
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self._client.aclose()
