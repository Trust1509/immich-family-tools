import httpx
import pytest
from fastapi import HTTPException

from routers.accounts import _check_immich_version, _reject_unsupported_version
from services.immich_client import ImmichClient


def test_reject_unsupported_version_rejects_immich_v2():
    with pytest.raises(HTTPException) as exc_info:
        _reject_unsupported_version({"major": 2, "minor": 4, "patch": 0})

    assert exc_info.value.status_code == 422
    assert "2.4" in exc_info.value.detail
    assert "v3.x" in exc_info.value.detail


def test_reject_unsupported_version_allows_immich_v3():
    _reject_unsupported_version({"major": 3, "minor": 1, "patch": 0})


def test_reject_unsupported_version_allows_future_majors():
    _reject_unsupported_version({"major": 4, "minor": 0, "patch": 0})


@pytest.mark.asyncio
async def test_check_immich_version_raises_for_an_old_server():
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"major": 2, "minor": 9, "patch": 0})

    client = ImmichClient(
        "http://immich.test",
        "api-key",
        transport=httpx.MockTransport(handle),
    )

    with pytest.raises(HTTPException) as exc_info:
        await _check_immich_version(client)

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_check_immich_version_fails_open_when_endpoint_is_missing():
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = ImmichClient(
        "http://immich.test",
        "api-key",
        transport=httpx.MockTransport(handle),
    )

    # Should not raise — an unreachable version endpoint must not block
    # exotic/older setups from adding an account.
    await _check_immich_version(client)
