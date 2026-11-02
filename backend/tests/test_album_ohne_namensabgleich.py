"""Manueller Abgleich ohne Umbenennen: `sync_names=false` und Zeilen mit
reinem Album-Zugang (`participation="album_access_only"`).

Anwendungsfall: Ein Konto (wer hochlaedt) benennt das Gesicht und steuert die
Fotos bei, ein anderes Konto braucht nur das geteilte Album. In Immich darf
dabei keine Person umbenannt werden, und das Album muss trotzdem geteilt und
automatisch abgeglichen werden.

Alle Daten erfunden; das Repo ist oeffentlich.
"""

import json

import httpx
import pytest

GEHEIM = "nur-fuer-den-test-kein-geheimnis"
K1 = {"id": "konto-1", "name": "Konto Eins", "immich_url": "http://eins.invalid",
      "api_key": "platzhalter-1", "color": "#111111", "user_id": "u1"}
K2 = {"id": "konto-2", "name": "Konto Zwei", "immich_url": "http://zwei.invalid",
      "api_key": "platzhalter-2", "color": "#222222", "user_id": "u2"}


def _datei(tmp_path):
    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({"accounts": {k["id"]: k for k in (K1, K2)},
                                "schema_version": 3, "managed_albums": []}),
                    encoding="utf-8")
    return pfad


def _attrappen(monkeypatch):
    from services import sync_service
    from services.config_store import ConfigStore
    import services.immich_client as ic

    z = {"update_person": [], "person_assets": [], "shared_with": [], "marked": []}

    class Immich:
        def __init__(self, url, *_a, **_k):
            self.url = url

        async def get_person(self, pid):
            return {"id": pid, "name": "alt"}

        async def update_person(self, pid, body):
            z["update_person"].append((self.url, pid))
            return {}

        async def get_person_assets(self, pid):
            z["person_assets"].append((self.url, pid))
            return [{"id": f"asset-{pid}"}]

        async def create_album(self, name, ids):
            return {"id": f"immich-{name}"}

        async def add_assets_to_album(self, _album_id, ids):
            return [{"id": i, "success": True} for i in ids]

        async def get_album_assets(self, *_a):
            return []

        async def get_album_assets_with_name(self, album_id):
            return None, []

    async def teilen(_client, _album_id, _name, accounts, *_a, **_k):
        z["shared_with"].extend(a.id for a in accounts)
        return []

    echtes_markieren = ConfigStore.mark_all_pairs_synced

    def markieren(self, person_ids):
        z["marked"].append(list(person_ids))
        return echtes_markieren(self, person_ids)

    monkeypatch.setattr(sync_service, "ImmichClient", Immich)
    monkeypatch.setattr(ic, "ImmichClient", Immich)
    monkeypatch.setattr(sync_service, "_share_album_if_needed", teilen)
    monkeypatch.setattr(ConfigStore, "mark_all_pairs_synced", markieren)
    return z


class _Pool:
    def get_for_account(self, _acc):
        class P:
            async def get_person(self, pid):
                return {"id": pid}
        return P()


async def _post(main, tmp_path, monkeypatch, koerper, *, refresh=False):
    monkeypatch.setattr(main.settings, "secret", GEHEIM, raising=False)
    monkeypatch.setattr(main.settings, "config_path", str(_datei(tmp_path)), raising=False)
    z = _attrappen(monkeypatch)
    async with main.app.router.lifespan_context(main.app):
        main.app.state.client_pool = _Pool()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                     base_url="http://t") as c:
            assert (await c.post("/api/auth/login", json={"token": GEHEIM})).status_code == 200
            r = await c.post("/api/sync/names-multi", json=koerper)
            alben = (await c.get("/api/sync/albums")).json()
            if refresh and r.status_code == 200:
                z["person_assets"].clear()
                z["shared_with"].clear()
                rr = await c.post(f"/api/sync/album/{alben[0]['id']}/refresh")
                assert rr.status_code == 200, rr.text
    return r, alben, z


@pytest.mark.asyncio
async def test_ohne_namensabgleich_kein_umbenennen_aber_album(tmp_path, monkeypatch):
    import main

    r, alben, z = await _post(main, tmp_path, monkeypatch, {
        "persons": [{"account_id": "konto-1", "person_id": "p1"},
                    {"account_id": "konto-2", "person_id": "p2"}],
        "canonical_name": "Kind", "album_name": "Kind", "owner_account_id": "konto-1",
        "expected_no_group": True, "sync_names": False,
    })

    assert r.status_code == 200, r.text
    assert z["update_person"] == []
    assert z["marked"] == []
    assert [e["action"] for e in r.json() if e["action"] == "sync_names"] == []
    assert len(alben) == 1
    assert z["shared_with"] == ["konto-2"]
    assert sorted(p for _, p in z["person_assets"]) == ["p1", "p2"]


@pytest.mark.asyncio
async def test_standard_benennt_weiter_um(tmp_path, monkeypatch):
    import main

    r, _, z = await _post(main, tmp_path, monkeypatch, {
        "persons": [{"account_id": "konto-1", "person_id": "p1"},
                    {"account_id": "konto-2", "person_id": "p2"}],
        "canonical_name": "Kind", "album_name": "Kind", "owner_account_id": "konto-1",
        "expected_no_group": True,
    })

    assert r.status_code == 200, r.text
    assert sorted(p for _, p in z["update_person"]) == ["p1", "p2"]
    assert z["marked"] == [["p1", "p2"]]


@pytest.mark.asyncio
async def test_nur_album_zugang_wird_geteilt_aber_nicht_befuellt(tmp_path, monkeypatch):
    import main

    r, alben, z = await _post(main, tmp_path, monkeypatch, {
        "persons": [{"account_id": "konto-1", "person_id": "p1"},
                    {"account_id": "konto-2", "participation": "album_access_only"}],
        "canonical_name": "Kind", "album_name": "Kind", "owner_account_id": "konto-1",
        "expected_no_group": True,
    }, refresh=True)

    assert r.status_code == 200, r.text
    assert z["update_person"] == [("http://eins.invalid", "p1")]
    [album] = alben
    zugang = [ref for ref in album["person_refs"] if ref["account_id"] == "konto-2"]
    assert zugang and zugang[0]["album_access_only"] is True
    assert "person_id" not in zugang[0]
    # Der Abgleich (Refresh) teilt weiter mit dem ansehenden Konto und holt
    # nur die Fotos des beisteuernden Kontos.
    assert z["shared_with"] == ["konto-2"]
    assert z["person_assets"] == [("http://eins.invalid", "p1")]


@pytest.mark.asyncio
async def test_nur_album_zugang_ohne_beitragende_wird_abgelehnt(tmp_path, monkeypatch):
    import main

    r, alben, z = await _post(main, tmp_path, monkeypatch, {
        "persons": [{"account_id": "konto-1", "participation": "album_access_only"},
                    {"account_id": "konto-2", "participation": "album_access_only"}],
        "canonical_name": "Kind", "album_name": "Kind", "owner_account_id": "konto-1",
        "expected_no_group": True,
    })

    assert r.status_code == 422, r.text
    assert r.json().get("error_key") == "err_min_one_contributor"
    assert alben == []
    assert z["update_person"] == []


@pytest.mark.asyncio
async def test_ohne_namensabgleich_und_ohne_album_wird_abgelehnt(tmp_path, monkeypatch):
    import main

    r, _, z = await _post(main, tmp_path, monkeypatch, {
        "persons": [{"account_id": "konto-1", "person_id": "p1"},
                    {"account_id": "konto-2", "person_id": "p2"}],
        "canonical_name": "Kind", "sync_names": False,
    })

    assert r.status_code == 422, r.text
    assert z["update_person"] == []


@pytest.mark.asyncio
async def test_beitragende_ohne_person_id_wird_abgelehnt(tmp_path, monkeypatch):
    import main

    r, _, z = await _post(main, tmp_path, monkeypatch, {
        "persons": [{"account_id": "konto-1"},
                    {"account_id": "konto-2", "person_id": "p2"}],
        "canonical_name": "Kind", "album_name": "Kind", "owner_account_id": "konto-1",
    })

    assert r.status_code == 422, r.text
    assert r.json().get("error_key") == "err_contributor_person_required"
    assert z["update_person"] == []
