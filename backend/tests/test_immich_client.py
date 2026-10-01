import json

import httpx
import pytest

from services.immich_client import AlbumNotFoundError, ImmichClient


@pytest.mark.asyncio
async def test_album_assets_are_loaded_across_all_search_pages():
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/server/version":
            return httpx.Response(200, json={"major": 3, "minor": 1, "patch": 0})
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
        "/api/server/version",
        "/api/search/metadata",
        "/api/search/metadata",
    ]
    assert [request.method for request in requests] == ["GET", "GET", "POST", "POST"]
    assert [json.loads(request.read())["page"] for request in requests[2:]] == [1, 3]


@pytest.mark.asyncio
async def test_get_album_assets_with_name_reads_the_album_name_from_the_get_response():
    """Panel-Fund zu #97, Nacharbeit 1 (Blindprüfer + Fremdprüfer) — eigene
    Nummerierung, um sie nicht mit den fünf „Nachweis"-Proben aus dem
    Bau-Brief in `test_sync_service.py` zu verwechseln. Kein Test der ECHTEN
    `ImmichClient.get_album_assets_with_name` prüfte bisher, dass der Name
    wirklich aus dem Feld `albumName` der GET-Antwort kommt — `info.get("name")`
    oder ein hartes `return None, asset_ids` blieben grün. Das hier ist die
    echte Klasse gegen eine echte HTTP-Antwort, kein handgeschriebenes
    Testdouble."""
    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200, json={"id": "album-1", "albumName": "Echter Name aus Immich"}
            )
        return httpx.Response(
            200,
            json={"assets": {"items": [{"id": "asset-1"}], "nextPage": None}},
        )

    client = ImmichClient(
        "http://immich.test",
        "api-key",
        transport=httpx.MockTransport(handle),
    )

    name, asset_ids = await client.get_album_assets_with_name("album-1")

    assert name == "Echter Name aus Immich"
    assert asset_ids == ["asset-1"]


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
async def test_album_rename_uses_patch_with_album_name():
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path == "/api/albums/album-1"
        assert json.loads(request.read()) == {"albumName": "New family name"}
        return httpx.Response(
            200,
            json={"id": "album-1", "albumName": "New family name"},
        )

    client = ImmichClient(
        "http://immich.test", "api-key", transport=httpx.MockTransport(handle)
    )

    album = await client.update_album("album-1", {"albumName": "New family name"})

    assert album["albumName"] == "New family name"


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
        if request.url.path == "/api/server/version":
            return httpx.Response(200, json={"major": 3, "minor": 1, "patch": 0})
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
        if request.url.path == "/api/server/version":
            return httpx.Response(200, json={"major": 3, "minor": 1, "patch": 0})
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


@pytest.mark.asyncio
async def test_structured_search_expresses_two_of_three_and_uses_cursor_pagination():
    payloads: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/server/version":
            return httpx.Response(200, json={"major": 3, "minor": 2, "patch": 0})
        body = json.loads(request.read())
        payloads.append(body)
        if "cursor" not in body:
            return httpx.Response(200, json={
                "assets": {"items": [{"id": "asset-1"}], "nextCursor": "cursor-2"}
            })
        return httpx.Response(200, json={
            "assets": {"items": [{"id": "asset-2"}], "nextCursor": None}
        })

    client = ImmichClient(
        "http://immich.test", "api-key", transport=httpx.MockTransport(handle)
    )

    assets = await client.get_assets_matching_people(["a", "b", "c"], 2)

    assert [asset["id"] for asset in assets] == ["asset-1", "asset-2"]
    expected_branches = [
        {"personIds": {"all": ["a", "b"]}},
        {"personIds": {"all": ["a", "c"]}},
        {"personIds": {"all": ["b", "c"]}},
    ]
    assert payloads[0] == {
        "filter": {"trashedAt": {"eq": None}, "or": expected_branches},
        "size": 1000,
    }
    assert payloads[1]["cursor"] == "cursor-2"
    assert "page" not in payloads[1]


@pytest.mark.asyncio
async def test_structured_search_uses_any_and_all_for_boundary_thresholds():
    filters: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/server/version":
            return httpx.Response(200, json={"major": 4, "minor": 0, "patch": 0})
        filters.append(json.loads(request.read())["filter"])
        return httpx.Response(200, json={"assets": {"items": [], "nextCursor": None}})

    client = ImmichClient(
        "http://immich.test", "api-key", transport=httpx.MockTransport(handle)
    )
    await client.get_assets_matching_people(["a", "b", "c"], 1)
    await client.get_assets_matching_people(["a", "b", "c"], 3)

    assert filters == [
        {"trashedAt": {"eq": None}, "personIds": {"any": ["a", "b", "c"]}},
        {"trashedAt": {"eq": None}, "personIds": {"all": ["a", "b", "c"]}},
    ]


@pytest.mark.asyncio
async def test_large_threshold_avoids_combinatorial_or_and_counts_structured_searches_locally():
    filters: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/server/version":
            return httpx.Response(200, json={"major": 3, "minor": 2, "patch": 0})
        search_filter = json.loads(request.read())["filter"]
        filters.append(search_filter)
        person_id = search_filter["personIds"]["any"][0]
        return httpx.Response(200, json={
            "assets": {
                "items": [{"id": "shared"}, {"id": f"only-{person_id}"}],
                "nextCursor": None,
            }
        })

    client = ImmichClient(
        "http://immich.test", "api-key", transport=httpx.MockTransport(handle)
    )
    people = [f"p{index}" for index in range(10)]

    assets = await client.get_assets_matching_people(people, 5)

    assert [asset["id"] for asset in assets] == ["shared"]
    assert len(filters) == 10
    assert all("or" not in search_filter for search_filter in filters)


@pytest.mark.asyncio
async def test_album_inventory_uses_structured_album_filter_on_immich_3_2():
    payloads: list[dict] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/albums/album-1":
            return httpx.Response(200, json={"id": "album-1"})
        if request.url.path == "/api/server/version":
            return httpx.Response(200, json={"major": 3, "minor": 2, "patch": 0})
        payloads.append(json.loads(request.read()))
        return httpx.Response(200, json={
            "assets": {"items": [{"id": "asset-1"}], "nextCursor": None}
        })

    client = ImmichClient(
        "http://immich.test", "api-key", transport=httpx.MockTransport(handle)
    )

    assert await client.get_album_assets("album-1") == ["asset-1"]
    assert payloads == [{
        "filter": {
            "trashedAt": {"eq": None},
            "albumIds": {"any": ["album-1"]},
        },
        "size": 1000,
    }]
