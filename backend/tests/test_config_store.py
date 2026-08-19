import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from models.account import AccountCreate
from models.match import SyncLogEntry
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
    # Deliberately recent (not a fixed past date): this fixture is about
    # migration preserving data, not about retention — a fixed old date
    # would eventually fall outside the retention window and make this
    # test fail for an unrelated reason. See the sync-log retention tests
    # below for retention-window behaviour.
    "timestamp": datetime.now(timezone.utc).isoformat(),
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


# ----------------------------------------------------------------------
# Sync-log retention (Issue #56)
# ----------------------------------------------------------------------
#
# `log_retention_days` (default 90, plus a 500-entry cap) must hold no
# matter how the log is reached — not only as a side effect of append_log().


def _log_entry(entry_id: str, *, days_old: float = 0, timestamp: str | None = None) -> dict:
    ts = timestamp if timestamp is not None else (
        datetime.now(timezone.utc) - timedelta(days=days_old)
    ).isoformat()
    return {
        "id": entry_id,
        "timestamp": ts,
        "action": "album_sync",
        "details": f"Testeintrag {entry_id}",
        "status": "success",
    }


def test_get_log_filters_expired_entries_without_a_write(tmp_path):
    """get_log() must apply the retention window on its own — an entry that
    is already outside the window must not show up just because nothing was
    ever written after it aged out."""
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path), log_retention_days=90)

    fresh = _log_entry("fresh", days_old=1)
    expired = _log_entry("expired", days_old=91)
    store._data["sync_log"] = [expired, fresh]
    # Deliberately not calling _save() / append_log(): get_log() must filter
    # purely on read, with no write having happened since the data was set.
    mtime_before = path.stat().st_mtime if path.exists() else None

    log = store.get_log()

    assert [e.id for e in log] == ["fresh"]
    # get_log() must not persist the filtered result (see docstring in
    # config_store.py for why): the file on disk is untouched.
    assert (path.stat().st_mtime if path.exists() else None) == mtime_before


def test_get_log_caps_at_500_entries_without_a_write(tmp_path):
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path))
    store._data["sync_log"] = [_log_entry(f"e{i}", days_old=0) for i in range(510)]

    log = store.get_log()

    assert len(log) == 500
    assert [e.id for e in log[:2]] == ["e10", "e11"]
    assert log[-1].id == "e509"


def test_get_log_keeps_entries_with_unparseable_timestamp(tmp_path):
    """A broken timestamp is not a reason to lose a log entry — it should be
    kept (and left for a human/future fix), not silently dropped.

    (An entirely *missing* "timestamp" key is a different failure: the
    SyncLogEntry model requires the field, so such an entry already can't
    round-trip through get_log() regardless of retention — that is a
    pre-existing model constraint, not something this slice changes.)"""
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path))
    broken = _log_entry("broken", timestamp="not-a-real-timestamp")
    fresh = _log_entry("fresh", days_old=1)
    store._data["sync_log"] = [broken, fresh]

    log = store.get_log()

    assert {e.id for e in log} == {"broken", "fresh"}


def test_append_log_still_prunes_expired_entries_on_write(tmp_path):
    """append_log() keeps enforcing retention itself (unchanged behaviour) —
    this is the write-path counterpart of the read-path tests above."""
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path), log_retention_days=90)
    store._data["sync_log"] = [_log_entry("expired", days_old=91)]

    store.append_log([SyncLogEntry(**_log_entry("new", days_old=0))])

    assert [e.id for e in store.get_log()] == ["new"]
