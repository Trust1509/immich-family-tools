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


# ----------------------------------------------------------------------
# Gruppenkennung (#78)
#
# Bis v1.6.0 war der Albumname der Gruppierungsschluessel. Diese Tests
# sichern den Uebergang auf eine stabile Kennung: die Wanderung muss die
# heutige Namensgruppierung EINMALIG uebernehmen und danach nie wieder
# anfassen.
# ----------------------------------------------------------------------


def _album(album_id, name, persons, group_id=None):
    """Ein verwaltetes Album als Rohdaten, wie es auf der Platte liegt."""
    eintrag = {
        "id": album_id,
        "match_id": f"match-{album_id}",
        "album_id": f"immich-{album_id}",
        "album_name": name,
        "owner_account_id": "acc-1",
        "person_refs": [
            {"account_id": "acc-1", "person_id": p, "person_name": p,
             "account_name": "Alice", "account_color": "#111111"}
            for p in persons
        ],
        "created_at": "2026-01-01T00:00:00+00:00",
        "last_synced_at": None,
        "total_assets": 0,
        "status": "active",
    }
    if group_id is not None:
        eintrag["group_id"] = group_id
    return eintrag


def _write_albums(path, albums):
    path.write_text(
        json.dumps({"accounts": LEGACY_ACCOUNTS, "managed_albums": albums}, indent=2),
        encoding="utf-8",
    )


def test_migrate_laesst_jedes_album_feld_unangetastet(tmp_path):
    """Datenerhalt der ALBUM-Felder — die Haelfte, die CLAUDE.md verlangt.

    `test_migrate_preserves_existing_data` prueft Konten, Protokoll und
    verworfene Matches, aber kein einziges Feld eines verwalteten Albums.
    Gemessen an der ersten Fassung dieses Slices: Sechs zerstoererische
    Mutationen in der Wanderung — `album_id`, `owner_account_id`, `match_id`,
    `total_assets`, `status`, `created_at` ueberschreiben — liessen die volle
    Suite gruen. `album_id` und `owner_account_id` sind die Zeiger auf das
    echte Immich-Album: Eine Wanderung, die sie verdirbt, laesst die
    Anwendung danach in ein FREMDES Album schreiben.

    Die Felder werden aus dem Altbestand gelesen, nicht aufgezaehlt — ein
    neues Feld ist damit automatisch mitgeprueft.
    """
    path = tmp_path / "accounts.json"
    vorher = _write_legacy_config(path)
    alt = {a["id"]: a for a in vorher["managed_albums"]}

    ConfigStore(str(path))

    neu = {a["id"]: a for a in json.loads(path.read_text(encoding="utf-8"))["managed_albums"]}
    assert set(neu) == set(alt), "kein Album darf verschwinden oder dazukommen"

    # Diese beiden aendert die Wanderung absichtlich; alles andere nicht.
    ERLAUBT = {"group_id", "linked_match_ids", "person_refs"}
    for aid, alt_album in alt.items():
        for feld, wert in alt_album.items():
            if feld in ERLAUBT:
                continue
            assert neu[aid][feld] == wert, f"{aid}.{feld} wurde veraendert"

    # person_refs wird nur AUFGEFUELLT: dieselben Personen, dieselbe Reihenfolge.
    for aid, alt_album in alt.items():
        assert [r["person_id"] for r in neu[aid]["person_refs"]] == [
            r["person_id"] for r in alt_album["person_refs"]
        ], f"{aid}.person_refs hat Personen verloren oder vertauscht"


def test_migrate_uebernimmt_die_heutige_namensgruppierung(tmp_path):
    """Gleicher Name -> gleiche Kennung; anderer Name -> andere Kennung.

    Auch die Normalisierung (strip/lower) muss die Wanderung ueberleben,
    sonst zerlegt der Uebergang genau die Gruppen, die er retten soll.
    """
    path = tmp_path / "accounts.json"
    _write_albums(path, [
        _album("a1", "Familie", ["p1", "p2"]),
        _album("a2", "  familie  ", ["p2", "p3"]),
        _album("a3", "Urlaub", ["p4", "p5"]),
    ])

    nach = {a.id: a.group_id for a in ConfigStore(str(path)).get_managed_albums()}

    assert nach["a1"] == nach["a2"], "gleicher Name muss dieselbe Gruppe ergeben"
    assert nach["a3"] != nach["a1"], "anderer Name muss eine eigene Gruppe ergeben"
    assert all(nach.values()), "jedes Album braucht eine Kennung"


def test_migrate_vergibt_beim_zweiten_laden_keine_neuen_kennungen(tmp_path):
    """Die Wanderung ist eine Reparatur, kein Neuwuerfeln.

    Wuerde sie bei jedem Start neu vergeben, waere die Kennung genauso
    instabil wie der Name — nur unsichtbar.
    """
    path = tmp_path / "accounts.json"
    _write_albums(path, [
        _album("a1", "Familie", ["p1", "p2"]),
        _album("a2", "Familie", ["p2", "p3"]),
    ])

    erst = {a.id: a.group_id for a in ConfigStore(str(path)).get_managed_albums()}
    zweit = {a.id: a.group_id for a in ConfigStore(str(path)).get_managed_albums()}

    assert erst == zweit


def test_migrate_haengt_neues_album_an_die_bestehende_gruppe(tmp_path):
    """Ein Altbestand, der zwischen zwei Starts ein Album dazubekommt.

    Die bereits vergebene Kennung gewinnt — sonst zerreisst der zweite
    Start die Gruppe, die der erste gebildet hat.
    """
    path = tmp_path / "accounts.json"
    _write_albums(path, [
        _album("a1", "Familie", ["p1", "p2"], group_id="gruppe-fest"),
        _album("a2", "Familie", ["p2", "p3"]),
    ])

    nach = {a.id: a.group_id for a in ConfigStore(str(path)).get_managed_albums()}

    assert nach["a1"] == "gruppe-fest"
    assert nach["a2"] == "gruppe-fest"


def test_migrate_laesst_verschiedene_kennungen_bei_gleichem_namen_getrennt(tmp_path):
    """Der eigentliche Zweck: Name und Gruppe sind entkoppelt.

    Zwei Alben gleichen Namens duerfen getrennt bleiben, wenn ihre
    Kennungen es sagen. Genau das kann die Namensregel nicht ausdruecken.
    """
    path = tmp_path / "accounts.json"
    _write_albums(path, [
        _album("a1", "Familie", ["p1", "p2"], group_id="gruppe-1"),
        _album("a2", "Familie", ["p3", "p4"], group_id="gruppe-2"),
    ])

    nach = {a.id: a.group_id for a in ConfigStore(str(path)).get_managed_albums()}

    assert nach["a1"] == "gruppe-1"
    assert nach["a2"] == "gruppe-2"


def test_migrate_schreibt_beim_zweiten_start_nichts_mehr(tmp_path):
    """Der INHALT der Datei steht nach dem zweiten Start unveraendert da.

    Damit faellt eine Wanderung auf, die bei jedem Start neu wuerfelt — bei
    Gruppenkennungen die gefaehrlichste Form, weil dann jeder Neustart die
    Gruppen anders schneidet und niemand es der Datei ansieht.

    BENANNTE LUECKE, gemessen statt behauptet: Ein folgenloses Neuschreiben
    (`changed` immer wahr, identischer Inhalt) kommt hier durch — der Test
    vergleicht Inhalt, nicht Schreibvorgaenge. Gegen diese Mutation ist er
    gruen geblieben. Wer sie fangen will, braucht eine Beobachtung von
    `_save`, nicht einen Dateivergleich.
    """
    path = tmp_path / "accounts.json"
    _write_legacy_config(path)

    ConfigStore(str(path))
    nach_erstem = path.read_text(encoding="utf-8")
    ConfigStore(str(path))

    assert path.read_text(encoding="utf-8") == nach_erstem


def test_group_id_for_name_tritt_bestehender_gruppe_bei(tmp_path):
    path = tmp_path / "accounts.json"
    _write_albums(path, [_album("a1", "Familie", ["p1", "p2"])])
    store = ConfigStore(str(path))
    bestehend = store.get_managed_albums()[0].group_id

    assert store.group_id_for_name("  FAMILIE ") == bestehend


def test_group_id_for_name_oeffnet_sonst_eine_neue_gruppe(tmp_path):
    path = tmp_path / "accounts.json"
    _write_albums(path, [_album("a1", "Familie", ["p1", "p2"])])
    store = ConfigStore(str(path))
    bestehend = store.get_managed_albums()[0].group_id

    neu = store.group_id_for_name("Urlaub")

    assert neu
    assert neu != bestehend
    assert neu not in {a.group_id for a in store.get_managed_albums()}


def test_migrate_raet_bei_mehrdeutigem_namen_nicht(tmp_path):
    """Zwei Gruppen gleichen Namens: das kennungslose Album bekommt eine eigene.

    Die erste Fassung haengte es still an die in der Datei ZUERST stehende
    Gruppe — vertauschte man zwei Zeilen, kippte das Ergebnis (Fremdpruefer
    20.09.2026). Ein Zufall der Dateireihenfolge darf keine Zugehoerigkeit
    stiften.
    """
    path = tmp_path / "accounts.json"
    _write_albums(path, [
        _album("a1", "Familie", ["p1"], group_id="gruppe-1"),
        _album("a2", "Familie", ["p2"], group_id="gruppe-2"),
        _album("a3", "Familie", ["p3"]),
        _album("a4", "Familie", ["p4"]),
    ])

    nach = {a.id: a.group_id for a in ConfigStore(str(path)).get_managed_albums()}

    assert nach["a3"] not in {"gruppe-1", "gruppe-2"}
    assert nach["a4"] not in {"gruppe-1", "gruppe-2"}
    # Und auch nicht miteinander: Ein mehrdeutiger Name sagt ueber die
    # Zugehoerigkeit dieser beiden zueinander genauso wenig. Ohne diese
    # Zeile ist der Mehrdeutigkeits-Zweig nicht von der allgemeinen
    # Neuvergabe zu unterscheiden — gemessen an einer Mutation, die den
    # Zweig entfernte und trotzdem gruen blieb.
    assert nach["a3"] != nach["a4"]


def test_migrate_ist_bei_mehrdeutigem_namen_unabhaengig_von_der_reihenfolge(tmp_path):
    """Dieselbe Datei mit vertauschten Zeilen muss dasselbe Ergebnis liefern."""
    def lauf(reihenfolge):
        pfad = tmp_path / f"accounts-{reihenfolge}.json"
        eins = _album("a1", "Familie", ["p1"], group_id="gruppe-1")
        zwei = _album("a2", "Familie", ["p2"], group_id="gruppe-2")
        drei = _album("a3", "Familie", ["p3"])
        _write_albums(pfad, [eins, zwei, drei] if reihenfolge == "ab" else [zwei, eins, drei])
        nach = {a.id: a.group_id for a in ConfigStore(str(pfad)).get_managed_albums()}
        return nach["a3"] in {"gruppe-1", "gruppe-2"}

    assert lauf("ab") == lauf("ba") is False


def test_migrate_verschweisst_namenlose_alben_nicht(tmp_path):
    """Ein leerer Name ist keine Aussage ueber Zugehoerigkeit.

    Die alte Namensregel warf alle namenlosen Alben in einen Topf; das war
    voruebergehend, weil ein Name es aufloeste. Eine Kennung friert es
    dauerhaft ein — deshalb hier die bewusste Abweichung von der
    Verhaltenserhaltung.
    """
    path = tmp_path / "accounts.json"
    _write_albums(path, [
        _album("a1", "", ["p1"]),
        _album("a2", "   ", ["p2"]),
    ])

    nach = {a.id: a.group_id for a in ConfigStore(str(path)).get_managed_albums()}

    assert nach["a1"] != nach["a2"]
    assert nach["a1"] and nach["a2"]


def test_group_id_for_name_raet_bei_mehrdeutigem_namen_nicht(tmp_path):
    path = tmp_path / "accounts.json"
    _write_albums(path, [
        _album("a1", "Familie", ["p1"], group_id="gruppe-1"),
        _album("a2", "Familie", ["p2"], group_id="gruppe-2"),
    ])
    store = ConfigStore(str(path))

    assert store.group_id_for_name("Familie") not in {"gruppe-1", "gruppe-2"}


def test_group_id_for_name_oeffnet_bei_leerem_namen_eine_eigene_gruppe(tmp_path):
    path = tmp_path / "accounts.json"
    _write_albums(path, [_album("a1", "   ", ["p1"], group_id="gruppe-leer")])
    store = ConfigStore(str(path))

    assert store.group_id_for_name("  ") != "gruppe-leer"


def test_gruppenkennung_darf_nicht_leer_sein():
    """Der Modellkommentar behauptet es — der Typ muss es auch halten.

    Gemessen vom Panel: Die Mutation `group_id=""` an beiden
    Erzeugungsstellen blieb gruen. Eine leere Kennung ist der Zustand, vor
    dem der Kommentar warnt, nur ohne den lauten Fehler.
    """
    import pytest as _pytest
    from pydantic import ValidationError

    from models.match import ManagedAlbum

    felder = dict(
        id="a1", match_id="m1", album_id="ia1", album_name="Testalbum",
        owner_account_id="konto-1", person_refs=[],
        created_at="2026-01-01T00:00:00+00:00",
    )
    with _pytest.raises(ValidationError):
        ManagedAlbum(group_id="", **felder)
    with _pytest.raises(ValidationError):
        ManagedAlbum(**felder)


def test_migrate_speichert_die_vergebenen_kennungen(tmp_path):
    """Die Wanderung muss auch SCHREIBEN, nicht nur im Speicher fuellen.

    Gemessen vom Blindpruefer: Die Mutation, die den Rueckgabewert von
    `_backfill_group_ids` verwirft (`self._backfill_group_ids(albums)` statt
    `if ...: changed = True`), ueberlebte die ganze Suite. Folge waere genau
    das, wovor der Docstring dort warnt — bei jedem Start neue Kennungen,
    also Gruppen, die sich bei jedem Neustart anders schneiden.

    Der Fall greift bei einer Datei, die schon Version 3 traegt und nur das
    Feld vermissen laesst; beim echten v2->v3-Uebergang deckt der
    Versionssprung `changed` mit ab und verbirgt die Luecke.
    """
    path = tmp_path / "accounts.json"
    payload = {
        "schema_version": ConfigStore.SCHEMA_VERSION,
        "accounts": LEGACY_ACCOUNTS,
        "managed_albums": [_album("a1", "Testalbum", ["p1"])],
        "dismissed_match_ids": [],
        "synced_name_match_ids": [],
        "sync_log": [],
        "auto_sync": {"enabled": False, "time": "01:00"},
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    im_speicher = ConfigStore(str(path)).get_managed_albums()[0].group_id
    auf_platte = json.loads(path.read_text(encoding="utf-8"))["managed_albums"][0].get("group_id")

    assert auf_platte == im_speicher
    # Und deshalb beim naechsten Start unveraendert.
    assert ConfigStore(str(path)).get_managed_albums()[0].group_id == im_speicher


def test_migrate_macht_einen_kaputten_albumnamen_nicht_unstartbar(tmp_path):
    """Eine Wanderung darf einen Bestand nicht unstartbar machen.

    Gemessen vom Blindpruefer: Bei `album_name: 42` warf `_name_key` eine
    AttributeError, und `_load` machte daraus "Configuration is invalid" —
    die App startete GAR NICHT MEHR, wo sie vorher startete und erst beim
    Lesen der Alben scheiterte. Eine nicht offengelegte Verschlechterung
    gegenueber dem Vorgaenger.
    """
    path = tmp_path / "accounts.json"
    kaputt = _album("a1", "egal", ["p1"])
    kaputt["album_name"] = 42
    _write_albums(path, [kaputt])

    store = ConfigStore(str(path))  # darf nicht werfen

    with pytest.raises(Exception):
        store.get_managed_albums()  # erst hier faellt der Typ auf


# ----------------------------------------------------------------------
# Ausdrueckliche Gruppenwahl (#81)
#
# Seit #78 traegt group_id die Zugehoerigkeit — beim ANLEGEN entscheidet aber
# weiter der Name. Diese Tests sichern die Trennung von ABFRAGE (welche Gruppe
# wuerde der Name treffen?) und VERGABE (welche wird es wirklich?).
# ----------------------------------------------------------------------


def test_existing_group_for_name_findet_die_bestehende_gruppe(tmp_path):
    path = tmp_path / "accounts.json"
    _write_albums(path, [_album("a1", "Testalbum", ["p1"], group_id="gruppe-1")])
    store = ConfigStore(str(path))

    assert store.existing_group_for_name("  TESTALBUM ") == "gruppe-1"


def test_existing_group_for_name_meldet_nichts_statt_zu_raten(tmp_path):
    """Kein Treffer, mehrdeutig, leer — drei Wege, die alle None ergeben.

    Die Vorschau darf nichts behaupten, wo die Vergabe nichts wuesste. Die
    beiden Ausnahmen aus #78 gelten hier unveraendert.
    """
    path = tmp_path / "accounts.json"
    _write_albums(path, [
        _album("a1", "Doppelt", ["p1"], group_id="gruppe-1"),
        _album("a2", "Doppelt", ["p2"], group_id="gruppe-2"),
        _album("a3", "   ", ["p3"], group_id="gruppe-leer"),
    ])
    store = ConfigStore(str(path))

    assert store.existing_group_for_name("Kennt keiner") is None, "kein Treffer"
    assert store.existing_group_for_name("Doppelt") is None, "mehrdeutig"
    assert store.existing_group_for_name("  ") is None, "leer"


def test_resolve_group_id_ohne_angabe_verhaelt_sich_wie_bisher(tmp_path):
    path = tmp_path / "accounts.json"
    _write_albums(path, [_album("a1", "Testalbum", ["p1"], group_id="gruppe-1")])
    store = ConfigStore(str(path))

    assert store.resolve_group_id("Testalbum") == "gruppe-1"
    neu = store.resolve_group_id("Ganz anders")
    assert neu and neu != "gruppe-1"


def test_resolve_group_id_erzwingt_eine_eigene_gruppe(tmp_path):
    """force_new schlaegt den Namenstreffer — das ist der Sinn des Slices."""
    path = tmp_path / "accounts.json"
    _write_albums(path, [_album("a1", "Testalbum", ["p1"], group_id="gruppe-1")])
    store = ConfigStore(str(path))

    eigen = store.resolve_group_id("Testalbum", force_new=True)

    assert eigen != "gruppe-1"
    assert eigen


def test_resolve_group_id_nimmt_die_gewaehlte_gruppe_auch_gegen_den_namen(tmp_path):
    path = tmp_path / "accounts.json"
    _write_albums(path, [
        _album("a1", "Eins", ["p1"], group_id="gruppe-1"),
        _album("a2", "Zwei", ["p2"], group_id="gruppe-2"),
    ])
    store = ConfigStore(str(path))

    assert store.resolve_group_id("Eins", chosen="gruppe-2") == "gruppe-2"


def test_resolve_group_id_lehnt_eine_geratene_kennung_ab(tmp_path):
    """Eine unbekannte Kennung darf keine Gruppe ERFINDEN.

    Sonst legt ein Tippfehler im Aufruf eine Geistergruppe an, zu der nie ein
    zweites Album findet — und niemand sieht es, weil das Anlegen gelingt.
    """
    path = tmp_path / "accounts.json"
    _write_albums(path, [_album("a1", "Testalbum", ["p1"], group_id="gruppe-1")])
    store = ConfigStore(str(path))

    from errors import AppError

    # BEWUSST der konkrete Typ UND der Schluessel: `pytest.raises(Exception)`
    # faengt auch den AttributeError einer noch fehlenden Methode, und
    # `AppError` allein ist die Basisklasse ALLER Anwendungsfehler — ein
    # vertauschter Schluessel (404 statt 422) kaeme durch, obwohl
    # test_errors die Statuscodes eigens festnagelt (Zweitstimme 21.09.2026).
    with pytest.raises(AppError) as fehler:
        store.resolve_group_id("Testalbum", chosen="gibt-es-nicht")
    assert fehler.value.key == "err_group_not_found"


def test_resolve_group_id_lehnt_widerspruechliche_angaben_ab(tmp_path):
    path = tmp_path / "accounts.json"
    _write_albums(path, [_album("a1", "Testalbum", ["p1"], group_id="gruppe-1")])
    store = ConfigStore(str(path))

    from errors import AppError

    with pytest.raises(AppError) as fehler:
        store.resolve_group_id("Testalbum", chosen="gruppe-1", force_new=True)
    assert fehler.value.key == "err_group_choice_conflict"

    # Eine LEERE Kennung ist eine Angabe, keine Auslassung.
    with pytest.raises(AppError) as leer:
        store.resolve_group_id("Testalbum", chosen="", force_new=True)
    assert leer.value.key == "err_group_choice_conflict"


def test_group_details_zeigt_wem_man_beitritt(tmp_path):
    """Die Vorschau muss die Personen der GANZEN Gruppe fuehren, entdoppelt.

    Ohne sie waere die Bestaetigung eine leere Geste: Der Nutzer soll sehen,
    WEM er beitritt, nicht nur DASS er beitritt.
    """
    path = tmp_path / "accounts.json"
    _write_albums(path, [
        _album("a1", "Testalbum", ["p1", "p2"], group_id="gruppe-1"),
        _album("a2", "Anders benannt", ["p2", "p3"], group_id="gruppe-1"),
        _album("a3", "Testalbum", ["p9"], group_id="gruppe-2"),
    ])
    store = ConfigStore(str(path))

    details = store.group_details("gruppe-1")

    assert [r["person_id"] for r in details["person_refs"]] == ["p1", "p2", "p3"]
    assert sorted(details["album_names"]) == ["Anders benannt", "Testalbum"]


def test_group_details_haelt_gleiche_personen_aus_zwei_konten_auseinander(tmp_path):
    """Der Schluessel traegt Konto UND Person.

    Zwei Immich-Instanzen koennen dieselbe Personen-Kennung vergeben. Die
    Entdopplung nur ueber person_id wuerde eine der beiden verschlucken — und
    der Nutzer saehe nicht, wem er wirklich beitritt. Gemessen: Ohne den
    Kontoanteil blieb die Suite gruen, weil alle Testpersonen in einem Konto
    lagen (Gegenpruefer 21.09.2026).
    """
    path = tmp_path / "accounts.json"
    eins = _album("a1", "Testalbum", ["p1"], group_id="gruppe-1")
    zwei = _album("a2", "Testalbum", ["p1"], group_id="gruppe-1")
    zwei["person_refs"][0]["account_id"] = "konto-2"
    zwei["person_refs"][0]["account_name"] = "Konto Zwei"
    _write_albums(path, [eins, zwei])
    store = ConfigStore(str(path))

    details = store.group_details("gruppe-1")

    assert len(details["person_refs"]) == 2
    assert {r["account_id"] for r in details["person_refs"]} == {"acc-1", "konto-2"}
