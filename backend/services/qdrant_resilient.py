"""Resilient wrapper around AsyncQdrantClient.

Forwards every attribute access to the underlying client. For coroutine
methods, wraps the call in a retry loop with exponential backoff so transient
network drops (which are common when traffic flows through an SSH tunnel)
don't surface as fatal errors.
"""
import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.NetworkError, httpx.RemoteProtocolError,
                        httpx.PoolTimeout, ConnectionError, asyncio.TimeoutError)):
        return True
    # qdrant-client wraps transport errors in its own exception type
    name = type(exc).__name__
    if name in ("ResponseHandlingException", "ApiException"):
        return True
    msg = str(exc).lower()
    return ("connection" in msg and "refused" in msg) or "timeout" in msg


class ResilientAsyncQdrantClient:
    def __init__(self, inner: Any, retry_attempts: int = 3, retry_backoff_sec: float = 0.5):
        self._inner = inner
        self._retry = max(1, retry_attempts)
        self._backoff = max(0.0, retry_backoff_sec)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr
        if not asyncio.iscoroutinefunction(attr):
            return attr
        return self._wrap_coro(attr, name)

    def _wrap_coro(self, fn, name: str):
        retry = self._retry
        backoff = self._backoff

        async def wrapper(*args, **kwargs):
            last_exc: BaseException | None = None
            for attempt in range(1, retry + 1):
                try:
                    return await fn(*args, **kwargs)
                except BaseException as e:
                    if not _is_transient(e) or attempt >= retry:
                        raise
                    last_exc = e
                    delay = backoff * (2 ** (attempt - 1))
                    logger.warning(
                        "Qdrant.%s transient error: %s — retrying in %.1fs (%d/%d)",
                        name, e, delay, attempt, retry,
                    )
                    await asyncio.sleep(delay)
            raise last_exc  # pragma: no cover

        return wrapper
