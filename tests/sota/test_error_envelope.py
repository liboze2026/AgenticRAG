import pytest

from backend.sota.error_envelope import ErrorKind, SotaError, wrap_response


@pytest.mark.asyncio
async def test_wrap_response_passes_through_ok_dict():
    @wrap_response
    async def handler():
        return {"ok": True, "data": 42}

    resp = await handler()
    assert resp == {"ok": True, "data": 42}


@pytest.mark.asyncio
async def test_wrap_response_catches_exception_returns_200_envelope():
    @wrap_response
    async def handler():
        raise ValueError("bad")

    resp = await handler()
    assert resp["ok"] is False
    assert resp["error_kind"] == ErrorKind.UNEXPECTED.value
    assert "bad" in resp["message"]


@pytest.mark.asyncio
async def test_wrap_response_known_error_kind_preserved():
    @wrap_response
    async def handler():
        raise SotaError(ErrorKind.DATASET_MISSING, "fetatab not on disk")

    resp = await handler()
    assert resp["ok"] is False
    assert resp["error_kind"] == "dataset_missing"
    assert resp["message"] == "fetatab not on disk"
