"""Betrieb rund um Start und Aufraeumung: `ConfigStore`s Umgang mit
liegengebliebenen Temp-Dateien, ihre eigenen Dateirechte und `config.py`s
`git_sha`-Feld — am echten Code nachgemessen, in einer eigenen Datei statt in
`test_config_store.py`, weil letztere Datei die Rueckweg-Protokoll-Proben
fuehrt und ein gemeinsamer Beruehrungspunkt hier keinen Nutzen haette.

Deckt:
- die unverwechselbare Temp-Datei-Kennung (`_TEMP_KENNUNG`) fuer `_save` UND
  `_sichere_vor_schemasprung`, inklusive Mutationsluecken bei Laenge, Alphabet
  und Mittelteil des Namensmusters, und dass sie ECHT von `mkstemp` erzeugte
  Dateien erkennt, nicht nur von Hand nachgebaute Namen;
- die Altersgrenze (`_TEMP_MINDESTALTER_SEKUNDEN`) gegen eine zweite Instanz
  auf demselben Verzeichnis, ihre exakte Schwelle, und dass ein zu junger
  oder in der Zukunft datierter Fund gemeldet statt still uebergangen wird;
- den einmaligen, verzoegerten zweiten Aufraeumdurchlauf im laufenden Betrieb
  (`ConfigStore.zweiter_aufraeum_durchlauf`) und sein sauberes Abbrechen beim
  Herunterfahren;
- dass ALTES Muster (ohne Kennung) nur noch gewarnt, nie mehr geloescht wird;
- Symlink/Verzeichnis-Schutz beim Loeschen UND beim Rechte-Anziehen, inklusive
  der Reihenfolge (Rechte werden erst NACH erfolgreichem Parsen angezogen);
- die eigene Rechte-Anziehung (`accounts.json` -> 0600 beim Laden) und die
  erweiterte Geschwistererkennung (versteckte Handkopien, Trennpunkt-Pflicht),
  plus mehrere Mutationsluecken dort;
- `backend/config.py`s `git_sha`-Vorgabewert und die leere bzw. reine
  Leerraum-Umgebungsvariable.
"""
import asyncio
import errno
import json
import os
import stat
import time
from pathlib import Path

import pytest

from config import Settings
from models.account import AccountCreate
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
    """Eine gerade erst angelegte eigene Temp-Datei (Alter ~0s) ist vermutlich
    eine laufende `_save` — nicht anfassen."""
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
    """Ein Symlink mit dem eigenen Temp-Muster wird nicht angefasst — NICHT
    weil `unlink()` sein Ziel loeschen wuerde (das tut `unlink()` nie: es
    entfernt immer nur den Verzeichniseintrag selbst, gemessen unten und in
    `test_unlink_eines_symlinks_entfernt_nie_dessen_ziel`), sondern weil ein
    Betreiber-Symlink mit zufaellig passendem Namen sonst wortlos
    verschwaende — nur reguläre Dateien werden entfernt."""
    path = tmp_path / "accounts.json"
    path.write_text(_leere_konfiguration(), encoding="utf-8")
    os.chmod(path, 0o600)
    fallensteller = tmp_path / ".accounts.json.speichern-tmp-a1B2c3D4"
    fallensteller.symlink_to(path)
    _zurueckdatieren(fallensteller, 3600, symlink=True)

    ConfigStore(str(path))

    assert path.exists(), "das Ziel des Symlinks (die echte Konfiguration) wurde geloescht"
    assert os.path.lexists(fallensteller), "der Symlink selbst wurde entfernt"


@POSIX_ONLY
def test_symlink_mit_eigener_kennung_und_altem_ziel_wird_nicht_geloescht(tmp_path):
    """Mutationsluecke (gemessen): Der Test oben allein laesst M04 (den
    `is_symlink()`-Zweig aus der Vorpruefung entfernen) unbemerkt gruen —
    `kandidat.stat()` im Alterscheck FOLGT dem Symlink und liest damit das
    Ziel-mtime, und das Ziel dort ist FRISCH (gerade erst geschrieben): Der
    Fund gilt allein durch die Altersgrenze schon als "zu jung", unabhaengig
    davon, ob die Symlink-Pruefung ueberhaupt existiert. Nur wenn auch das
    ZIEL alt ist, prueft dieser Fall wirklich die Symlink-Pruefung selbst,
    nicht bloss zufaellig die Altersgrenze."""
    ziel = tmp_path / "woanders.json"
    ziel.write_text(_leere_konfiguration(), encoding="utf-8")
    os.chmod(ziel, 0o600)
    _zurueckdatieren(ziel, 3600)
    path = tmp_path / "accounts.json"
    path.write_text(_leere_konfiguration(), encoding="utf-8")
    os.chmod(path, 0o600)
    fallensteller = tmp_path / ".accounts.json.speichern-tmp-a1B2c3D4"
    fallensteller.symlink_to(ziel)
    _zurueckdatieren(fallensteller, 3600, symlink=True)

    ConfigStore(str(path))

    assert ziel.exists(), "das Ziel des Symlinks wurde geloescht"
    assert os.path.lexists(fallensteller), "der Symlink selbst wurde entfernt"


@POSIX_ONLY
def test_unlink_eines_symlinks_entfernt_nie_dessen_ziel(tmp_path):
    """Grundlage der Begruendung oben, direkt gemessen statt behauptet:
    `os.unlink()`/`Path.unlink()` entfernen unter POSIX IMMER nur den
    Verzeichniseintrag (den Symlink), niemals sein Ziel — unabhaengig davon,
    ob die aufrufende Stelle das vorher prueft oder nicht."""
    ziel = tmp_path / "ziel.json"
    ziel.write_text("bleibt", encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(ziel)

    link.unlink()

    assert not link.exists() and not os.path.lexists(link)
    assert ziel.exists() and ziel.read_text(encoding="utf-8") == "bleibt"


def test_verzeichnis_mit_eigener_kennung_wird_nicht_geloescht(tmp_path, caplog):
    """Ein Verzeichnis mit dem eigenen Temp-Muster wird nicht als Datei
    behandelt und bleibt unangetastet — und zwar durch die VORAB-Pruefung
    (`is_symlink() or not is_file()`), nicht bloss zufaellig, weil ein
    `unlink()`-Versuch auf ein Verzeichnis mit `OSError` scheitern wuerde
    (Mutationsluecke M05: die Existenz-Zusicherung allein uebersieht eine
    Fassung, die das Verzeichnis erst UNLINK-VERSUCHT und erst DANACH am
    Fehler scheitert — beobachtbar nur am Wortlaut der Log-Zeile)."""
    path = tmp_path / "accounts.json"
    verzeichnis = tmp_path / ".accounts.json.speichern-tmp-a1B2c3D4"
    verzeichnis.mkdir()
    _zurueckdatieren(verzeichnis, 3600)

    with caplog.at_level("WARNING"):
        ConfigStore(str(path))  # darf nicht werfen

    assert verzeichnis.exists()
    eigene = [r for r in caplog.records if r.name == "services.config_store"]
    # NUR die "unangetastet gelassen"-Zeile der Temp-Aufraeumung zaehlt hier —
    # unter echten POSIX-Rechten (Linux-Container) meldet die UNABHAENGIGE
    # Geschwister-Rechte-Warnung DASSELBE Verzeichnis zusaetzlich ein zweites
    # Mal (`mkdir()` erzeugt es standardmaessig fuer Gruppe/Welt lesbar) — das
    # ist ein eigener, richtiger Fund einer anderen Pruefung, kein Duplikat
    # dieser hier, und deshalb keine Regel fuer "genau eine Zeile insgesamt".
    treffer = [r for r in eigene if str(verzeichnis) in r.getMessage() and "unangetastet gelassen" in r.getMessage()]
    assert len(treffer) == 1, [r.getMessage() for r in eigene]


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
    """Eine `_sichere_vor_schemasprung`-Leiche (Prozess hart beendet zwischen
    `mkstemp` und `os.replace`) wird von derselben Kennung und derselben
    Aufraeumroutine erfasst wie eine `_save`-Leiche — hier fuer den
    Schemasprung-Fall (eine fruehere Fassung raeumte nur `_save` auf und liess
    diese Familie dauerhaft liegen)."""
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


def test_fremde_konfiguration_im_selben_ordner_bleibt_unberuehrt(tmp_path):
    """KLEIN-Befund (Gegenpruefer, gemessen): Der Zwischenteil des eigenen
    Musters war vorher beliebig (`(?:\\..+)?`) und erkannte damit auch die
    Temp-Datei-Leiche einer VOELLIG ANDEREN Konfigurationsdatei im selben
    Ordner als eigene — dieser `ConfigStore` (fuer `accounts.json`) loeschte
    dann `.accounts.json.test.speichern-tmp-<8 Zeichen>`, obwohl die zu
    `accounts.json.test` gehoert, nicht zu ihm. Der Zwischenteil zaehlt jetzt
    nur noch die beiden bekannten Rueckweg-Endungen auf."""
    path = tmp_path / "accounts.json"
    fremde_leiche = tmp_path / ".accounts.json.test.speichern-tmp-a1B2c3D4"
    fremde_leiche.write_text('{"accounts": {"k": {"api_key": "GEHOERT-NICHT-UNS"}}}', encoding="utf-8")
    _zurueckdatieren(fremde_leiche, 3600)

    ConfigStore(str(path))

    assert fremde_leiche.exists(), "die Leiche einer fremden Konfigurationsdatei wurde geloescht"


@pytest.mark.parametrize("alter,bleibt", [(299, True), (301, False)])
def test_altersgrenze_ist_exakt_300_sekunden(tmp_path, alter, bleibt):
    """Mutationsluecken M02/M03: Die bisherigen Proben massen nur grob (0s
    bleibt, 3600s geht) — eine auf 1s oder 3000s verstellte Schwelle blieb
    unbemerkt gruen. Zurueckdatieren macht die exakte Grenze ohne echtes
    Warten messbar."""
    path = tmp_path / "accounts.json"
    leiche = tmp_path / ".accounts.json.speichern-tmp-a1B2c3D4"
    leiche.write_text("x", encoding="utf-8")
    _zurueckdatieren(leiche, alter)

    ConfigStore(str(path))

    assert leiche.exists() is bleibt


def test_junge_temp_datei_wird_gemeldet_nicht_still_uebergangen(tmp_path, caplog):
    """Der eigentliche Befund dieser Runde: Ein Absturz mit sofortigem
    Neustart (`restart: unless-stopped` faehrt in Sekunden wieder hoch)
    hinterlaesst einen Rest, der beim Start-Scan juenger als die
    Altersgrenze ist — er blieb VORHER still liegen, ohne dass irgendeine
    Zeile ihn nannte. Jetzt wird er gemeldet, mit Pfad, auch wenn er (noch)
    nicht entfernt wird."""
    path = tmp_path / "accounts.json"
    leiche = tmp_path / ".accounts.json.speichern-tmp-a1B2c3D4"
    leiche.write_text('{"api_key": "GEHEIM-IM-TEMP"}', encoding="utf-8")
    os.chmod(leiche, 0o600)  # isoliert die Aussage von der Rechte-Warnung
    _zurueckdatieren(leiche, 10)

    with caplog.at_level("WARNING"):
        ConfigStore(str(path))

    assert leiche.exists(), "Testaufbau: 10s ist juenger als die Altersgrenze"
    eigene = [r for r in caplog.records if r.name == "services.config_store"]
    treffer = [r for r in eigene if str(leiche) in r.getMessage()]
    assert len(treffer) == 1, [r.getMessage() for r in eigene]
    assert treffer[0].levelname == "WARNING"


def test_leiche_mit_mtime_in_der_zukunft_bleibt_liegen_und_wird_gemeldet(tmp_path, caplog):
    """Mutationsluecke M23: `abs(jetzt - mtime)` wuerde eine Aenderungszeit in
    der Zukunft (Uhrsprung, verstellte Systemzeit) in ein hohes POSITIVES
    Alter verwandeln und die Leiche sofort loeschen — ein `os.utime` mit
    (versehentlich oder mutwillig) zukuenftigem Zeitstempel ist genauso ein
    aktiver Schreibvorgang wie einer mit juengst-vergangenem."""
    path = tmp_path / "accounts.json"
    leiche = tmp_path / ".accounts.json.speichern-tmp-a1B2c3D4"
    leiche.write_text('{"api_key": "GEHEIM-IM-TEMP"}', encoding="utf-8")
    os.chmod(leiche, 0o600)
    in_der_zukunft = time.time() + 86400
    os.utime(leiche, (in_der_zukunft, in_der_zukunft))

    with caplog.at_level("WARNING"):
        ConfigStore(str(path))

    assert leiche.exists(), "eine Leiche mit Zukunfts-mtime wurde faelschlich geloescht"
    eigene = [r for r in caplog.records if r.name == "services.config_store"]
    assert any(str(leiche) in r.getMessage() for r in eigene)


@pytest.mark.asyncio
async def test_zweiter_durchlauf_entfernt_zunaechst_zu_jungen_rest(tmp_path):
    """Der einmalige zweite Aufraeumdurchlauf schliesst die Luecke, die der
    Start-Scan allein offen laesst: Ein Rest, der beim Start noch zu jung
    war, wird spaeter — INNERHALB DERSELBEN laufenden Instanz, ohne auf einen
    weiteren vollen Neustart zu warten — doch noch entfernt, sobald die
    Altersgrenze ueberschritten ist. `verzoegerung_sekunden` haelt die Probe
    schnell; die Zeit selbst kommt aus einer zurueckdatierten `mtime`, nicht
    aus echtem Warten."""
    path = tmp_path / "accounts.json"
    leiche = tmp_path / ".accounts.json.speichern-tmp-a1B2c3D4"
    leiche.write_text('{"api_key": "GEHEIM-IM-TEMP"}', encoding="utf-8")
    os.chmod(leiche, 0o600)
    _zurueckdatieren(leiche, 10)  # zu jung fuer den Start-Scan

    store = ConfigStore(str(path))
    assert leiche.exists(), "Testaufbau: der Start-Scan darf sie noch nicht entfernt haben"

    # Zeit vergeht: die Leiche altert ueber die Schwelle, ohne dass echt
    # gewartet wird.
    _zurueckdatieren(leiche, 3600)
    await store.zweiter_aufraeum_durchlauf(verzoegerung_sekunden=0.01)

    assert not leiche.exists(), "der zweite Durchlauf haette die inzwischen gealterte Leiche entfernen muessen"


@pytest.mark.asyncio
async def test_zweiter_durchlauf_faengt_eigene_fehler_ab(tmp_path, monkeypatch, caplog):
    """FEHLER BRECHEN NICHTS: Ein Fehler im Scan selbst darf die
    Hintergrundaufgabe nicht mit einer unbehandelten Ausnahme beenden."""
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path))

    def wirft(*_a, **_k):
        raise RuntimeError("simulierter Fehler im Scan")

    monkeypatch.setattr(store, "_raeume_verwaiste_temp_dateien", wirft)

    with caplog.at_level("ERROR"):
        await store.zweiter_aufraeum_durchlauf(verzoegerung_sekunden=0.01)  # darf nicht werfen

    assert any(r.levelname == "ERROR" for r in caplog.records)


@pytest.mark.asyncio
async def test_zweiter_durchlauf_bricht_beim_abbrechen_sauber_ab():
    """Herunterfahren vor Ablauf der Wartezeit bricht die Aufgabe ohne Fehler
    ab — genau das Verhalten, das `main.py`s Shutdown-Handler braucht:
    `task.cancel()` gefolgt von `await task` darf keine andere Ausnahme als
    `asyncio.CancelledError` erzeugen, und die Koroutine selbst darf diese
    nicht abfangen (sonst gilt die Aufgabe als beendet, nicht als
    abgebrochen)."""
    store = ConfigStore.__new__(ConfigStore)  # kein echter Scan noetig
    aufgabe = asyncio.create_task(store.zweiter_aufraeum_durchlauf(verzoegerung_sekunden=10))
    await asyncio.sleep(0)  # der Aufgabe die Chance geben, in den `sleep` zu laufen

    aufgabe.cancel()
    with pytest.raises(asyncio.CancelledError):
        await aufgabe
    assert aufgabe.cancelled()


# ---------------------------------------------------------------------------
# Verdrahtung: die ECHTE Temp-Datei erkennen, nicht eine von Hand nachgebaute
# ---------------------------------------------------------------------------

def _echte_temp_datei_durch_schreibfehler_zurueckgelassen(tmp_path, monkeypatch, aktion, *, passt) -> Path:
    """Simuliert einen echten Schreibfehler (statt eines Prozessabsturzes,
    der sich in einem einzelnen Testprozess nicht nachstellen laesst): sowohl
    `os.replace` als auch das eigene Aufraeumen im `finally` schlagen fehl,
    sodass die ECHTE, von `tempfile.mkstemp` erzeugte Temp-Datei tatsaechlich
    liegen bleibt — die Probe baut ihren Namen NICHT von Hand nach
    (Blindpruefer W1: alle bisherigen Proben taten genau das und uebersahen
    deshalb eine Verdrahtungsluecke, bei der `_save`/der Rueckweg einen
    ANDEREN Praefix benutzen als die Erkennung erwartet — Mutationsluecken
    M08-M11). `passt(pfad)` waehlt aus, WELCHER `os.replace`-Aufruf sabotiert
    wird — ein `ConfigStore`-Start kann mehrere ausloesen (z. B. den Rueckweg
    UND danach `_save` fuer die geheilte Konfiguration selbst), und nur einer
    davon ist der, den diese Probe untersucht; alle anderen laufen echt."""
    real_replace = os.replace
    real_unlink = os.unlink
    gemerkt: dict = {}

    def replace_schlaegt_fehl(src, dst):
        if str(tmp_path) not in str(src) or not passt(str(src)):
            return real_replace(src, dst)
        gemerkt["pfad"] = str(src)
        raise OSError(errno.EIO, "simulierter Schreibfehler")

    def unlink_schlaegt_fehl(pfad):
        if str(pfad) != gemerkt.get("pfad"):
            return real_unlink(pfad)
        raise OSError(errno.EIO, "simulierter Schreibfehler beim Aufraeumen")

    monkeypatch.setattr(config_store_module.os, "replace", replace_schlaegt_fehl)
    monkeypatch.setattr(config_store_module.os, "unlink", unlink_schlaegt_fehl)
    aktion()
    monkeypatch.setattr(config_store_module.os, "replace", real_replace)
    monkeypatch.setattr(config_store_module.os, "unlink", real_unlink)

    assert "pfad" in gemerkt, "Testaufbau: kein passender os.replace-Aufruf fand statt"
    return Path(gemerkt["pfad"])


def test_echte_temp_datei_von_save_wird_erkannt(tmp_path, monkeypatch):
    """Verdrahtungsluecke (Blindpruefer W1): `_save` hinterlaesst seine ECHTE
    Temp-Datei (nicht eine von Hand nachgebaute), die Probe datiert sie
    zurueck und laedt neu — die reguläre Aufraeumroutine muss sie ueber ihr
    ECHTES Muster erkennen."""
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path))

    def aktion():
        with pytest.raises(OSError):
            store.add_account(AccountCreate(name="K", immich_url="http://k.invalid", api_key="X"))

    ist_die_eigene_save_datei = lambda p: "vor-schema" not in p and "vor-kennungsvergabe" not in p
    echte_temp_datei = _echte_temp_datei_durch_schreibfehler_zurueckgelassen(
        tmp_path, monkeypatch, aktion, passt=ist_die_eigene_save_datei,
    )
    assert echte_temp_datei.name.startswith(".accounts.json.speichern-tmp-")

    _zurueckdatieren(echte_temp_datei, 3600)
    ConfigStore(str(path))  # regulaerer Start, echte Aufraeumroutine

    assert not echte_temp_datei.exists(), "die ECHTE Temp-Datei von _save wurde nicht erkannt"


def test_echte_temp_datei_des_schemasprung_rueckwegs_wird_erkannt(tmp_path, monkeypatch):
    """Dieselbe Verdrahtungsluecke fuer `_sichere_vor_schemasprung(einmalig=
    True)` — ausgeloest durch einen Schemasprung beim Laden. Der fehlschlagende
    Rueckweg wird intern abgefangen (`_sichere_vor_schemasprung`s eigenes
    `except OSError`); ein anschliessendes `_save` fuer die geheilte
    Konfiguration selbst laeuft danach unbehindert weiter (`passt` sabotiert
    nur den Rueckweg, nicht diesen zweiten, unabhaengigen Schreibvorgang)."""
    path = tmp_path / "accounts.json"
    path.write_text(json.dumps({"schema_version": 2, "accounts": {}, "managed_albums": []}), encoding="utf-8")

    def aktion():
        ConfigStore(str(path))  # Fehler wird intern abgefangen, wirft nicht

    echte_temp_datei = _echte_temp_datei_durch_schreibfehler_zurueckgelassen(
        tmp_path, monkeypatch, aktion, passt=lambda p: "vor-schema" in p,
    )
    assert echte_temp_datei.name.startswith(".accounts.json.vor-schema-3.bak.speichern-tmp-")

    _zurueckdatieren(echte_temp_datei, 3600)
    ConfigStore(str(path))

    assert not echte_temp_datei.exists(), "die ECHTE Rueckweg-Temp-Datei (Schemasprung) wurde nicht erkannt"


def test_echte_temp_datei_der_kennungsvergabe_sicherung_wird_erkannt(tmp_path, monkeypatch):
    """Dieselbe Verdrahtungsluecke fuer `_sichere_vor_schemasprung(einmalig=
    False)` — ausgeloest durch ein Album ohne `group_id` beim Laden."""
    path = tmp_path / "accounts.json"
    album = {
        "id": "a1", "match_id": "m-a1", "album_id": "i-a1", "album_name": "a1",
        "owner_account_id": "konto-1", "person_refs": [], "linked_match_ids": [],
        "created_at": "2026-01-01T00:00:00+00:00", "total_assets": 0,
    }  # kein group_id -> loest die Kennungsvergabe-Sicherung aus
    path.write_text(json.dumps({"schema_version": 3, "accounts": {}, "managed_albums": [album]}), encoding="utf-8")

    def aktion():
        ConfigStore(str(path))

    echte_temp_datei = _echte_temp_datei_durch_schreibfehler_zurueckgelassen(
        tmp_path, monkeypatch, aktion, passt=lambda p: "vor-kennungsvergabe" in p,
    )
    assert echte_temp_datei.name.startswith(".accounts.json.vor-kennungsvergabe.bak.speichern-tmp-")

    _zurueckdatieren(echte_temp_datei, 3600)
    ConfigStore(str(path))

    assert not echte_temp_datei.exists(), "die ECHTE Rueckweg-Temp-Datei (Kennungsvergabe) wurde nicht erkannt"


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


def test_p17_stat_fehler_beim_alterscheck_bricht_den_start_nicht(tmp_path, monkeypatch):
    """Mutationsluecke M17: Zwischen der Pruefung `is_file()` (folgt dem Pfad
    und ruft dabei intern bereits `stat()` auf) und dem separaten
    `kandidat.stat().st_mtime` fuer den Alterscheck liegt eine — wenn auch
    winzige — Zeitluecke, in der die Datei verschwinden koennte (ein
    Wettlauf mit einer anderen Instanz oder einem Betreiber-Aufraeumskript).
    Ohne das eigene `try/except OSError` an dieser zweiten Stelle wuerde ein
    `stat()`-Fehscheitern dort den ganzen Start mitreissen."""
    path = tmp_path / "accounts.json"
    path.write_text(_leere_konfiguration(), encoding="utf-8")
    kandidat = tmp_path / ".accounts.json.speichern-tmp-a1B2c3D4"
    kandidat.write_text("x", encoding="utf-8")
    _zurueckdatieren(kandidat, 3600)
    echtes_stat = Path.stat
    echtes_is_file = Path.is_file

    def is_file_ohne_stat(self, *a, **k):
        # umgeht den eigenen stat()-Aufruf von is_file() fuer den Kandidaten,
        # damit NUR der explizite `kandidat.stat()` im Alterscheck faellt —
        # sonst waere nicht klar, WELCHER interne Aufruf scheitern soll.
        if self == kandidat:
            return True
        return echtes_is_file(self, *a, **k)

    def stat_schlaegt_fehl(self, *a, **k):
        if self == kandidat:
            raise OSError(2, "verschwunden zwischen is_file() und stat()")
        return echtes_stat(self, *a, **k)

    monkeypatch.setattr(Path, "is_file", is_file_ohne_stat)
    monkeypatch.setattr(Path, "stat", stat_schlaegt_fehl)

    ConfigStore(str(path))  # darf nicht werfen

    # NICHT `kandidat.exists()`: `Path.exists()` ruft intern ebenfalls
    # `self.stat()` auf (gemessen unter Python 3.12) — mit unserem Patch noch
    # aktiv wuerde JEDE Pruefung ueber `kandidat` immer `False` liefern,
    # unabhaengig vom echten Zustand auf der Platte. `os.path.exists` ist
    # unbeeinflusst, weil nur `pathlib.Path.stat` gepatcht ist.
    assert os.path.exists(str(kandidat)), "durch den simulierten Fehler haette nichts geloescht werden duerfen"


# ---------------------------------------------------------------------------
# Rechte-Anziehen: erst NACH erfolgreichem Parsen, nie ueber einen Symlink
# ---------------------------------------------------------------------------

@POSIX_ONLY
def test_rechte_werden_bei_ungueltiger_konfiguration_nicht_angezogen(tmp_path):
    """KLEIN-Befund (Gegenpruefer, T1f): Die Fehlermeldung von `_load` sagt
    woertlich "was left untouched" — vorher wurden die Rechte trotzdem schon
    VOR dem Parsen angezogen, ein Widerspruch zur eigenen Zusicherung. Rechte
    werden jetzt erst NACH erfolgreichem Parsen angefasst; eine ungueltige
    Konfiguration bleibt in JEDER Hinsicht unangetastet."""
    path = tmp_path / "accounts.json"
    path.write_text("{kaputt", encoding="utf-8")
    os.chmod(path, 0o644)
    os.chmod(tmp_path, 0o700)

    with pytest.raises(RuntimeError, match="left untouched"):
        ConfigStore(str(path))

    modus = stat.S_IMODE(path.stat().st_mode)
    assert oct(modus) == oct(0o644), f"die Rechte wurden trotz ungueltiger Konfiguration geaendert: {oct(modus)}"


@POSIX_ONLY
def test_rechte_werden_bei_verzeichnis_statt_konfiguration_nicht_angezogen(tmp_path):
    """Dieselbe Korrektur, fuer den Fall T1e (Gegenpruefer): Ein Verzeichnis
    an der Stelle von `accounts.json` bekam vorher trotzdem `chmod 0600`,
    obwohl `_load` es Zeilen spaeter als ungueltige Konfiguration verwirft."""
    path = tmp_path / "accounts.json"
    path.mkdir()
    os.chmod(path, 0o755)  # mkdir(mode=...) unterliegt dem umask, ein expliziter chmod nicht
    os.chmod(tmp_path, 0o700)

    with pytest.raises(RuntimeError, match="left untouched"):
        ConfigStore(str(path))

    modus = stat.S_IMODE(path.stat().st_mode)
    assert oct(modus) == oct(0o755), f"die Rechte eines Verzeichnisses wurden veraendert: {oct(modus)}"


@POSIX_ONLY
def test_symlink_konfiguration_wird_nicht_angezogen_sondern_gewarnt(tmp_path, caplog):
    """Mutationsluecke (Gegenpruefer-Vorschlag, VORSCHLAG_naiv_follow_false):
    `os.chmod(pfad, ..., follow_symlinks=False)` waere die naheliegende
    "richtige" Absicherung, ist aber unter Linux fuer Symlinks NICHT
    implementiert (`NotImplementedError`, gemessen) — ein Absturz beim Start.
    Der eigene Code prueft deshalb `is_symlink()` VOR jedem `chmod`-Versuch.
    Zusaetzlich: Ein Symlink auf ein Ziel ausserhalb wird nicht automatisch
    umgestellt, aber auch nicht stillschweigend uebergangen — eine WARNUNG
    nennt den Pfad."""
    aussen = tmp_path / "aussen"
    aussen.mkdir()
    ziel = aussen / "geteilt.json"
    ziel.write_text(_leere_konfiguration(), encoding="utf-8")
    os.chmod(ziel, 0o644)
    daten = tmp_path / "daten"
    daten.mkdir()
    os.chmod(daten, 0o700)
    (daten / "accounts.json").symlink_to(ziel)

    with caplog.at_level("WARNING"):
        ConfigStore(str(daten / "accounts.json"))

    assert oct(stat.S_IMODE(ziel.stat().st_mode)) == oct(0o644), "das Ziel des Symlinks wurde umgestellt"
    eigene = [r for r in caplog.records if r.name == "services.config_store"]
    treffer = [r for r in eigene if "Symlink" in r.getMessage() and str(daten / "accounts.json") in r.getMessage()]
    assert len(treffer) == 1, [r.getMessage() for r in eigene]


@POSIX_ONLY
@pytest.mark.parametrize("fehlercode", [errno.EPERM, errno.EROFS])
def test_chmod_fehler_beim_anziehen_wird_abgefangen(tmp_path, monkeypatch, caplog, fehlercode):
    """Mutationsluecke M13: Der `chmod`-Versuch beim Rechte-Anziehen ist mit
    `except OSError` abgesichert — ein zu eng oder falsch gefasster Fang (hier
    simuliert durch einen anderen Exception-Typ an der Aufrufstelle) wuerde
    bei EPERM (kein Schreibrecht auf den Modus, z. B. fremder Eigentuemer)
    oder EROFS (schreibgeschuetztes Dateisystem) den Start mitreissen, statt
    nur zu warnen."""
    path = tmp_path / "accounts.json"
    path.write_text(_leere_konfiguration(), encoding="utf-8")
    os.chmod(path, 0o644)
    os.chmod(tmp_path, 0o700)
    echtes_chmod = os.chmod

    def chmod_schlaegt_fehl(pfad, modus, *a, **k):
        if str(pfad) == str(path) and modus == 0o600:
            raise OSError(fehlercode, os.strerror(fehlercode))
        return echtes_chmod(pfad, modus, *a, **k)

    monkeypatch.setattr(config_store_module.os, "chmod", chmod_schlaegt_fehl)

    with caplog.at_level("WARNING"):
        ConfigStore(str(path))  # darf nicht werfen

    eigene = [r for r in caplog.records if r.name == "services.config_store"]
    treffer = [r for r in eigene if str(path) in r.getMessage() and "nicht auf" in r.getMessage()]
    assert len(treffer) == 1, [r.getMessage() for r in eigene]
    assert treffer[0].levelname == "WARNING"


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


@pytest.mark.parametrize("wert", [" ", "\t", "  \n "])
def test_git_sha_reiner_leerraum_wird_zu_unknown(wert):
    """KLEIN-Befund dieser Runde: Der bisherige Validator prueft `wert ==
    ""` — eine Umgebungsvariable, die NUR aus Leerraum besteht (denkbar durch
    ein Quoting-Versehen im Baubefehl, z. B. `GIT_SHA=" "`), besteht diesen
    Vergleich NICHT und lief ungeprueft durch: `/api/health` haette
    `"commit":" "` ausgegeben statt ehrlich "unknown". `.strip()` VOR dem
    Leer-Vergleich faengt das ab."""
    einstellungen = Settings(_env_file=None, git_sha=wert)
    assert einstellungen.git_sha == "unknown"


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
# Layer-Cache (`ARG GIT_SHA=unknown` statt eines erfundenen Platzhalters).
# Kein Docker-Aufruf hier (zu langsam fuer die Suite) — die Cache-Wirkung
# selbst ist am echten `docker build` gemessen, dies pinnt nur die TEXTFORM
# fest, die diese Messung voraussetzt.
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
