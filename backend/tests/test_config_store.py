import json
import os

import pytest

from models.account import AccountCreate
from services.config_store import ConfigStore


def test_save_is_private_versioned_and_recoverable(tmp_path):
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path))
    store.add_account(
        AccountCreate(name="A", immich_url="http://192.168.1.2", api_key="secret")
    )
    payload = json.loads(path.read_text())
    assert payload["schema_version"] == ConfigStore.SCHEMA_VERSION
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


def test_invalid_config_fails_closed(tmp_path):
    path = tmp_path / "accounts.json"
    path.write_text("{broken")
    with pytest.raises(RuntimeError, match="left untouched"):
        ConfigStore(str(path))


def test_delete_account_removes_local_references(tmp_path):
    store = ConfigStore(str(tmp_path / "accounts.json"))
    account = store.add_account(
        AccountCreate(name="A", immich_url="http://192.168.1.2", api_key="secret")
    )
    assert store.delete_account(account.id)
    assert store.list_accounts() == []


# ----------------------------------------------------------------------
# Migration against a pre-schema_version file on disk
# ----------------------------------------------------------------------
#
# Old-format accounts.json: no "schema_version" key, a managed_albums entry
# whose person_refs are missing account_name/account_color/person_name (as
# they were before those fields existed), a linked_match_ids that no longer
# matches the person_refs, and pre-existing sync_log/dismissed_match_ids
# entries that must survive the migration untouched.

LEGACY_ACCOUNTS = {
    "acc-1": {
        "id": "acc-1",
        "name": "Alice",
        "immich_url": "http://192.168.1.10",
        "api_key": "key-1",
        "color": "#111111",
    },
    "acc-2": {
        "id": "acc-2",
        "name": "Bob",
        "immich_url": "http://192.168.1.11",
        "api_key": "key-2",
        "color": "#222222",
    },
}

LEGACY_SYNC_LOG_ENTRY = {
    "id": "log-1",
    "timestamp": "2026-01-01T00:00:00+00:00",
    "action": "album_sync",
    "details": "Altbestand-Eintrag, der die Migration ueberleben muss",
    "status": "success",
}

LEGACY_DISMISSED_ID = "existing-dismissed-1"


def _write_legacy_config(path):
    payload = {
        # No "schema_version" key at all — this is the pre-schema_version format.
        "accounts": LEGACY_ACCOUNTS,
        "managed_albums": [
            {
                "id": "album-1",
                "match_id": "match-1",
                "album_id": "immich-album-1",
                "album_name": "Familie",
                "owner_account_id": "acc-1",
                "person_refs": [
                    # account_name, account_color, person_name are all missing.
                    {"account_id": "acc-1", "person_id": "p1"},
                    {"account_id": "acc-2", "person_id": "p2"},
                ],
                # Deliberately stale — must be recomputed from person_refs.
                "linked_match_ids": ["stale-bogus-match-id"],
                "created_at": "2026-01-01T00:00:00+00:00",
                "last_synced_at": None,
                "total_assets": 5,
                "status": "active",
            }
        ],
        "dismissed_match_ids": [LEGACY_DISMISSED_ID],
        "sync_log": [LEGACY_SYNC_LOG_ENTRY],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def test_migrate_backfills_missing_person_ref_fields(tmp_path):
    path = tmp_path / "accounts.json"
    _write_legacy_config(path)

    store = ConfigStore(str(path))

    albums = store.get_managed_albums()
    assert len(albums) == 1
    refs = albums[0].person_refs
    by_person = {r["person_id"]: r for r in refs}

    assert by_person["p1"]["account_name"] == "Alice"
    assert by_person["p1"]["account_color"] == "#111111"
    assert by_person["p1"]["person_name"] == "Familie"  # album_name fallback

    assert by_person["p2"]["account_name"] == "Bob"
    assert by_person["p2"]["account_color"] == "#222222"
    assert by_person["p2"]["person_name"] == "Familie"

    expected_ids = ConfigStore.compute_linked_match_ids(refs)
    assert set(albums[0].linked_match_ids) == set(expected_ids)
    assert "stale-bogus-match-id" not in albums[0].linked_match_ids

    # Migration is a schema-version bump too.
    payload_on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert payload_on_disk["schema_version"] == ConfigStore.SCHEMA_VERSION


def test_migrate_preserves_existing_data(tmp_path):
    path = tmp_path / "accounts.json"
    _write_legacy_config(path)

    store = ConfigStore(str(path))

    # A clean migration proves nothing about data retention on its own —
    # this test is the actual point: old data must still be there afterwards.
    log = store.get_log()
    assert len(log) == 1
    assert log[0].id == "log-1"
    assert log[0].details == LEGACY_SYNC_LOG_ENTRY["details"]

    assert store.get_dismissed_ids() == {LEGACY_DISMISSED_ID}

    accounts = {a.id: a for a in store.list_accounts()}
    assert accounts["acc-1"].name == "Alice"
    assert accounts["acc-2"].name == "Bob"

    # And the same must hold for what actually landed on disk, not just
    # the in-memory model.
    payload_on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert payload_on_disk["dismissed_match_ids"] == [LEGACY_DISMISSED_ID]
    assert payload_on_disk["sync_log"] == [LEGACY_SYNC_LOG_ENTRY]
