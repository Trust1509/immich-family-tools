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
    """A broken timestamp is not a reason to lose a log entry — SyncLogEntry
    stores `timestamp` as a plain str, so a garbled-but-present value still
    builds a valid model and is kept (and left for a human/future fix), not
    silently dropped.

    (An entirely *missing* "timestamp" key is a different failure — see
    test_get_log_skips_unbuildable_entries_without_crashing below: that one
    IS a corrupt entry, because the model requires the field, and is handled
    by the self-healing path instead.)"""
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path))
    broken = _log_entry("broken", timestamp="not-a-real-timestamp")
    fresh = _log_entry("fresh", days_old=1)
    store._data["sync_log"] = [broken, fresh]

    log = store.get_log()

    assert {e.id for e in log} == {"broken", "fresh"}


def test_get_log_treats_naive_timestamp_as_utc(tmp_path):
    """A timestamp without a UTC offset (no tzinfo) must not crash the
    comparison against the timezone-aware retention cutoff — it is
    interpreted as UTC, since every timestamp this app writes is UTC, and
    then filtered like any other."""
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path), log_retention_days=90)
    old_naive = _log_entry(
        "old-naive",
        timestamp=(datetime.now(timezone.utc) - timedelta(days=91))
        .replace(tzinfo=None)
        .isoformat(),
    )
    fresh_naive = _log_entry(
        "fresh-naive",
        timestamp=(datetime.now(timezone.utc) - timedelta(days=1))
        .replace(tzinfo=None)
        .isoformat(),
    )
    store._data["sync_log"] = [old_naive, fresh_naive]

    log = store.get_log()  # must not raise TypeError

    assert [e.id for e in log] == ["fresh-naive"]


def test_get_log_skips_unbuildable_entries_without_crashing(tmp_path):
    """An entry missing a required field entirely (e.g. after a manual/
    partial recovery of accounts.json) is genuinely corrupt — not just
    clock-less — and must not take down the whole log. get_log() skips it
    and still returns everything else."""
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path))
    unbuildable = {"id": "corrupt", "action": "album_sync", "status": "success"}
    fresh = _log_entry("fresh", days_old=1)
    store._data["sync_log"] = [unbuildable, fresh]

    log = store.get_log()  # must not raise ValidationError

    assert [e.id for e in log] == ["fresh"]


def test_append_log_self_heals_unbuildable_entries_on_next_write(tmp_path):
    """Unlike a merely-bad timestamp, a structurally corrupt entry (missing a
    required field) is dropped for good the next time append_log() persists
    — the store finds its way out of the state instead of being stuck with a
    permanently broken get_log() call."""
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path))
    unbuildable = {"id": "corrupt", "action": "album_sync", "status": "success"}
    store._data["sync_log"] = [unbuildable]
    store._save()

    store.append_log([SyncLogEntry(**_log_entry("new", days_old=0))])

    on_disk = json.loads(path.read_text(encoding="utf-8"))["sync_log"]
    assert [e["id"] for e in on_disk] == ["new"]
    assert [e.id for e in store.get_log()] == ["new"]


def test_append_log_still_prunes_expired_entries_on_write(tmp_path):
    """append_log() keeps enforcing retention itself (unchanged behaviour) —
    this is the write-path counterpart of the read-path tests above."""
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path), log_retention_days=90)
    store._data["sync_log"] = [_log_entry("expired", days_old=91)]

    store.append_log([SyncLogEntry(**_log_entry("new", days_old=0))])

    assert [e.id for e in store.get_log()] == ["new"]


def test_append_log_persists_pruned_result_to_disk(tmp_path):
    """The pruned/healed result must actually reach the file on disk, not
    just self._data in memory — checking through get_log() on the same
    instance would not catch a regression here, because get_log() re-filters
    from whatever is in memory regardless of what append_log() persisted."""
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path), log_retention_days=90)
    store._data["sync_log"] = [_log_entry("expired", days_old=91)]
    store._save()

    store.append_log([SyncLogEntry(**_log_entry("new", days_old=0))])

    on_disk = json.loads(path.read_text(encoding="utf-8"))["sync_log"]
    assert [e["id"] for e in on_disk] == ["new"]


def test_append_log_writes_are_visible_to_a_freshly_reopened_store(tmp_path):
    """Proves _save() actually ran (not just that self._data was updated):
    a second ConfigStore instance reading the same file must see the
    pruned+appended result."""
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path), log_retention_days=90)
    store._data["sync_log"] = [_log_entry("expired", days_old=91)]
    store._save()

    store.append_log([SyncLogEntry(**_log_entry("new", days_old=0))])

    reopened = ConfigStore(str(path), log_retention_days=90)
    assert [e.id for e in reopened.get_log()] == ["new"]


def test_append_log_does_not_mutate_stored_list_before_success(tmp_path, monkeypatch):
    """If something inside append_log() raises after the list would have
    been extended, self._data["sync_log"] must still hold its old value —
    not a grown-but-unfiltered list waiting to leak into disk in full via
    some later, unrelated _save() call (e.g. from add_account()).

    IMPORTANT: `expected_snapshot` is a deliberately separate list/dict copy,
    not just another name for the same object append_log() might mutate in
    place — comparing a mutated list to itself via a shared reference would
    always pass regardless of the bug."""
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path))
    store._data["sync_log"] = [_log_entry("original", days_old=0)]
    expected_snapshot = [dict(e) for e in store._data["sync_log"]]
    store._save()

    def boom(self, entries):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(ConfigStore, "_apply_log_retention", boom)

    with pytest.raises(RuntimeError):
        store.append_log([SyncLogEntry(**_log_entry("new", days_old=0))])

    assert store._data["sync_log"] == expected_snapshot

    monkeypatch.undo()
    store._save()  # an unrelated save must not leak a bloated list either
    on_disk = json.loads(path.read_text(encoding="utf-8"))["sync_log"]
    assert on_disk == expected_snapshot


def test_expired_entries_on_disk_disappear_from_get_log_without_any_write(tmp_path):
    """The scenario the issue is actually about: an entry that has been
    sitting on disk since before the retention window, with no sync having
    run since. A freshly loaded store must not show it — purely from
    reading the file, no append_log()/_save() involved at all."""
    path = tmp_path / "accounts.json"
    payload = {
        "schema_version": ConfigStore.SCHEMA_VERSION,
        "accounts": {},
        "dismissed_match_ids": [],
        "managed_albums": [],
        "sync_log": [
            _log_entry("stale-on-disk", days_old=91),
            _log_entry("fresh-on-disk", days_old=1),
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    store = ConfigStore(str(path), log_retention_days=90)

    assert [e.id for e in store.get_log()] == ["fresh-on-disk"]
