import json

import httpx
import pytest

from services.immich_client import AlbumNotFoundError, ImmichClient


@pytest.mark.asyncio
async def test_album_assets_are_loaded_across_all_search_pages():
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"id": "album-1", "assetCount": 3})
        body = json.loads(request.read())
        if body["page"] == 1:
            return httpx.Response(
                200,
                json={
                    "assets": {
                        "items": [{"id": "asset-1"}, {"id": "asset-2"}],
                        "nextPage": "3",
                    }
                },
            )
        return httpx.Response(
            200,
            json={
                "assets": {
                    "items": [{"id": "asset-2"}, {"id": "asset-3"}],
                    "nextPage": None,
                }
            },
        )

    client = ImmichClient(
        "http://immich.test",
        "api-key",
        transport=httpx.MockTransport(handle),
    )

    assert await client.get_album_assets("album-1") == ["asset-1", "asset-2", "asset-3"]
    assert [request.url.path for request in requests] == [
        "/api/albums/album-1",
        "/api/search/metadata",
        "/api/search/metadata",
    ]
    assert [request.method for request in requests] == ["GET", "POST", "POST"]
    assert [json.loads(request.read())["page"] for request in requests[1:]] == [1, 3]


@pytest.mark.asyncio
async def test_album_asset_lookup_reports_a_deleted_album():
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = ImmichClient(
        "http://immich.test",
        "api-key",
        transport=httpx.MockTransport(handle),
    )

    with pytest.raises(AlbumNotFoundError):
        await client.get_album_assets("deleted-album")


@pytest.mark.asyncio
async def test_people_pagination_uses_the_v3_size_parameter():
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.params == httpx.QueryParams(
            {"page": 2, "size": 250, "withHidden": False}
        )
        return httpx.Response(200, json={"people": [], "hasNextPage": False})

    client = ImmichClient(
        "http://immich.test",
        "api-key",
        transport=httpx.MockTransport(handle),
    )

    await client.get_people(page=2, page_size=250)


@pytest.mark.asyncio
async def test_all_people_are_combined_across_pages():
    pages: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        page = request.url.params["page"]
        pages.append(page)
        if page == "1":
            return httpx.Response(
                200,
                json={"people": [{"id": "person-1"}], "hasNextPage": True},
            )
        return httpx.Response(
            200,
            json={"people": [{"id": "person-2"}], "hasNextPage": False},
        )

    client = ImmichClient(
        "http://immich.test",
        "api-key",
        transport=httpx.MockTransport(handle),
    )

    people = await client.get_all_people()

    assert pages == ["1", "2"]
    assert [person["id"] for person in people] == ["person-1", "person-2"]


@pytest.mark.asyncio
async def test_name_sync_updates_a_person_with_put():
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == "/api/people/person-1"
        assert json.loads(request.read()) == {"name": "Unified Name"}
        return httpx.Response(200, json={"id": "person-1", "name": "Unified Name"})

    client = ImmichClient(
        "http://immich.test",
        "api-key",
        transport=httpx.MockTransport(handle),
    )

    person = await client.update_person("person-1", {"name": "Unified Name"})

    assert person["name"] == "Unified Name"


@pytest.mark.asyncio
async def test_get_server_version_returns_the_parsed_payload():
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/server/version"
        return httpx.Response(200, json={"major": 3, "minor": 1, "patch": 0})

    client = ImmichClient(
        "http://immich.test",
        "api-key",
        transport=httpx.MockTransport(handle),
    )

    assert await client.get_server_version() == {"major": 3, "minor": 1, "patch": 0}


@pytest.mark.asyncio
async def test_get_server_version_raises_on_http_error():
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = ImmichClient(
        "http://immich.test",
        "api-key",
        transport=httpx.MockTransport(handle),
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_server_version()


@pytest.mark.asyncio
async def test_person_assets_pagination_stops_on_a_non_numeric_next_page():
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        if body["page"] == 1:
            return httpx.Response(
                200,
                json={
                    "assets": {
                        "items": [{"id": "asset-1"}],
                        "nextPage": "not-a-number",
                    }
                },
            )
        raise AssertionError("should not request a page beyond the malformed nextPage")

    client = ImmichClient(
        "http://immich.test",
        "api-key",
        transport=httpx.MockTransport(handle),
    )

    assets = await client.get_person_assets("person-1")

    assert [a["id"] for a in assets] == ["asset-1"]


@pytest.mark.asyncio
async def test_add_assets_to_album_returns_the_per_item_results():
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert json.loads(request.read()) == {"ids": ["asset-1", "asset-2"]}
        return httpx.Response(
            200,
            json=[
                {"id": "asset-1", "success": True},
                {"id": "asset-2", "success": False, "error": "duplicate"},
            ],
        )

    client = ImmichClient(
        "http://immich.test",
        "api-key",
        transport=httpx.MockTransport(handle),
    )

    result = await client.add_assets_to_album("album-1", ["asset-1", "asset-2"])

    assert result == [
        {"id": "asset-1", "success": True},
        {"id": "asset-2", "success": False, "error": "duplicate"},
    ]


@pytest.mark.asyncio
async def test_person_assets_pagination_terminates_when_the_server_repeats_a_page():
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        if body["page"] == 1:
            return httpx.Response(
                200,
                json={
                    "assets": {
                        "items": [{"id": "asset-1"}],
                        # Server bug: nextPage doesn't advance.
                        "nextPage": "1",
                    }
                },
            )
        raise AssertionError("should not request a page beyond the non-advancing nextPage")

    client = ImmichClient(
        "http://immich.test",
        "api-key",
        transport=httpx.MockTransport(handle),
    )

    assets = await client.get_person_assets("person-1")

    assert [a["id"] for a in assets] == ["asset-1"]
