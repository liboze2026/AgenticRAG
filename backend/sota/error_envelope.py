"""Error envelope: every /api/sota/* handler returns HTTP 200 with
{ok, error_kind?, message?}. Frontend never blanks on backend errors.
"""
from __future__ import annotations

import enum
import functools
import inspect
import logging
import traceback
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ErrorKind(str, enum.Enum):
    UNEXPECTED = "unexpected"
    DATASET_MISSING = "dataset_missing"
    DATASET_INTEGRITY = "dataset_integrity"
    INDEX_BUILD_FAILED = "index_build_failed"
    METHOD_FAILED = "method_failed"
    METHOD_TIMEOUT = "method_timeout"
    RUN_NOT_FOUND = "run_not_found"
    INVALID_CONFIG = "invalid_config"
    WORKER_OFFLINE = "worker_offline"
    CIRCUIT_OPEN = "circuit_open"
    ACADEMIC_INTEGRITY = "academic_integrity"


class SotaError(Exception):
    def __init__(self, kind: ErrorKind, message: str):
        self.kind = kind
        self.message = message
        super().__init__(message)


def wrap_response(fn: Callable) -> Callable:
    """Decorator: catch all exceptions, return 200-status JSON envelope.

    Preserves the wrapped function's signature so FastAPI dependency
    injection still sees `request: Request`, body models, query params, etc.
    """
    sig = inspect.signature(fn)

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            return await fn(*args, **kwargs)
        except SotaError as e:
            logger.warning("[sota] %s: %s", e.kind.value, e.message)
            return {"ok": False, "error_kind": e.kind.value, "message": e.message}
        except Exception as e:
            logger.exception("[sota] unexpected error in %s", fn.__name__)
            return {
                "ok": False,
                "error_kind": ErrorKind.UNEXPECTED.value,
                "message": f"{type(e).__name__}: {e}"[:500],
                "trace": traceback.format_exc()[-2000:],
            }

    wrapper.__signature__ = sig  # type: ignore[attr-defined]
    return wrapper
