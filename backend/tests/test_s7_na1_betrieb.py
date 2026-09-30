"""Nacharbeit 1 zu #106/#68/#124 B10 (S7 Betrieb) — Blind-, Gegen- und
Fremdpruefer-Funde am echten `ConfigStore` und an `config.py` nachgemessen.

Bewusst in einer EIGENEN Datei statt in `test_config_store.py` angehaengt
(Bau-Brief, "Nicht anfassen"): Slice S8 baut dort an den
Rueckweg-Protokoll-Proben, und eine gemeinsame Datei waere ein unnoetiger
Beruehrungspunkt zwischen zwei parallelen Slices.

Deckt:
- die neue, unverwechselbare Temp-Datei-Kennung (`_TEMP_KENNUNG`) fuer
  `_save` UND `_sichere_vor_schemasprung`, inklusive Mutationsluecken
  T2 (Laenge), T3 (Alphabet), T4 (fremder Konfigname);
- die Altersgrenze (`_TEMP_MINDESTALTER_SEKUNDEN`) gegen eine zweite
  Instanz auf demselben Verzeichnis;
- dass ALTES Muster (ohne Kennung) nur noch gewarnt, nie mehr geloescht wird;
- Symlink/Verzeichnis-Schutz beim Loeschen;
- die eigene Rechte-Anziehung (`accounts.json` -> 0600 beim Laden) und die
  erweiterte Geschwistererkennung (versteckte Handkopien, Trennpunkt-Pflicht
  gegen P8), plus die Mutationsluecken P3/P3b/P4/P5/P6;
- `backend/config.py`s `git_sha`-Vorgabewert und die leere-Umgebungsvariable
  (H1).
"""
import json
import os
import stat
import time
from pathlib import Path

import pytest

from config import Settings
from services import config_store as config_store_module
from services.config_store import ConfigStore

POSIX_ONLY = pytest.mark.skipif(
    os.name != "posix",
    reason="POSIX-Rechte/Symlinks sind unter Windows nicht verlaesslich messbar "
           "(siehe test_config_store.py, test_sicherung_bekommt_enge_rechte) — "
           "die CI faehrt den Backend-Job auf ubuntu-latest und deckt dies ab.",
)


def _leere_konfiguration() -> str:
    return json.dumps({"schema_version": 3, "accounts": {}, "managed_albums": []})


def _zurueckdatieren(pfad: Path, sekunden_alt: float, *, symlink: bool = False) -> None:
    zeitpunkt = time.time() - sekunden_alt
    os.utime(pfad, (zeitpunkt, zeitpunkt), follow_symlinks=not symlink)


# ---------------------------------------------------------------------------
# Temp-Datei-Kennung: neues Muster loeschen, altes nur warnen, Alter pruefen
# ---------------------------------------------------------------------------

def test_frische_eigene_temp_datei_bleibt_liegen(tmp_path):
    """R1 (`posix_probe.py`): Eine gerade erst angelegte eigene Temp-Datei
    (Alter ~0s) ist vermutlich eine laufende `_save` — nicht anfassen."""
    path = tmp_path / "accounts.json"
    frisch = tmp_path / ".accounts.json.speichern-tmp-a1B2c3D4"
    frisch.write_text('{"accounts": {"x": {"api_key": "noch-in-arbeit"}}}', encoding="utf-8")

    ConfigStore(str(path))

    assert frisch.exists(), "eine gerade erst angelegte Temp-Datei wurde geloescht"


def test_alte_eigene_temp_datei_mit_kennung_wird_entfernt(tmp_path, caplog):
    """Jenseits der Altersgrenze gilt eine Temp-Datei mit der eigenen
    Kennung als Leiche eines harten Absturzes und wird entfernt."""
    path = tmp_path / "accounts.json"
    leiche = tmp_path / ".accounts.json.speichern-tmp-a1B2c3D4"
    leiche.write_text('{"accounts": {"x": {"api_key": "schluessel-leiche"}}}', encoding="utf-8")
    _zurueckdatieren(leiche, 3600)

    with caplog.at_level("WARNING"):
        ConfigStore(str(path))

    assert not leiche.exists()
    treffer = [r for r in caplog.records if str(leiche) in r.getMessage()]
    assert len(treffer) == 1, [r.getMessage() for r in caplog.records]
    assert treffer[0].levelname == "WARNING"


def test_altes_muster_ohne_kennung_wird_nur_gewarnt_nicht_geloescht(tmp_path, caplog):
    """Der eigentliche Fund dieser Nacharbeit: Eine Temp-Datei-Leiche im
    ALTEN Muster (vor dieser Nacharbeit, ohne Kennung) ist nicht mehr sicher
    von einer Handkopie zu unterscheiden — sie bleibt liegen, wird aber
    gemeldet, statt geraten und geloescht zu werden."""
    path = tmp_path / "accounts.json"
    alte_leiche = tmp_path / ".accounts.json.a1B2c3D4"
    alte_leiche.write_text('{"accounts": {"x": {"api_key": "schluessel-alt"}}}', encoding="utf-8")
    os.chmod(alte_leiche, 0o600)  # isoliert die Aussage von der (separaten) Rechte-Warnung
    _zurueckdatieren(alte_leiche, 3600)

    with caplog.at_level("WARNING"):
        ConfigStore(str(path))

    assert alte_leiche.exists(), "eine Datei im alten Muster wurde geloescht statt nur gewarnt"
    eigene = [r for r in caplog.records if r.name == "services.config_store"]
    treffer = [r for r in eigene if str(alte_leiche) in r.getMessage()]
    assert len(treffer) == 1, [r.getMessage() for r in eigene]
    assert "aelteren" in treffer[0].getMessage() or "älteren" in treffer[0].getMessage()


@pytest.mark.parametrize("name", [
    ".accounts.json.20260930",
    ".accounts.json.original",
    ".accounts.json.backup01",
])
def test_handkopie_mit_acht_zeichen_bleibt_liegen(tmp_path, name):
    """Der URSPRUENGLICHE Fehler (Blind-/Gegenpruefer zu a1c6ae8): Diese
    Handkopien tragen genau die Laenge, die `mkstemp` ohne Kennung erzeugt
    haette, und wurden deshalb faelschlich geloescht."""
    path = tmp_path / "accounts.json"
    handkopie = tmp_path / name
    handkopie.write_text('{"accounts": {"k": {"api_key": "HANDKOPIE"}}}', encoding="utf-8")
    _zurueckdatieren(handkopie, 3600)

    ConfigStore(str(path))

    assert handkopie.exists(), f"Handkopie {name} wurde faelschlich geloescht"


@POSIX_ONLY
def test_symlink_mit_eigener_kennung_wird_nicht_geloescht(tmp_path):
    """`posix_probe.py` R2: Ein Symlink mit dem eigenen Temp-Muster koennte
    auf die echte Konfiguration zeigen — nur reguläre Dateien werden entfernt."""
    path = tmp_path / "accounts.json"
    path.write_text(_leere_konfiguration(), encoding="utf-8")
    os.chmod(path, 0o600)
    fallensteller = tmp_path / ".accounts.json.speichern-tmp-a1B2c3D4"
    fallensteller.symlink_to(path)
    _zurueckdatieren(fallensteller, 3600, symlink=True)

    ConfigStore(str(path))

    assert path.exists(), "das Ziel des Symlinks (die echte Konfiguration) wurde geloescht"
    assert os.path.lexists(fallensteller), "der Symlink selbst wurde entfernt"


def test_verzeichnis_mit_eigener_kennung_wird_nicht_geloescht(tmp_path):
    """`posix_probe.py` R3: Ein Verzeichnis mit dem eigenen Temp-Muster wird
    nicht als Datei behandelt und bleibt unangetastet."""
    path = tmp_path / "accounts.json"
    verzeichnis = tmp_path / ".accounts.json.speichern-tmp-a1B2c3D4"
    verzeichnis.mkdir()
    _zurueckdatieren(verzeichnis, 3600)

    ConfigStore(str(path))  # darf nicht werfen

    assert verzeichnis.exists()


def test_t2_laengerer_kennungsrest_wird_nicht_entfernt(tmp_path):
    """Mutationsluecke T2: Das Muster verlangt EXAKT 8 Zeichen nach der
    Kennung — ein 9-stelliger Rest ist kein `mkstemp`-Ergebnis und bleibt
    liegen."""
    path = tmp_path / "accounts.json"
    zu_lang = tmp_path / ".accounts.json.speichern-tmp-a1B2c3D4e"
    zu_lang.write_text("nicht anfassen", encoding="utf-8")
    _zurueckdatieren(zu_lang, 3600)

    ConfigStore(str(path))

    assert zu_lang.exists()


def test_t3_kennungsrest_mit_fremdem_zeichen_wird_nicht_entfernt(tmp_path):
    """Mutationsluecke T3: `mkstemp`s Alphabet ist Buchstaben/Ziffern/
    Unterstrich — ein Bindestrich im Rest ist kein moegliches Ergebnis."""
    path = tmp_path / "accounts.json"
    fremdes_zeichen = tmp_path / ".accounts.json.speichern-tmp-a1B2c3D-"
    fremdes_zeichen.write_text("nicht anfassen", encoding="utf-8")
    _zurueckdatieren(fremdes_zeichen, 3600)

    ConfigStore(str(path))

    assert fremdes_zeichen.exists()


def test_t4_fremder_configname_bleibt_liegen(tmp_path):
    """Mutationsluecke T4: Eine Temp-Datei-Kennung fuer eine ANDERE
    Konfigurationsdatei im selben Verzeichnis gehoert nicht zu diesem
    `ConfigStore` und bleibt unangetastet."""
    path = tmp_path / "accounts.json"
    fremd = tmp_path / ".other.json.speichern-tmp-a1B2c3D4"
    fremd.write_text("nicht anfassen", encoding="utf-8")
    _zurueckdatieren(fremd, 3600)

    ConfigStore(str(path))

    assert fremd.exists()


def test_sichere_vor_schemasprung_temp_rest_wird_beim_start_entfernt(tmp_path):
    """KLEIN-Befund (`probe_sigkill.py`): Vor dieser Nacharbeit raeumte der
    Start nur `_save`-Temp-Dateien auf; eine `_sichere_vor_schemasprung`-
    Leiche (SIGKILL zwischen `mkstemp` und `os.replace`) blieb dauerhaft
    liegen. Dieselbe Kennung, dieselbe Aufraeumroutine deckt jetzt beide
    Familien ab — hier fuer den Schemasprung-Fall."""
    path = tmp_path / "accounts.json"
    leiche = tmp_path / ".accounts.json.vor-schema-3.bak.speichern-tmp-a1B2c3D4"
    leiche.write_text('{"accounts": {"k": {"api_key": "SCHLUESSEL-IM-TEMP"}}}', encoding="utf-8")
    _zurueckdatieren(leiche, 3600)

    ConfigStore(str(path))

    assert not leiche.exists()


def test_sichere_vor_kennungsvergabe_temp_rest_wird_beim_start_entfernt(tmp_path):
    """Dieselbe Kennungsvergabe-Variante der KLEIN-Befund-Probe oben."""
    path = tmp_path / "accounts.json"
    leiche = tmp_path / ".accounts.json.vor-kennungsvergabe.bak.speichern-tmp-a1B2c3D4"
    leiche.write_text('{"accounts": {"k": {"api_key": "SCHLUESSEL-IM-TEMP"}}}', encoding="utf-8")
    _zurueckdatieren(leiche, 3600)

    ConfigStore(str(path))

    assert not leiche.exists()


# ---------------------------------------------------------------------------
# Rechte: eigene Datei wird angezogen, Geschwistererkennung erweitert
# ---------------------------------------------------------------------------

@POSIX_ONLY
def test_eigene_konfiguration_wird_beim_laden_auf_0600_gezogen(tmp_path, caplog):
    """#106 NACHARBEIT 1: `accounts.json` selbst wird beim Laden auf 0600
    gezogen, wenn sie offen ist — mit einer INFO-Zeile, OHNE zusaetzliche
    WARNUNG (andere Tests zaehlen WARNUNG-Zeilen exakt)."""
    path = tmp_path / "accounts.json"
    path.write_text(_leere_konfiguration(), encoding="utf-8")
    os.chmod(path, 0o644)
    os.chmod(tmp_path, 0o700)

    with caplog.at_level("INFO"):
        ConfigStore(str(path))

    modus = stat.S_IMODE(path.stat().st_mode)
    assert oct(modus) == oct(0o600), f"Konfiguration wurde nicht auf 0600 gezogen: {oct(modus)}"
    eigene = [r for r in caplog.records if r.name == "services.config_store"]
    info_treffer = [r for r in eigene if r.levelname == "INFO" and "0600" in r.getMessage()]
    assert len(info_treffer) == 1, [r.getMessage() for r in eigene]
    warnungen = [r for r in eigene if r.levelname == "WARNING" and "lesbar" in r.getMessage()]
    assert not warnungen, "eine zusaetzliche WARNUNG ist entstanden"


@POSIX_ONLY
def test_eigene_konfiguration_bereits_eng_bleibt_unangetastet(tmp_path, caplog):
    """Gegenprobe: Ist `accounts.json` schon 0600, geschieht nichts — kein
    `chmod`-Aufruf, keine INFO-Zeile dazu."""
    path = tmp_path / "accounts.json"
    path.write_text(_leere_konfiguration(), encoding="utf-8")
    os.chmod(path, 0o600)
    os.chmod(tmp_path, 0o700)

    with caplog.at_level("INFO"):
        ConfigStore(str(path))

    eigene = [r for r in caplog.records if r.name == "services.config_store"]
    treffer = [r for r in eigene if "0600 gezogen" in r.getMessage()]
    assert not treffer, [r.getMessage() for r in treffer]


@POSIX_ONLY
def test_versteckte_handkopie_loest_die_rechte_warnung_aus(tmp_path, caplog):
    """KLEIN-Befund: Eine versteckte Handkopie (`.accounts.json.alt`)
    beginnt nicht mit `accounts.json` und wurde von der alten
    Geschwistererkennung uebersehen."""
    path = tmp_path / "accounts.json"
    path.write_text(_leere_konfiguration(), encoding="utf-8")
    os.chmod(path, 0o600)
    os.chmod(tmp_path, 0o700)
    versteckt = tmp_path / ".accounts.json.alt"
    versteckt.write_text('{"accounts": {}}', encoding="utf-8")
    os.chmod(versteckt, 0o644)

    with caplog.at_level("WARNING"):
        ConfigStore(str(path))

    eigene = [r for r in caplog.records if r.name == "services.config_store"]
    treffer = [r for r in eigene if str(versteckt) in r.getMessage()]
    assert len(treffer) == 1, [r.getMessage() for r in eigene]
    assert treffer[0].levelname == "WARNING"


@POSIX_ONLY
def test_p8_datei_ohne_trennpunkt_zaehlt_nicht_als_geschwister(tmp_path, caplog):
    """Mutationsluecke P8: Ohne Trennpunkt-Pflicht waere `accounts.json2`
    (kein echtes Geschwister, nur derselbe Namensanfang) mitgezaehlt worden."""
    path = tmp_path / "accounts.json"
    path.write_text(_leere_konfiguration(), encoding="utf-8")
    os.chmod(path, 0o600)
    os.chmod(tmp_path, 0o700)
    kein_geschwister = tmp_path / "accounts.json2"
    kein_geschwister.write_text("fremd", encoding="utf-8")
    os.chmod(kein_geschwister, 0o777)

    with caplog.at_level("WARNING"):
        ConfigStore(str(path))

    eigene = [r for r in caplog.records if r.name == "services.config_store"]
    treffer = [r for r in eigene if str(kein_geschwister) in r.getMessage()]
    assert not treffer, [r.getMessage() for r in treffer]


@POSIX_ONLY
def test_p3_nur_gruppe_lesbar_loest_warnung_aus(tmp_path, caplog):
    path = tmp_path / "accounts.json"
    path.write_text(_leere_konfiguration(), encoding="utf-8")
    os.chmod(path, 0o600)
    os.chmod(tmp_path, 0o700)
    geschwister = tmp_path / "accounts.json.gruppe"
    geschwister.write_text("x", encoding="utf-8")
    os.chmod(geschwister, 0o640)  # nur Gruppe darf lesen

    with caplog.at_level("WARNING"):
        ConfigStore(str(path))

    eigene = [r for r in caplog.records if r.name == "services.config_store"]
    treffer = [r for r in eigene if str(geschwister) in r.getMessage()]
    assert len(treffer) == 1, [r.getMessage() for r in eigene]


@POSIX_ONLY
def test_p3b_nur_welt_lesbar_loest_warnung_aus(tmp_path, caplog):
    path = tmp_path / "accounts.json"
    path.write_text(_leere_konfiguration(), encoding="utf-8")
    os.chmod(path, 0o600)
    os.chmod(tmp_path, 0o700)
    geschwister = tmp_path / "accounts.json.welt"
    geschwister.write_text("x", encoding="utf-8")
    os.chmod(geschwister, 0o604)  # nur Welt darf lesen

    with caplog.at_level("WARNING"):
        ConfigStore(str(path))

    eigene = [r for r in caplog.records if r.name == "services.config_store"]
    treffer = [r for r in eigene if str(geschwister) in r.getMessage()]
    assert len(treffer) == 1, [r.getMessage() for r in eigene]


@POSIX_ONLY
def test_p4_zwei_offene_geschwister_ergeben_zwei_warnungen(tmp_path, caplog):
    """Mutationsluecke P4: Ein `break` nach dem ersten Fund haette eine
    zweite offene Datei verschwiegen."""
    path = tmp_path / "accounts.json"
    path.write_text(_leere_konfiguration(), encoding="utf-8")
    os.chmod(path, 0o600)
    os.chmod(tmp_path, 0o700)
    erstes = tmp_path / "accounts.json.eins"
    erstes.write_text("x", encoding="utf-8")
    os.chmod(erstes, 0o644)
    zweites = tmp_path / "accounts.json.zwei"
    zweites.write_text("x", encoding="utf-8")
    os.chmod(zweites, 0o644)

    with caplog.at_level("WARNING"):
        ConfigStore(str(path))

    eigene = [r for r in caplog.records if r.name == "services.config_store"]
    rechte_warnungen = [r for r in eigene if "lesbar" in r.getMessage()]
    assert len(rechte_warnungen) == 2, [r.getMessage() for r in rechte_warnungen]
    assert any(str(erstes) in r.getMessage() for r in rechte_warnungen)
    assert any(str(zweites) in r.getMessage() for r in rechte_warnungen)


def test_p5_iterdir_fehler_bricht_den_start_nicht(tmp_path, monkeypatch):
    """Mutationsluecke P5: Scheitert das Auflisten des Verzeichnisses beim
    Geschwister-Scan (z. B. ein unter den Fuessen entferntes Verzeichnis),
    darf der Start nicht abbrechen."""
    path = tmp_path / "accounts.json"
    path.write_text(_leere_konfiguration(), encoding="utf-8")

    if os.name == "posix":
        os.chmod(path, 0o600)
        os.chmod(tmp_path, 0o700)
    monkeypatch.setattr(config_store_module, "_verlaessliche_posix_rechte", lambda: True)

    echtes_iterdir = Path.iterdir

    def iterdir_scheitert(self):
        if self == tmp_path:
            raise OSError(2, "verzeichnis verschwunden")
        return echtes_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", iterdir_scheitert)

    ConfigStore(str(path))  # darf nicht werfen


@POSIX_ONLY
def test_p6_stat_fehler_bei_einem_kandidaten_bricht_den_start_nicht(tmp_path, caplog):
    """Mutationsluecke P6: Ein Geschwister, dessen `stat()` scheitert (hier:
    ein kaputter Symlink), darf den Start nicht abbrechen und wird einfach
    uebersprungen — auch das dazugehoerige `is_dir()`-Rennen (Fremdpruefer-
    KLEIN-Befund) ist damit ausgeschlossen, weil dieselbe `stat()`-Antwort
    fuer beides wiederverwendet wird, statt sie ein zweites Mal (ungeschuetzt)
    abzufragen."""
    path = tmp_path / "accounts.json"
    path.write_text(_leere_konfiguration(), encoding="utf-8")
    os.chmod(path, 0o600)
    os.chmod(tmp_path, 0o700)
    kaputt = tmp_path / "accounts.json.kaputt"
    kaputt.symlink_to(tmp_path / "gibt-es-nicht")

    with caplog.at_level("WARNING"):
        ConfigStore(str(path))  # darf nicht werfen

    eigene = [r for r in caplog.records if r.name == "services.config_store"]
    assert not any(str(kaputt) in r.getMessage() for r in eigene)


# ---------------------------------------------------------------------------
# backend/config.py — H1: Vorgabewert und leere Umgebungsvariable
# ---------------------------------------------------------------------------

def test_git_sha_vorgabewert_ist_unknown():
    """H1 (Mutationsluecke): Der VORGABEWERT des Feldes selbst — ohne jedes
    Monkeypatch einer Umgebungsvariable — muss "unknown" sein. Ein Test, der
    nur eine bereits gesetzte Umgebungsvariable prueft (wie
    `test_health.py`), sieht diese Mutation nicht: er ersetzt den Wert, bevor
    er ihn liest."""
    assert Settings.model_fields["git_sha"].default == "unknown"


def test_git_sha_leerer_wert_wird_zu_unknown():
    """H1, zweiter Teil: `docker build --build-arg GIT_SHA=` OHNE Wert setzt
    das Docker-`ARG`, und damit `ENV IMMICH_FAMILY_TOOLS_GIT_SHA`, auf eine
    LEERE Zeichenkette — `pydantic-settings` behandelt eine GESETZTE leere
    Umgebungsvariable als Wert, nicht als "fehlt". Ohne den Validator in
    `config.py` waere das Ergebnis `""`, nicht der ehrliche Vorgabewert."""
    einstellungen = Settings(_env_file=None, git_sha="")
    assert einstellungen.git_sha == "unknown"


def test_git_sha_echter_wert_bleibt_unangetastet():
    """Gegenprobe zum Validator: Ein echter Commit-Hash wird nicht verworfen."""
    einstellungen = Settings(_env_file=None, git_sha="a1c6ae8")
    assert einstellungen.git_sha == "a1c6ae8"


# ---------------------------------------------------------------------------
# Doku-Korrekturen (PRIVACY.md / docs/BACKUP_RESTORE.md) — jede geaenderte
# Aussage mit eigener Messung festgehalten, nicht nur im Bericht behauptet.
# Erfundene Konten/Alben/Schluessel, Adressen `http://*.invalid` (Block 7).
# ---------------------------------------------------------------------------

def _konto(n):
    return {"id": f"konto-{n}", "name": f"Konto {n}", "immich_url": f"http://k{n}.invalid",
            "api_key": f"SCHLUESSEL-{n}", "color": "#111111", "user_id": f"u{n}"}


def _ref(n, name):
    return {"account_id": f"konto-{n}", "person_id": f"p{n}-{name}", "person_name": name,
            "account_name": f"Konto {n}", "account_color": "#111111"}


def _album(aid, refs, group=True):
    a = {"id": aid, "match_id": f"m-{aid}", "album_id": f"immich-{aid}", "album_name": aid,
         "owner_account_id": "konto-1", "person_refs": refs, "linked_match_ids": [],
         "created_at": "2026-01-01T00:00:00+00:00", "total_assets": 0}
    if group:
        a["group_id"] = f"g-{aid}"
    return a


def test_rueckweg_vor_schemasprung_enthaelt_geheilte_tote_referenz(tmp_path):
    """docs/BACKUP_RESTORE.md, "A third kind of start-time write ...":
    behauptete bisher, die Bereinigung toter Kontoreferenzen bekomme NIE
    einen Rueckweg, "regardless of whether it runs together" mit einem
    Schemasprung. Gemessen: falsch. `_sichere_vor_schemasprung` kopiert die
    Platte, BEVOR `_migrate` im selben Lauf die tote Referenz entfernt —
    der Rueckweg traegt die geheilte Referenz also incidental mit, Name
    inklusive (Fall F2/`test_G_...` der Gegenpruefer-Proben)."""
    path = tmp_path / "accounts.json"
    daten = {
        "schema_version": 2,  # loest den Schemasprung auf Version 3 aus
        "accounts": {"konto-1": _konto(1), "konto-2": _konto(2)},
        "managed_albums": [_album("a1", [_ref(1, "P1"), _ref(9, "TOTE-PERSON")])],
    }
    path.write_text(json.dumps(daten), encoding="utf-8")

    ConfigStore(str(path))  # Start heilt konto-9 (existiert nicht) UND springt das Schema

    rueckweg = tmp_path / "accounts.json.vor-schema-3.bak"
    assert rueckweg.exists()
    assert "TOTE-PERSON" in rueckweg.read_text(encoding="utf-8")
    assert "TOTE-PERSON" not in path.read_text(encoding="utf-8"), "die tote Referenz haette geheilt sein muessen"


def test_rueckweg_vor_kennungsvergabe_enthaelt_geheilte_tote_referenz(tmp_path):
    """Dieselbe Korrektur wie oben, fuer die Kennungsvergabe statt den
    Schemasprung (Fall F der Gegenpruefer-Proben)."""
    path = tmp_path / "accounts.json"
    daten = {
        "schema_version": 3,
        "accounts": {"konto-1": _konto(1), "konto-2": _konto(2)},
        "managed_albums": [_album("a1", [_ref(1, "P1"), _ref(9, "TOTE-PERSON")], group=False)],
    }
    path.write_text(json.dumps(daten), encoding="utf-8")

    ConfigStore(str(path))

    rueckweg = tmp_path / "accounts.json.vor-kennungsvergabe.bak"
    assert rueckweg.exists()
    assert "TOTE-PERSON" in rueckweg.read_text(encoding="utf-8")
    assert "TOTE-PERSON" not in path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_ohne_eigenes_album_aber_mit_fremdem_totem_rest_sind_es_zwei_saves(tmp_path):
    """PRIVACY.md, die vier gemessenen `#127`-Faelle: "the account is
    referenced by no managed album at all -> the account-row removal is the
    ONLY save" galt bisher unbedingt. Gemessen: falsch, wenn irgendwo ANDERS
    im Bestand schon eine tote Referenz auf ein LAENGST anderes Konto liegt
    — `delete_account` heilt bei jedem Aufruf JEDE tote Referenz, die es
    findet, nicht nur die des Kontos, das gerade geloescht wird. Das ist ein
    ZWEITER Save, und `.bak` traegt danach nicht mehr den Zustand von VOR der
    Loeschung."""
    path = tmp_path / "accounts.json"
    daten = {
        "schema_version": 3,
        "accounts": {f"konto-{n}": _konto(n) for n in (1, 2, 3)},
        "managed_albums": [
            _album("a1", [_ref(1, "P1")]),
            _album("a9", [_ref(1, "P1b"), _ref(9, "TOTE-PERSON-9")]),  # konto-9 existiert nicht
        ],
    }
    path.write_text(json.dumps(daten), encoding="utf-8")
    # OHNE `_migrate()` laden (kein regulaeres `ConfigStore(...)`): sonst
    # heilt schon der erste Load den fremden toten Rest, und der Fall, den
    # diese Probe misst (Rest liegt schon, WAEHREND `delete_account` laeuft),
    # existiert nie. Derselbe Kniff wie in der Gegenpruefer-Probe (Fall A2).
    store = ConfigStore.__new__(ConfigStore)
    store._path = path
    store._log_retention_days = 90
    store._data = json.loads(path.read_text(encoding="utf-8"))
    saves = {"n": 0}
    echte_save = store._save

    def zaehlend():
        saves["n"] += 1
        echte_save()
    store._save = zaehlend

    ergebnis = await store.delete_account("konto-3")

    assert ergebnis is True
    assert saves["n"] == 2, "erwartet: ein Save fuer die Kontozeile, ein weiterer fuer den fremden toten Rest"
    bak = (tmp_path / "accounts.json.bak").read_text(encoding="utf-8")
    assert "SCHLUESSEL-3" not in bak, (
        "der zweite Save (Heilung des fremden Rests) ueberschreibt .bak mit dem "
        "Zustand NACH der Kontoentfernung — der Schluessel ist dort schon weg"
    )


@pytest.mark.asyncio
async def test_toter_rest_heilt_auch_durch_naechste_beliebige_kontoloeschung(tmp_path):
    """PRIVACY.md: "keeps showing ... until the application is restarted"
    war zu eng. Gemessen: Die naechste `DELETE`-Anfrage fuer IRGENDEIN Konto
    — auch eines, das es gar nicht (mehr) gibt — heilt einen liegengebliebenen
    toten Rest ebenfalls, solange das betroffene Album gerade kein Schloss
    haelt. Ein Neustart ist nur das letzte Mittel, nicht das einzige."""
    path = tmp_path / "accounts.json"
    daten = {
        "schema_version": 3,
        "accounts": {"konto-1": _konto(1)},
        "managed_albums": [_album("a1", [_ref(1, "P1"), _ref(9, "TOTE-PERSON-9")])],
    }
    path.write_text(json.dumps(daten), encoding="utf-8")
    # Ohne _migrate laden, um den Laufzeitzustand "toter Rest liegt schon"
    # nachzustellen, statt dass der erste Load ihn schon selbst heilt.
    store = ConfigStore.__new__(ConfigStore)
    store._path = path
    store._log_retention_days = 90
    store._data = json.loads(path.read_text(encoding="utf-8"))

    ergebnis = await store.delete_account("konto-nie-existent")

    assert ergebnis is False, "eine erfundene Kennung liefert False, heilt aber trotzdem mit"
    rest = [r for r in store._data["managed_albums"][0]["person_refs"] if r["account_id"] == "konto-9"]
    assert not rest, "der tote Rest wurde nicht geheilt, obwohl kein Schloss gehalten wurde"


# ---------------------------------------------------------------------------
# Dockerfile: Vorgabewert des Build-Arguments + Schichtreihenfolge fuer den
# Cache (Gegen K4 `ARG GIT_SHA=erfunden-default`; Punkt 4 des Bau-Briefs).
# Kein Docker-Aufruf hier (zu langsam fuer die Suite) — die Cache-Wirkung
# selbst ist am echten `docker build` gemessen (Bericht), dies pinnt nur die
# TEXTFORM fest, die diese Messung voraussetzt.
# ---------------------------------------------------------------------------

def _dockerfile_zeilen():
    pfad = Path(__file__).resolve().parents[2] / "Dockerfile"
    return pfad.read_text(encoding="utf-8").splitlines()


def test_dockerfile_git_sha_vorgabe_ist_unknown():
    """Gegen K4: Ein Direktbau ohne `--build-arg GIT_SHA=...` muss ehrlich
    "unknown" melden — nicht einen erfundenen Platzhalter."""
    zeilen = _dockerfile_zeilen()
    treffer = [z for z in zeilen if z.strip().startswith("ARG GIT_SHA")]
    assert treffer == ["ARG GIT_SHA=unknown"], treffer


def test_dockerfile_git_sha_steht_nach_den_teuren_schichten():
    """Punkt 4: `ARG`/`ENV GIT_SHA` muessen NACH `apt-get`/`pip install`
    stehen, sonst invalidiert jeder Commit deren Layer-Cache (siehe Bericht
    fuer die gemessene `CACHED`-Probe). Pin: die Zeilennummer von `ARG
    GIT_SHA` liegt hinter der von `pip install`."""
    zeilen = _dockerfile_zeilen()
    zeile_pip = next(i for i, z in enumerate(zeilen) if "pip install" in z)
    zeile_arg = next(i for i, z in enumerate(zeilen) if z.strip().startswith("ARG GIT_SHA"))
    zeile_cmd = next(i for i, z in enumerate(zeilen) if z.strip().startswith("CMD ["))
    assert zeile_pip < zeile_arg < zeile_cmd, (zeile_pip, zeile_arg, zeile_cmd)
