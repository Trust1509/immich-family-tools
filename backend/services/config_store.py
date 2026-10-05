"""
Persistent config storage: accounts + dismissed match IDs + sync log + managed albums.
Backed by a JSON file on the Docker volume.
"""
import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import stat
import tempfile
import time
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from models.account import Account, AccountCreate
from models.match import LinkedPerson, ManagedAlbum, MultiSyncPersonEntry, PersonRef, SyncLogEntry

logger = logging.getLogger(__name__)

# Ein Schloss je normalisiertem Albumnamen.
#
# Zwischen "welche Gruppe wird es?" und "das Album ist gespeichert" liegen die
# Immich-Aufrufe, und an jedem `await` kann eine zweite Anfrage drankommen.
# Beide sehen dann "diesen Namen gibt es noch nicht" und oeffnen je eine
# Gruppe. Danach ist der Name dauerhaft MEHRDEUTIG: Die Vorschau schweigt fuer
# immer, jedes weitere Album bekommt wieder eine eigene Gruppe, und die
# Oberflaeche bietet keinen Weg zurueck — sie kann nur beitreten, was
# angezeigt wird (Gegenpruefer zu #81, mit asyncio.gather gemessen).
#
# Modulweit, nicht je ConfigStore: Der Container faehrt einen Prozess mit
# einem Store, und ein Schloss, das mit seinem Besitzer entsteht, schuetzt
# nichts. Dasselbe Muster benutzt `sync_service._album_locks` fuer den
# Abgleich.
#
# Der Schluessel traegt die EREIGNISSCHLEIFE mit. In der Anwendung gibt es
# genau eine, dort aendert das nichts — aber ein `asyncio.Lock` gehoert der
# Schleife, in der es zuerst benutzt wurde, und ein Zugriff aus einer anderen
# endet mit "is bound to a different event loop". Ohne den Schleifenanteil
# war die Registrierung von der Reihenfolge abhaengig: Dieselbe Probe lief
# allein gruen und in der vollen Suite rot (gemessen 21.09.2026).
_gruppen_schloesser: dict[tuple[int, str], asyncio.Lock] = {}

# Dasselbe Muster fuer den TREFFER. Es schuetzt eine andere Luecke als das
# Gruppenschloss, und beide werden gebraucht:
#
#   Gruppenschloss  — zwei Anlagen mit demselben NAMEN bekommen eine Gruppe.
#   Trefferschloss  — zwei Anlagen fuer dieselbe KENNUNG bekommen ein Album.
#
# Ein Namensschloss allein reicht hier nicht. Zwei Anfragen mit derselben
# `match_id`, aber verschiedenen Albumnamen naehmen verschiedene Schloesser
# und kaemen beide durch — die Oberflaeche schlaegt den Personennamen nur vor,
# aendern laesst er sich (#86).
#
# REIHENFOLGE, und sie ist die ganze Verklemmungsfrage: Wer beide haelt,
# nimmt IMMER zuerst das Trefferschloss, dann das Gruppenschloss. Der
# umgekehrte Weg existiert heute nirgends — gemessen ueber alle `async with`
# auf ein Schloss im Backend, von zwei Pruefstimmen unabhaengig.
#
# Es gibt zwei WEITERE Schloesser im Backend, und sie gehoeren hierher, auch
# wenn sie sich mit diesen beiden nicht kreuzen (nachgemessen):
#   `sync_service._album_locks`  je verwaltetem Album, im Abgleich. Wird
#                                nirgends unter einem der beiden HIER
#                                genommen — ABER seit #117 nimmt
#                                `ConfigStore.delete_account` es ebenfalls,
#                                EIN Album nach dem anderen, nie zwei
#                                gleichzeitig: Es entfernt Referenzen des
#                                geloeschten Kontos aus jedem betroffenen
#                                Album, unter GENAU dem Schloss, das auch
#                                Refresh/Umbenennen/Erweitern halten, damit
#                                keiner der drei Schreiber eine Loeschung
#                                zurueckdrehen kann, waehrend er selbst auf
#                                Immich wartet (Befund, Issue #117). Verklemmt
#                                sich das nicht mit sich selbst? Nein: Jede
#                                Schleifenrunde haelt hoechstens EIN
#                                `_album_schloss`, nimmt es, schreibt, gibt es
#                                wieder frei, bevor die naechste Runde ein
#                                zweites nimmt — zu keinem Zeitpunkt haelt
#                                `delete_account` zwei Albumschloesser
#                                gleichzeitig, also gibt es auch keine
#                                Reihenfolge zwischen zwei Albumschloessern,
#                                die kippen koennte. Import von
#                                `sync_service` NUR lokal in der Methode
#                                (Kreislauf: `sync_service` importiert
#                                bereits `config_store` auf Modulebene).
#   `MatchCache.lock`            im Treffer-Zwischenspeicher. `get_matches`
#                                laeuft in `create_album` VOR dem
#                                Trefferschloss und gibt es vorher frei.
# Die erste Fassung dieses Absatzes nannte sich vollstaendig und war es am
# Tag ihrer Einfuehrung nicht (Blindpruefer, Nacharbeit 1).
#
# ABER: Was diese Regel traegt, ist DIESER ABSATZ und sonst nichts.
#
# Die Verschachtelung laeuft ueber eine Funktionsgrenze (`create_album` nimmt
# das Trefferschloss, das Gruppenschloss liegt in der aufgerufenen Funktion) —
# wer nur den Text einer Funktion liest, sieht sie gar nicht. Ein kuenftiger
# umgekehrter Weg wuerde also von keiner Probe rot gemacht, und eine
# Verklemmung zeigt sich als haengende Anfrage, nicht als Fehler.
#
# Das ist eine benannte Luecke, kein Versehen: Der Blindpruefer hat sie am
# 22.09.2026 gemessen, ein Waechter dafuer ist ein eigener Slice (Issue in
# diesem Repo). Bis dahin gilt: Wer ein drittes Schloss einfuehrt oder die
# Reihenfolge anfasst, liest diesen Absatz — und traegt seine Stelle hier ein.
#
# Und eine zweite benannte Grenze: Dieses Verzeichnis waechst und wird nie
# geleert, ein `asyncio.Lock` je `match_id`. Dasselbe gilt seit jeher fuer
# `_gruppen_schloesser` oben. Bei der Groessenordnung dieser Anwendung
# (Treffer in Hunderten, ein Prozess, Neustart je Auslieferung) ist das kein
# Problem — es ist nur keines, das jemand geprueft haette.
_treffer_schloesser: dict[tuple[int, str], asyncio.Lock] = {}

# #124 B10 NACHARBEIT 1: `_save` und `_sichere_vor_schemasprung` legen ihre
# Temp-Dateien mit einer UNVERWECHSELBAREN KENNUNG an: Praefix
# `.<Dateiname>.speichern-tmp-`, danach der `mkstemp`-eigene Rest (Buchstaben/
# Ziffern/Unterstrich, Alphabet und Laenge kommen aus
# `tempfile._RandomNameSequence`, heute 8 Zeichen). Vor dieser Nacharbeit war
# der Praefix nur `.<Dateiname>.` OHNE Kennung — und genau das war der Fehler
# (Blind- und Gegenpruefer, a1c6ae8): Eine Handkopie mit zufaellig gleicher
# Laenge (".accounts.json.20260930", ".accounts.json.original",
# ".accounts.json.backup01" — acht Zeichen aus demselben Alphabet) sah fuer
# die alte Aufraeumroutine WIE die eigene Temp-Datei aus und wurde geloescht.
# Die Kennung macht diese Verwechslung strukturell unmoeglich: Eine
# Handkopie, die zufaellig auch noch ".speichern-tmp-" plus acht Zeichen
# traegt, ist so unwahrscheinlich, dass sie nicht mehr die Sorge dieses
# Codes ist (der Betreiber waehlt seine eigenen Dateinamen).
#
# RESTE IM ALTEN MUSTER (aus Versionen vor dieser Nacharbeit, ohne Kennung)
# werden NICHT mehr geloescht — sie koennten ebenso gut eine Handkopie sein,
# und genau diese Verwechslung ist der Fehler, den diese Nacharbeit behebt.
# Sie werden stattdessen einmal je Start als WARNUNG mit Pfad gemeldet:
# „moeglicherweise liegengebliebene Temp-Datei einer aelteren Version —
# pruefen und von Hand loeschen." Nichts verschwindet still (Projektgrundsatz,
# siehe `docs/agents/lehren.md`), aber auch nichts wird mehr geraten.
_TEMP_KENNUNG = "speichern-tmp-"
# Exaktes `mkstemp`-Alphabet/-Laenge — EINE Quelle, von beiden Mustern unten
# per `.pattern` wiederverwendet (kein zweites, driftfaehiges Literal).
_TEMP_REST_MUSTER = re.compile(r"[A-Za-z0-9_]{8}")


def _temp_praefix(name: str) -> str:
    """Der `mkstemp`-Praefix fuer EIGENE Temp-Dateien zu `name` — gemeinsam
    fuer `_save` (name=`self._path.name`) und `_sichere_vor_schemasprung`
    (name=`ziel.name`, also z. B. `accounts.json.vor-schema-3.bak`)."""
    return f".{name}.{_TEMP_KENNUNG}"


def _eigenes_temp_muster(name: str) -> re.Pattern:
    """Erkennt NUR die eigene, neue Temp-Datei-Kennung zu `name` — beide
    Familien (`_save` UND `_sichere_vor_schemasprung`) in einem Muster, weil
    der Zwischenteil bei Letzterer selbst Punkte traegt
    (`vor-schema-<N>.bak` bzw. `vor-kennungsvergabe.bak`).

    DER ZWISCHENTEIL ZAEHLT NUR DIE BEIDEN BEKANNTEN RUECKWEG-ENDUNGEN AUF,
    nicht mehr `(?:\\..+)?` fuer einen BELIEBIGEN Zwischenteil (Gegenpruefer,
    gemessen): Mit dem beliebigen Zwischenteil erkannte `name="accounts.json"`
    auch `.accounts.json.test.speichern-tmp-<8 Zeichen>` als EIGENE
    Temp-Datei — das ist die Leiche einer VOELLIG ANDEREN, fremden
    Konfigurationsdatei (`accounts.json.test`) im selben Ordner, und dieser
    `ConfigStore` loeschte sie trotzdem. Die Aufzaehlung deckt nur, was
    `_temp_praefix` tatsaechlich als `ziel.name` uebergeben bekommt
    (`_sichere_vor_schemasprung`) — kein anderer Zwischenteil ist ein
    moegliches Ergebnis der eigenen Schreiber, verankert (`fullmatch`) an
    Anfang und Ende, damit kein Rest davor oder danach durchrutscht."""
    return re.compile(
        r"^\." + re.escape(name)
        + r"(?:\.vor-schema-\d+\.bak|\.vor-kennungsvergabe\.bak)?\."
        + re.escape(_TEMP_KENNUNG) + _TEMP_REST_MUSTER.pattern + r"$"
    )


def _altes_temp_muster(name: str) -> re.Pattern:
    """Erkennt, was VOR dieser Nacharbeit als eigene Temp-Datei zu `name`
    galt — ohne die neue Kennung, also nicht mehr sicher von einer Handkopie
    zu unterscheiden. Dient NUR der Warnung, nie mehr dem Loeschen (siehe
    Kopf-Kommentar oben)."""
    return re.compile(r"^\." + re.escape(name) + r"(?:\..+)?\." + _TEMP_REST_MUSTER.pattern + r"$")


# Grosszuegige Altersgrenze fuer die Loeschung EIGENER, NEU erkannter
# Temp-Dateien beim Start (Gegenpruefer K3 / Fremdpruefer WICHTIG 1): Eine
# zweite `ConfigStore`-Instanz auf demselben Verzeichnis darf die gerade
# aktive Temp-Datei einer laufenden `_save` NICHT loeschen, waehrend diese
# zwischen `mkstemp` und `os.replace` haengt. Zwei Instanzen auf demselben
# Verzeichnis sind fuer diese Anwendung kein unterstuetztes Betriebsmodell
# (ein Container faehrt einen Prozess mit einem Store, siehe Kopf-Kommentar
# zu `_gruppen_schloesser`) — aber ein Start ist trotzdem kein Ort, an dem
# man sich auf diese Annahme VERLASSEN sollte, wenn eine einzige Zeile sie
# auch ohne Verlass absichert. Eine Altersgrenze ist einfacher und lokaler
# als eine Umstellung auf Ein-Instanz-Erzwingung (z. B. eine Lock-Datei) und
# deckt denselben gemessenen Fall ab. Gewaehlt: 300 Sekunden — der
# eigentliche Schreibvorgang (JSON serialisieren, `fsync`, `chmod`,
# `os.replace`) braucht Millisekunden bis niedrige Sekunden, auch auf
# langsamem Speicher; 300 s liegt zwei Groessenordnungen darueber.
#
# EIN unterhalb der Schwelle liegender Rest bleibt NICHT stumm liegen (seit
# dieser Fassung): Er wird mit Pfad als WARNUNG gemeldet, auch wenn er (noch)
# nicht entfernt wird — siehe `_raeume_verwaiste_temp_dateien`. Und er bleibt
# nicht bis zum naechsten vollen Neustart unbeachtet: Der Anwendungs-Lebenszyklus
# (`main.py`, Start) plant zusaetzlich EINEN einmaligen, verzoegerten zweiten
# Aufraeumdurchlauf ein, der nach genau dieser Altersgrenze noch einmal
# denselben Scan faehrt (`ConfigStore.zweiter_aufraeum_durchlauf`) — ein
# harter Absturz mit sofortigem Neustart (`restart: unless-stopped` faehrt in
# Sekunden wieder hoch) hinterlaesst einen Rest, der beim STARTSCAN zu jung
# ist, aber vom verzoegerten zweiten Durchlauf INNERHALB DERSELBEN laufenden
# Instanz erfasst wird — ohne auf einen weiteren, vielleicht erst Stunden
# spaeter faelligen Neustart zu warten. Ein `fcntl.flock` auf dem Temp-Datei-
# Deskriptor waere eine praezisere Alternative (kein Alter raten, sondern den
# tatsaechlichen Halter fragen) — bewusst NICHT gewaehlt: POSIX-only wie die
# Rechte-Pruefung ohnehin, aber zusaetzlich muesste der Lock ueber die volle
# Lebensdauer von `mkstemp` bis `os.replace` gehalten UND von der Aufraeum-
# routine non-blocking erfragt werden, ohne selbst eine neue Racebedingung
# einzufuehren — mehr neue Flaeche, als diese letzte Nacharbeitsrunde tragen
# soll, und die Altersgrenze deckt denselben gemessenen Fall bereits ab.
# Kein Test misst 300 s durch echtes Warten (zu langsam) — die Proben pruefen
# stattdessen ueber zurueckdatierte `mtime` bzw. eine einstellbare Wartezeit
# fuer den zweiten Durchlauf: eine gerade erst angelegte Temp-Datei (Alter
# ~0 s) bleibt liegen (wird aber gemeldet), eine kuenstlich zurueckdatierte
# (Alter > Schwelle) wird entfernt.
_TEMP_MINDESTALTER_SEKUNDEN = 300.0

# #106: Gruppe ODER Welt darf eine Sicherung/Konfiguration nicht lesen
# koennen. Nur diese beiden Bits zaehlen — Schreibrechte fuer Gruppe/Welt
# waeren ein eigener, staerkerer Befund, den dieses Issue nicht stellt.
_GRUPPE_ODER_WELT_LESBAR = stat.S_IRGRP | stat.S_IROTH


def _verlaessliche_posix_rechte() -> bool:
    """Eigene Funktion statt eines direkten `os.name`-Vergleichs an der
    Aufrufstelle — ausschliesslich, damit ein Test sie gezielt monkeypatchen
    kann, OHNE `os.name` selbst zu veraendern: `pathlib.Path` entscheidet bei
    JEDER Instanziierung anhand von `os.name`, ob es eine `WindowsPath` oder
    `PosixPath` baut, und ein direkt gefaelschtes `os.name` bricht deshalb
    jeden `Path(...)`-Aufruf, der danach im selben Test noch laeuft (gemessen:
    `NotImplementedError: cannot instantiate 'WindowsPath' on your system`
    unter Linux, sobald `os.name` auf `"nt"` steht)."""
    return os.name == "posix"


class ConfigStore:
    SCHEMA_VERSION = 3

    def __init__(self, path: str, log_retention_days: int = 90):
        self._path = Path(path)
        self._log_retention_days = log_retention_days
        self._data: dict = {
            "schema_version": self.SCHEMA_VERSION,
            "accounts": {},
            "dismissed_match_ids": [],
            "sync_log": [],
            "managed_albums": [],
            "linked_people": [],
        }
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def pair_match_id(id_a: str, id_b: str) -> str:
        """Same algorithm as face_matcher._match_id — keep in sync."""
        key = "_".join(sorted([id_a, id_b]))
        return hashlib.md5(key.encode()).hexdigest()

    @staticmethod
    def compute_linked_match_ids(person_refs: list[dict]) -> list[str]:
        """All pairwise MD5 match IDs for the persons in an album."""
        ids = [r["person_id"] for r in person_refs if r.get("person_id")]
        return [
            ConfigStore.pair_match_id(a, b)
            for a, b in combinations(ids, 2)
        ]

    def _album_linked_match_ids(self, album: ManagedAlbum | dict) -> list[str]:
        """Return identity-match IDs without pairing unrelated conditional subjects."""
        raw = album.model_dump() if hasattr(album, "model_dump") else album
        if not str(raw.get("match_id", "")).startswith("conditional_"):
            return self.compute_linked_match_ids(raw.get("person_refs", []))

        album_keys = {
            (ref.get("account_id"), ref.get("person_id"))
            for ref in raw.get("person_refs", [])
        }
        match_ids: list[str] = []
        for linked_id in raw.get("linked_person_ids", []):
            linked = next(
                (
                    item
                    for item in self._data.get("linked_people", [])
                    if item.get("id") == linked_id
                ),
                None,
            )
            if not linked:
                continue
            refs = [
                ref
                for ref in linked.get("person_refs", [])
                if (ref.get("account_id"), ref.get("person_id")) in album_keys
            ]
            match_ids.extend(self.compute_linked_match_ids(refs))
        return list(dict.fromkeys(match_ids))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _raeume_verwaiste_temp_dateien(self) -> None:
        """Liegengebliebene Temp-Dateien von `_save` UND von
        `_sichere_vor_schemasprung` entfernen — beim Start UND, mit demselben
        Code, aus dem einmaligen zweiten Durchlauf im laufenden Betrieb
        (`zweiter_aufraeum_durchlauf` unten).

        Beide Schreiber schreiben erst in eine Temp-Datei (`tempfile.mkstemp`,
        Praefix ueber `_temp_praefix`), dann `os.replace` — der volle Inhalt,
        inklusive Immich-API-Schluesseln, liegt also kurz auf der Platte,
        BEVOR er die eigentliche Datei ersetzt. Stirbt der Prozess hart
        dazwischen (SIGKILL, Stromausfall, OOM-Killer), laeuft das eigene
        `finally` nie — die Temp-Datei bleibt mit vollem Inhalt liegen, bis
        entweder ein spaeterer Lauf dieser Methode sie erfasst oder jemand sie
        von Hand findet.

        NUR Dateien, die EXAKT dem eigenen, NEUEN Namensmuster entsprechen
        (`_eigenes_temp_muster`, Kennung `_TEMP_KENNUNG`), werden entfernt —
        und auch dann nur, wenn sie REGULAERE Dateien sind (kein Symlink,
        kein Verzeichnis) UND ihre Aenderungszeit mindestens
        `_TEMP_MINDESTALTER_SEKUNDEN` zurueckliegt (schuetzt die Temp-Datei
        einer GERADE laufenden zweiten Instanz auf demselben Verzeichnis vor
        vorzeitigem Loeschen, siehe Begruendung dort). Ein Symlink wird nicht
        angefasst — NICHT weil `unlink()` sein Ziel loeschen wuerde (tut es
        nie: `unlink()` entfernt immer nur den Verzeichniseintrag selbst,
        gemessen), sondern weil ein Betreiber-Symlink mit zufaellig
        passendem Namen sonst wortlos verschwaende, ohne dass irgendein
        Nutzen dem gegenuebersteht.

        Ein Fund, der (noch) NICHT geloescht wird, weil er juenger als die
        Altersgrenze ist ODER eine Aenderungszeit in der Zukunft traegt, wird
        trotzdem gemeldet (WARNUNG mit Pfad) — nichts verschwindet still, aber
        auch nichts wird beim ersten Anblick schon geloescht: Genau dieser
        Fund ist es, den der zweite Durchlauf spaeter erneut sieht und dann,
        sobald er die Altersgrenze ueberschritten hat, entfernt.

        RESTE IM ALTEN MUSTER (ohne Kennung, aus Versionen vor der Einfuehrung
        der Kennung — `_altes_temp_muster`) werden NICHT geloescht, weil sie
        nicht mehr sicher von einer Handkopie mit zufaellig gleicher Laenge
        zu unterscheiden sind (genau das war der urspruengliche Fehler:
        Handkopien wie `.accounts.json.20260930` oder
        `.accounts.json.original` wurden vorher geloescht). Sie werden
        stattdessen einmal je Fund als Warnung mit Pfad gemeldet. Eine
        fremde Datei, die zu KEINEM der beiden Muster passt, bleibt
        unangetastet und ungemeldet.

        Laeuft bei JEDEM Start, unabhaengig davon, ob `self._path` selbst
        existiert (ein Absturz kann die Konfiguration selbst verloren, die
        Temp-Datei aber ueberlebt haben).
        """
        try:
            geschwister = list(self._path.parent.iterdir())
        except OSError:
            return
        neu_muster = _eigenes_temp_muster(self._path.name)
        alt_muster = _altes_temp_muster(self._path.name)
        jetzt = time.time()
        for kandidat in geschwister:
            name = kandidat.name
            if neu_muster.fullmatch(name):
                if kandidat.is_symlink() or not kandidat.is_file():
                    logger.warning(
                        "Traegt die eigene Temp-Datei-Kennung, ist aber "
                        "keine reguläre Datei (Symlink oder Verzeichnis) — "
                        "unangetastet gelassen: %s", kandidat,
                    )
                    continue
                try:
                    alter_sekunden = jetzt - kandidat.stat().st_mtime
                except OSError:
                    continue
                if alter_sekunden < _TEMP_MINDESTALTER_SEKUNDEN:
                    # Vermutlich eine gerade laufende `_save`/`_sichere_vor_
                    # schemasprung` (dieser oder einer zweiten Instanz auf
                    # demselben Verzeichnis) — noch nicht anfassen. NICHT
                    # STILL: Ein Absturz mit sofortigem Neustart (`restart:
                    # unless-stopped`) hinterlaesst hier genau denselben
                    # Befund wie eine echte laufende Instanz — von aussen
                    # ununterscheidbar. Also wird gemeldet, mit Pfad, auch
                    # wenn (noch) nichts geloescht wird; der zweite Durchlauf
                    # (`zweiter_aufraeum_durchlauf`) sieht denselben Kandidaten
                    # spaeter erneut, wenn die Altersgrenze ueberschritten ist.
                    logger.warning(
                        "Traegt die eigene Temp-Datei-Kennung, ist aber "
                        "juenger als die Altersgrenze (%.0fs) oder traegt "
                        "eine Aenderungszeit in der Zukunft — noch nicht "
                        "entfernt: %s",
                        _TEMP_MINDESTALTER_SEKUNDEN, kandidat,
                    )
                    continue
                try:
                    kandidat.unlink()
                    logger.warning(
                        "Liegengebliebene Temp-Datei beim Start entfernt: %s",
                        kandidat,
                    )
                except OSError as exc:
                    logger.warning(
                        "Liegengebliebene Temp-Datei konnte nicht entfernt werden: %s (%s)",
                        kandidat, exc,
                    )
            elif alt_muster.fullmatch(name):
                logger.warning(
                    "Moeglicherweise liegengebliebene Temp-Datei einer "
                    "aelteren Version — pruefen und von Hand loeschen: %s",
                    kandidat,
                )

    async def zweiter_aufraeum_durchlauf(self, *, verzoegerung_sekunden: Optional[float] = None) -> None:
        """Genau EIN verzoegerter zweiter Aufraeumdurchlauf im laufenden
        Betrieb — schliesst die Luecke, die der reine Start-Scan offen laesst:
        Ein Absturz mit sofortigem Neustart (`restart: unless-stopped` faehrt
        in Sekunden wieder hoch) hinterlaesst einen Rest, der beim Start noch
        juenger als `_TEMP_MINDESTALTER_SEKUNDEN` ist — er wird gemeldet
        (siehe `_raeume_verwaiste_temp_dateien`), aber nicht entfernt, und
        blieb vor dieser Aenderung bis zum NAECHSTEN vollen Neustart liegen,
        der je nach Betrieb Stunden oder Tage entfernt sein kann.

        Wartet einmalig `verzoegerung_sekunden` (Vorgabe: dieselbe
        Altersgrenze wie der Start-Scan, `_TEMP_MINDESTALTER_SEKUNDEN`) und
        fuehrt dann GENAU EINMAL denselben Scan wie beim Start erneut aus.
        Kein wiederkehrender Zeitplan: Ein Rest, der auch nach diesem zweiten
        Durchlauf noch juenger als die Grenze waere, ist kein plausibler
        Absturzrest mehr, sondern eine tatsaechlich laufende zweite Instanz —
        und genau die soll dieser Code nicht anfassen (siehe Begruendung bei
        `_TEMP_MINDESTALTER_SEKUNDEN`).

        `verzoegerung_sekunden` ist ausschliesslich fuer Tests da: Kein Test
        wartet 300 echte Sekunden — die Probe setzt hier eine kurze Wartezeit
        und arbeitet mit einer zurueckdatierten `mtime`, um denselben
        Ablaufzustand zu erzwingen, den eine echte Wartezeit erzeugen wuerde.

        FEHLER BRECHEN NICHTS: Diese Koroutine laeuft als eigene
        Hintergrundaufgabe (`main.py`, Start), nicht im Anfrage-Pfad. Ein
        Fehler im Scan selbst (`_raeume_verwaiste_temp_dateien` faengt
        `OSError` bereits selbst ab) wird zusaetzlich hier abgefangen, damit
        eine unerwartete Ausnahme nicht als unbehandelte Task-Exception
        endet. `asyncio.CancelledError` wird NICHT abgefangen — sie muss beim
        Herunterfahren (`main.py`, Shutdown) ungehindert durchlaufen, damit
        die Aufgabe als sauber abgebrochen gilt, nicht als beendet.
        """
        warte = _TEMP_MINDESTALTER_SEKUNDEN if verzoegerung_sekunden is None else verzoegerung_sekunden
        await asyncio.sleep(warte)
        try:
            self._raeume_verwaiste_temp_dateien()
        except Exception:
            logger.exception(
                "Zweiter Aufraeum-Durchlauf ist fehlgeschlagen — der naechste "
                "reguläre Start raeumt spaetestens dann auf."
            )

    def _ziehe_eigene_rechte_an(self) -> None:
        """`accounts.json` selbst zieht beim Laden auf `0600` an, wenn sie
        noch fuer Gruppe oder Welt lesbar ist — genau wie `_save()` es bei
        jedem eigenen Schreibvorgang ohnehin tut (siehe dort). Vorher stand in
        `docs/BACKUP_RESTORE.md` faelschlich, dies loese eine WARNUNG aus —
        es geschah gar nichts. Diese Methode macht die Doku-Aussage wahr,
        statt sie nur zu korrigieren: Die Konfiguration bleibt nicht mehr
        offen liegen, bis der naechste `_save()` zufaellig kommt.

        LAEUFT ERST NACH ERFOLGREICHEM PARSEN (Aufrufstelle: `_load`, NACH dem
        Schema-Check, VOR `_migrate`) — eine fruehere Fassung zog die Rechte
        VOR dem Parsen an, aus `_warne_bei_offenen_rechten` heraus. Das
        widersprach der eigenen Fehlermeldung eine Handvoll Zeilen weiter
        unten ("was left untouched"): Ein Verzeichnis oder eine kaputte
        Konfiguration an dieser Stelle bekam trotzdem schon `chmod 0600`,
        bevor `_load` sie ueberhaupt als ungueltig verwarf (Gegenpruefer,
        gemessen an einem Verzeichnis und an kaputtem JSON mit `0644`).

        SYMLINKS WERDEN NICHT ANGEZOGEN, nur gemeldet — und zwar aus zwei
        Gruenden, nicht nur einem: Erstens waere `os.chmod(pfad, ...,
        follow_symlinks=False)` die naheliegende "richtige" Absicherung gegen
        das Folgen des Links, aber sie ist unter Linux fuer Symlinks NICHT
        implementiert (`NotImplementedError`, KEINE `OSError` — ein
        ungefangener Absturz beim Start, gemessen), also wird `is_symlink()`
        VOR jedem `chmod`-Versuch geprueft, nie `follow_symlinks=False`
        benutzt. Zweitens waere selbst ein gewoehnliches `chmod` (das dem Link
        folgt) kein Datenschutz-Loch im eigentlichen Sinne — es zieht die
        Rechte des ZIELS an, nicht die eines fremden Dritten —, aber es ist
        eine Nebenwirkung auf eine Datei AUSSERHALB des Datenordners, die der
        Betreiber bewusst so verlinkt haben kann; das gehoert gemeldet, nicht
        stillschweigend veraendert. NUR REGULAERE Dateien werden angezogen
        (`stat.S_ISREG`) — ein Verzeichnis an dieser Stelle, das `_load`
        ohnehin gleich als ungueltige Konfiguration verwirft, wird nicht mehr
        angefasst, seit die Reihenfolge oben korrigiert ist.

        Laeuft NICHT, wenn die Datei noch gar nicht existiert (erster Start,
        `stat()` wirft dann `OSError`) — dort gibt es nichts anzuziehen, das
        erledigt der erste `_save()`. Laeuft ebenfalls nicht auf Systemen ohne
        verlaessliche POSIX-Rechte (siehe `_verlaessliche_posix_rechte`) — sie
        wird nicht mehr nur ueber die Aufrufreihenfolge in `_warne_bei_
        offenen_rechten` davor geschuetzt, sondern prueft das jetzt selbst,
        weil sie seit dieser Fassung unabhaengig von dort aufgerufen wird.
        """
        if not _verlaessliche_posix_rechte():
            return
        if self._path.is_symlink():
            logger.warning(
                "Eigene Konfiguration ist ein Symlink — Rechte werden NICHT "
                "automatisch angezogen: %s", self._path,
            )
            return
        try:
            st = self._path.stat()
        except OSError:
            return
        if not stat.S_ISREG(st.st_mode):
            return
        modus = stat.S_IMODE(st.st_mode)
        if not (modus & _GRUPPE_ODER_WELT_LESBAR):
            return
        try:
            os.chmod(self._path, 0o600)
            logger.info(
                "Rechte der eigenen Konfiguration beim Laden auf 0600 gezogen (war %s): %s",
                oct(modus), self._path,
            )
        except OSError as exc:
            logger.warning(
                "Rechte der eigenen Konfiguration konnten beim Laden nicht auf "
                "0600 gezogen werden (%s): %s", exc, self._path,
            )

    def _warne_bei_offenen_rechten(self) -> None:
        """#106: beim Start einmal warnen, wenn eine Geschwisterdatei der
        Konfiguration — oder ihr Verzeichnis — fuer Gruppe oder Welt lesbar ist.

        NUR WARNEN: nichts aendern, nichts abbrechen. Der Betreiber kann
        Gruende haben, und ein Start, der an einer Dateirechte-Frage
        scheitert, ist schlimmer als das Leck, vor dem die Warnung schuetzt
        (Anlass: eine drei Monate alte Handkopie mit `0644` beim Rollout von
        1.8.0, mit Immich-API-Schluesseln von womoeglich laengst geloeschten
        Konten).

        Geprueft wird jede DATEI NEBEN der Konfiguration, deren Name mit dem
        der Konfiguration PLUS TRENNPUNKT beginnt (`accounts.json.bak`,
        `accounts.json.vor-schema-3.bak`, eine Handkopie
        `accounts.json.pre-v1.2.0`, …) — der Trennpunkt ist Pflicht
        (NACHARBEIT 1: vorher reichte ein blosser `startswith`, und eine
        voellig fremde Datei wie `accounts.json2` waere mitgezaehlt worden,
        Mutationsluecke P8), sowie GENAUSO jede VERSTECKTE Handkopie mit
        fuehrendem Punkt (`.accounts.json.alt`, `.accounts.json.20260930`) —
        die erste Fassung dieser Pruefung fand solche Dateien gar nicht,
        weil ihr Name nicht mit `accounts.json` beginnt, sondern mit einem
        Punkt (KLEIN-Befund) — sowie das Verzeichnis selbst. `accounts.json`
        selbst bewusst NICHT hier: siehe `_ziehe_eigene_rechte_an`, die
        diesen Fall selbst behebt statt nur zu warnen — und die seit dieser
        Fassung NICHT mehr von HIER aus aufgerufen wird, sondern von `_load`,
        NACH erfolgreichem Parsen (siehe dort und die eigene Begruendung bei
        `_ziehe_eigene_rechte_an`).

        AUF SYSTEMEN OHNE VERLAESSLICHE POSIX-RECHTE WIRD GESCHWIEGEN — aber
        sichtbar, nicht stumm: `os.name != "posix"` ist der Test (nicht nur
        `"nt"`), weil `st_mode` auch auf manchen Nicht-POSIX-Dateisystemen
        wenig sagt. Unter Windows liefert `st_mode` fuer jede Datei denselben
        Wert (`0o666`), unabhaengig vom tatsaechlichen Zugriff (gemessen,
        siehe `test_sicherung_bekommt_enge_rechte`) — eine Warnung darauf
        waere eine falsche Behauptung, kein Fund. Aus demselben Grund laeuft
        `_ziehe_eigene_rechte_an` NUR, wenn diese Methode nicht vorher schon
        abbricht (Aufrufreihenfolge in `_load`).
        """
        if not _verlaessliche_posix_rechte():
            logger.info(
                "Rechte-Warnung fuer %s uebersprungen: keine verlaesslichen "
                "POSIX-Rechte auf diesem System (os.name=%r).",
                self._path.name, os.name,
            )
            return
        name = self._path.name
        praefixe = (f"{name}.", f".{name}.")
        try:
            geschwister = sorted(
                p for p in self._path.parent.iterdir()
                if p.name != name and p.name.startswith(praefixe)
            )
        except OSError as exc:
            logger.warning(
                "Rechte-Warnung fuer %s konnte Verzeichnis nicht lesen: %s",
                self._path.name, exc,
            )
            return
        for kandidat in [self._path.parent, *geschwister]:
            try:
                st = kandidat.stat()
            except OSError:
                continue
            modus = stat.S_IMODE(st.st_mode)
            if modus & _GRUPPE_ODER_WELT_LESBAR:
                logger.warning(
                    "%s ist fuer Gruppe oder Welt lesbar (Modus %s): %s",
                    "Verzeichnis" if stat.S_ISDIR(st.st_mode) else "Datei",
                    oct(modus), kandidat,
                )

    def _load(self) -> None:
        self._raeume_verwaiste_temp_dateien()
        self._warne_bei_offenen_rechten()
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
                if not isinstance(self._data, dict) or not isinstance(self._data.get("accounts", {}), dict):
                    raise ValueError("invalid configuration schema")
                self._data.setdefault("managed_albums", [])
                self._data.setdefault("linked_people", [])
                logger.info("Config loaded from %s", self._path)
                # ERST NACH erfolgreichem Parsen (siehe `_ziehe_eigene_
                # rechte_an`s eigene Begruendung): Eine Konfiguration, die
                # gleich darunter als ungueltig verworfen wird, bleibt jetzt
                # WIRKLICH unangetastet, auch in ihren Rechten.
                self._ziehe_eigene_rechte_an()
                self._migrate()
            except Exception as exc:
                raise RuntimeError(
                    f"Configuration {self._path} is invalid and was left untouched. "
                    f"Restore a ZFS snapshot, {self._path}.vor-schema-*.bak "
                    f"(the state before the last schema migration), "
                    f"{self._path}.vor-kennungsvergabe.bak (the state before the last "
                    f"identifier assignment) or "
                    f"{self._path}.bak (may already carry the migrated state)."
                ) from exc

    def _sichere_vor_schemasprung(self, *, einmalig: bool) -> None:
        """Rueckweg vor einer unumkehrbaren Migrations-Arbeit — zwei Faelle,
        eine Routine: `einmalig=True` vor einem Schemasprung (versioniert;
        ein BRAUCHBARER Rueckweg wird nie ueberschrieben, ein unbrauchbarer
        schon, siehe unten), `einmalig=False` vor einer Kennungsvergabe (eine
        Generation, jedes Mal erneuert). Der Name der Methode nennt nur den
        ersten Fall (historisch, Umfang dieses Slices deckt keine
        Umbenennung); welcher Fall vorliegt, unterscheidet `einmalig`, und
        seit #105 auch das Protokoll (siehe unten).

        DIE ZWEI FAELLE SCHLIESSEN EINANDER NICHT AUS: Ein Altbestand ohne
        `schema_version` UND mit einem Album ohne `group_id` loest in EINEM
        einzigen `_migrate()`-Lauf BEIDE Zweige aus — erst `einmalig=True`,
        dann `einmalig=False` (die Reihenfolge, in der `_migrate()` beide
        Aufrufe absetzt) — und schreibt in diesem Fall beide Rueckweg-
        Dateien und beide Protokollzeilen (gemessen, Nacharbeit 2 zu #105).
        DAS GILT NICHT IMMER (#120): Liegt am Schemasprung-Ziel schon ein
        BRAUCHBARER `vor-schema-*.bak`, kehrt der `einmalig=True`-Zweig ganz
        oben in dieser Methode fruehzeitig zurueck, ohne zu schreiben und
        ohne zu protokollieren — dann entsteht nur die Kennungsvergabe-Zeile.
        „Kennungsvergabe ohne Schemaaenderung" beschreibt deshalb nur den
        AUSLOESER dieses Zweigs (eine fehlende Kennung, unabhaengig von der
        Schemaversion), nicht eine Garantie, dass kein Schemasprung im
        selben Lauf mitlaeuft.

        DIE REIHENFOLGE DER BEIDEN AUFRUFE IN `_migrate()` IST JETZT FESTGEHALTEN,
        nicht mehr nur behauptet (Nacharbeit 1 zu #114/#116/#111/#120, Sonde S8,
        D2): Jeder Zweig liest und schreibt zwar seine EIGENE Zieldatei — an
        den beiden Rueckweg-DATEIEN aendert eine Vertauschung nichts —, aber
        beide Zweige protokollieren ueber denselben Logger, und die REIHENFOLGE
        der beiden Protokollzeilen folgt sichtbar der Aufrufreihenfolge. Eine
        erste Fassung dieses Docstrings behauptete deshalb fälschlich, die
        Reihenfolge sei „bedeutungslos" — eine Mutation, die die beiden Aufrufe
        vertauscht (D2), blieb damals unter der ALTEN, mengenbasierten Fassung
        von `test_mischfall_schemasprung_und_kennungsvergabe_bekommen_beide_
        rueckwege` unbemerkt gruen. Seit die drei Nacharbeit-Funde D1/D7, D4, D5
        (verdoppelte Zeile — zwei Mutationen fuer denselben Fund —, falsche
        Stufe, zusaetzliche Warnung; vier Kennungen fuer drei Funde) diesen Test auf
        eine LISTE in fester Reihenfolge umgestellt haben, faengt genau dieselbe
        Probe auch D2 — selbst GEMESSEN, nicht aus einer fruehen Sonden-Notiz
        uebernommen: eine Vertauschung macht `test_mischfall_...` jetzt rot,
        weil die beiden Protokollzeilen dann in der falschen Reihenfolge
        ankommen.

        Die gewoehnliche `.bak` traegt den Vor-Zustand nur bis zum naechsten
        Schreibvorgang — und in der laufenden Anwendung ist das das
        `_backfill_user_ids` im Startup, das fuer GENAU die alten
        Installationen feuert, die auch die Wanderung brauchen. Der Rueckweg
        lebte also Millisekunden (Gegenpruefer zu #78, gemessen).

        Ein BRAUCHBARER Rueckweg wird nie ueberschrieben — auch nicht bei
        einem zweiten Sprung (hoch, zurueck auf die alte Fassung, wieder
        hoch). Ein UNBRAUCHBARER dagegen schon: `exists()` allein
        unterschied eine abgeschnittene Teildatei nicht von einer gueltigen
        Sicherung und machte den kaputten Zustand dauerhaft und stumm — mit
        einem Dateinamen davor, der Sicherheit vortaeuscht (beide
        Panel-Stimmen 21.09.2026, gemessen).

        Geschrieben wird wie in `_save`: Temp-Datei, `fsync`, `os.replace`.
        Ein blankes `copy2` waere weniger haltbar als die Datei, die es
        sichern soll — ausgerechnet in dem Szenario, fuer das es da ist.
        """
        if einmalig:
            # EINMALIG, nie ueberschrieben: der Schemasprung. Er passiert je
            # Version genau einmal, und der Zustand davor ist der einzige, zu
            # dem man zurueck WILL.
            ziel = self._path.parent / f"{self._path.name}.vor-schema-{self.SCHEMA_VERSION}.bak"
            if self._rueckweg_brauchbar(ziel):
                return
        else:
            # EINE GENERATION, jedes Mal erneuert: die Kennungsvergabe. Sie
            # kann sich wiederholen (eine aeltere Fassung legt ein Album ohne
            # Kennung an), und dann ist der gewollte Rueckweg der Zustand vor
            # dem LETZTEN Lauf — nicht der von vor Monaten.
            #
            # Die erste Fassung benutzte fuer beides dieselbe Datei. Folge,
            # gemessen: Nach der ersten Wanderung bekam jede weitere
            # Kennungsvergabe gar keinen Rueckweg mehr, und wer die
            # vorhandene Sicherung zurueckspielte, verlor alles seither
            # (Blindpruefer 21.09.2026).
            ziel = self._path.parent / f"{self._path.name}.vor-kennungsvergabe.bak"

        if ziel.exists() and not self._rueckweg_brauchbar(ziel):
            logger.warning("Unbrauchbarer Rueckweg wird ersetzt: %s", ziel)

        temp_name = None
        try:
            roh = self._path.read_bytes()
            fd, temp_name = tempfile.mkstemp(prefix=_temp_praefix(ziel.name), dir=ziel.parent)
            with os.fdopen(fd, "wb") as handle:
                handle.write(roh)
                handle.flush()
                # NICHT durch einen Test beweisbar, und das steht hier statt
                # eines Wachters: Haltbarkeit zeigt sich erst bei einem
                # Strom- oder Kernel-Ausfall. `_save` tut dasselbe aus
                # demselben Grund. Ohne diese Zeile waere die Sicherung
                # weniger haltbar als die Datei, die sie sichert —
                # ausgerechnet in dem Szenario, fuer das sie da ist.
                os.fsync(handle.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, ziel)
            temp_name = None
        except OSError:
            # Ein fehlgeschlagener Rueckweg darf den Start nicht verhindern.
            # Diese Zeile ist die Zusage, dass eine kaputte Konfiguration
            # gemeldet wird und eine fehlende SICHERUNG nicht — ohne sie
            # startet die Anwendung gar nicht mehr und behauptet dabei, die
            # Konfiguration sei ungueltig, obwohl sie unversehrt ist
            # (Blindpruefer 21.09.2026, gemessen).
            #
            # ZWEI FAELLE, ZWEI TEXTE (#105): Bis hierher stand in BEIDEN
            # Zweigen "Sicherung vor Schemasprung nicht moeglich" — auch in
            # DIESEM Zweig (`einmalig=False`), dessen Ausloeser eine fehlende
            # Kennung ist, NICHT zwingend ein Schemasprung (die beiden
            # Zweige schliessen einander nicht aus, siehe Docstring oben).
            # Beim echten Rollout von 1.8.0 (Schema 2 -> 3) standen deshalb
            # zwei Zeilen im Protokoll, die dasselbe Wort trugen, obwohl nur
            # eine ein Schemasprung war (Beleg: Rollout-Protokoll in Issue
            # #105).
            #
            # ASCII "moeglich" bewusst NICHT auf "möglich" umgestellt: Zwei
            # bestehende Proben (`test_gescheiterte_sicherung_verhindert_den_
            # start_nicht`, `test_ein_verzeichnis_an_der_stelle_wird_nicht_
            # fuer_eine_sicherung_gehalten`) pruefen die Zeichenkette
            # "nicht moeglich" in ASCII-Schreibweise gegen `caplog` — eine
            # echte Umlautschreibung waere ein anderer String und haette
            # beide Proben LAUT rot gemacht, nicht stumm zerbrochen (Issue #105).
            if einmalig:
                logger.warning(
                    "Rueckweg vor Schemasprung auf Version %s nicht moeglich: %s",
                    self.SCHEMA_VERSION, ziel,
                )
            else:
                logger.warning(
                    "Rueckweg vor Kennungsvergabe nicht moeglich: %s", ziel,
                )
            return
        finally:
            # EIGENER Fang: Ein gescheitertes Aufraeumen lief am Zweig darueber
            # VORBEI, und `_load` machte daraus wieder "Configuration is
            # invalid" — die Anwendung startete nicht, obwohl die
            # Konfiguration unversehrt war. Erreichbar genau dort, wofuer die
            # Sicherung da ist: voller Datentraeger (Blindpruefer 21.09.2026,
            # gemessen).
            if temp_name:
                try:
                    if os.path.exists(temp_name):
                        os.unlink(temp_name)
                except OSError:
                    logger.warning("Temp-Datei der Sicherung blieb liegen: %s", temp_name)
        # Dieselbe Unterscheidung fuer den Erfolgsfall (#105): "Sicherung vor
        # Schemasprung" stand vorher auch dann im Protokoll, wenn der Rueckweg
        # in Wahrheit eine Kennungsvergabe war.
        if einmalig:
            logger.info(
                "Rueckweg vor Schemasprung auf Version %s: %s", self.SCHEMA_VERSION, ziel,
            )
        else:
            logger.info("Rueckweg vor Kennungsvergabe: %s", ziel)

    @staticmethod
    def _rueckweg_brauchbar(ziel: Path) -> bool:
        """Ist an dieser Stelle eine Sicherung, mit der man WIRKLICH zurueck kann?

        Nicht "liegt da etwas" — gemessen wurden drei Zustaende, die alle
        `exists()` bestehen und keinen Rueckweg bieten: eine abgeschnittene
        Teildatei nach vollem Datentraeger, ein Verzeichnis, und ein Verweis
        auf eine fremde Datei. Die ersten beiden faengt diese Pruefung; der
        dritte nur, solange die fremde Datei kein formgleiches JSON ist
        (siehe die benannte Grenze unten).

        BENANNTE GRENZE: Geprueft wird auf lesbares JSON mit einem
        `accounts`-Schluessel. Ein Verweis auf eine FREMDE, aber
        formgleiche Konfiguration kaeme durch. Weiter zu gehen hiesse, den
        Inhalt gegen die laufende Datei zu vergleichen — und genau die soll
        er ja NICHT sein.
        """
        try:
            # Kein `is_file()` davor: Ein Verzeichnis laesst `read_text`
            # ohnehin mit OSError scheitern, und ein Verweis auf eine Datei
            # gilt `is_file()` als Datei — die Zeile fing also nichts, was
            # der Fang darunter nicht schon faengt. Gemessen: Ihre Mutation
            # ueberlebte die volle Suite.
            inhalt = json.loads(ziel.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return isinstance(inhalt, dict) and "accounts" in inhalt

    def _migrate(self) -> None:
        """One-time repair of managed_albums: fill missing fields from live account data.

        RAEUMT SEIT NACHARBEIT 2 (#117/#121/#103, BLOCKER) AUCH TOTE
        KONTOREFERENZEN, EINMAL BEIM START: `sync_service`s Schloss-Wrapper
        (`refresh_managed_album`, `rename_managed_album`, `extend_match`)
        raeumen tote Referenzen jetzt bei JEDEM eigenen Ausgang unter ihrem
        Albumschloss (`_raeume_tote_referenzen_synchron`) — aber nur, wenn
        WENIGSTENS EINMAL noch eine dieser drei Routinen (oder ein Abgleich
        ueber `delete_account`) fuer das betroffene Album laeuft. Ein Album,
        das VOR diesem Fix verwaist ist und seither nie wieder angefasst
        wurde (kein Refresh, kein Umbenennen, keine Erweiterung, keine
        weitere Kontoloeschung), traegt die tote Referenz sonst UNBEGRENZT
        weiter — auch nach einem Neustart. `_migrate` laeuft bei JEDEM Start
        (`ConfigStore.__init__` -> `_load` -> `_migrate`) und ist damit die
        Stelle, die diesen Fall unabhaengig vom weiteren Betrieb schliesst.
        Dieselbe Filterregel wie ueberall sonst: eine Referenz auf ein Konto,
        das nicht (mehr) in `accounts` steht, wird verworfen, nie neu
        angehaengt.
        """
        accounts = self._data.get("accounts", {})
        albums = self._data.get("managed_albums", [])
        changed = False

        # Der Rueckweg haengt an der unumkehrbaren ARBEIT, nicht an der
        # Versionsnummer — und er wird aus der PLATTE kopiert, nicht aus
        # `self._data`. Eine fruehere Fassung begruendete die Platzierung mit
        # "VOR jeder Aenderung, danach waere der Vor-Zustand schon weg". Das
        # stimmte nicht: Solange `_save()` nicht gelaufen ist, liegt der
        # Vor-Zustand unveraendert auf der Platte. Tragend ist nur, dass die
        # Sicherung VOR dem ersten `_save()` passiert (Gegenpruefer
        # 21.09.2026, gemessen). `_backfill_group_ids` vergibt dauerhafte
        # Gruppenkennungen auch ohne Schemasprung — etwa fuer ein Album, das
        # eine aeltere Fassung ohne Kennung angelegt hat. Die erste Fassung
        # haengte die Sicherung allein an die Version und liess genau diesen
        # Pfad ungesichert (Gegenpruefer 21.09.2026, gemessen).
        sprung = self._data.get("schema_version") != self.SCHEMA_VERSION
        kennungen_fehlen = any(not a.get("group_id") for a in albums)
        if sprung:
            self._sichere_vor_schemasprung(einmalig=True)
        if kennungen_fehlen:
            self._sichere_vor_schemasprung(einmalig=False)
        if sprung:
            self._data["schema_version"] = self.SCHEMA_VERSION
            changed = True
        self._data.setdefault("accounts", {})
        self._data.setdefault("dismissed_match_ids", [])
        self._data.setdefault("synced_name_match_ids", [])
        self._data.setdefault("sync_log", [])
        self._data.setdefault("auto_sync", {"enabled": False, "time": "01:00"})
        self._data.setdefault("linked_people", [])

        for album in albums:
            album_name = album.get("album_name", "")

            # TOTE KONTOREFERENZEN EINMAL BEIM START (Nacharbeit 2, BLOCKER,
            # siehe Methoden-Docstring oben) — VOR dem Auffuellen unten, damit
            # dessen Schleife nicht mehr an einer Referenz arbeitet, die
            # gleich darauf ohnehin verworfen wird.
            urspruengliche_refs = album.get("person_refs", [])
            gefilterte_refs = [
                r for r in urspruengliche_refs if r.get("account_id") in accounts
            ]
            if len(gefilterte_refs) != len(urspruengliche_refs):
                album["person_refs"] = gefilterte_refs
                changed = True

            for ref in album.get("person_refs", []):
                acc = accounts.get(ref.get("account_id", ""), {})
                # Fill account_color from live accounts dict
                if acc and not ref.get("account_color"):
                    ref["account_color"] = acc.get("color", "#6366f1")
                    changed = True
                # Fill account_name from live accounts dict
                if acc and not ref.get("account_name"):
                    ref["account_name"] = acc.get("name", "")
                    changed = True
                # Fill person_name with album_name as canonical fallback
                if not ref.get("person_name"):
                    ref["person_name"] = album_name
                    changed = True

            # Recompute linked_match_ids — always authoritative
            computed = self._album_linked_match_ids(album)
            if set(album.get("linked_match_ids", [])) != set(computed):
                album["linked_match_ids"] = computed
                changed = True
            if "linked_person_ids" not in album:
                album["linked_person_ids"] = []
                changed = True
            if not album.get("condition_person_count"):
                album["condition_person_count"] = len({
                    (ref.get("account_id"), ref.get("person_id"))
                    for ref in album.get("person_refs", [])
                })
                changed = True

        if self._backfill_group_ids(albums):
            changed = True

        if changed:
            logger.info("Config migration applied; saving.")
            self._save()

    @staticmethod
    def _name_key(album_name: str) -> str:
        """Die Normalisierung, die bis v1.6.0 der Gruppenschluessel WAR.

        Sie lebt weiter — aber nur noch als Zuordnungshilfe beim Anlegen und
        beim einmaligen Uebernehmen von Altbestaenden, nicht mehr als
        Identitaet einer Gruppe.

        UNICODE-FEST SEIT #83. Vorher stand hier `strip().lower()`, und das
        war seit #81 eine falsche ZUSAGE an den Nutzer: `existing_group_for_name`
        antwortete „keine Gruppe" fuer zwei sichtbar gleiche Namen, der Nutzer
        legte eine zweite Gruppe an und wusste nicht, dass er eine hatte.
        Gemessen wurde das ueber `GET /api/sync/album-group`: „Café" in NFC
        fand „Café" in NFD nicht, „Strassenfest" fand „Straßenfest" nicht.

        Die Form ist NFC, dann `casefold`, **dann noch einmal NFC**:

        * `casefold` statt `lower`, weil `lower` sprachabhaengige Faelle nicht
          aufloest — `ß` gegen `ss`, `ﬁ` gegen `fi`.
        * NFC, weil dieselben sichtbaren Zeichen in zwei Byte-Folgen vorliegen
          koennen, je nachdem, welches Geraet sie erzeugt hat.
        * Das ZWEITE NFC ist keine Vorsicht, sondern eine Korrektur. `casefold`
          kann aus einem normalisierten Text einen nicht mehr normalisierten
          machen. Ohne den zweiten Durchgang fielen Namen AUSEINANDER, die
          vorher zusammenfielen (`Ĥ` mit Kombinierer gegen seinen
          Kleinbuchstaben) — die Faltung waere stellenweise FEINER geworden
          statt groeber. Gemessen: zehn solche Zeichenpaare unterhalb U+3000.
          `test_namensfaltung.py` haelt beide Richtungen fest.

        SIE SCHREIBT KEINEN BESTEHENDEN SCHLUESSEL UM — dieser Schluessel wird
        nirgends gespeichert, er entsteht bei jedem Zugriff neu. Gespeichert
        wird `group_id`.

        ABER SIE ENTSCHEIDET JEDEN NEU VERGEBENEN, und der bleibt:
        `group_id_for_name` beim Anlegen (die Kennung landet im gespeicherten
        Album) und `_backfill_group_ids` fuer jedes Album OHNE Kennung. Der
        Backfill haengt allein an der fehlenden Kennung, NICHT an der
        Schemaversion oder an einem alten Backup — sein eigener Docstring
        nennt den Fall „ein Album, das zwischen zwei Starts dazukommt".
        Eine fruehere Fassung dieses Absatzes behauptete „nur beim Rueckspiel
        einer Sicherung von vor v1.7.0"; Blind- und Fremdpruefer haben das
        unabhaengig voneinander widerlegt.

        DIE KEHRSEITE DES GROEBER-WERDENS traegt `_gruppe_fuer_namen`: Zwei
        Schreibweisen in verschiedenen Gruppen wuerden sonst BEIDE
        unauffindbar. Die Abfrage laeuft deshalb zweistufig.

        Gemessen am echten Bestand vor der Aenderung
        (`scripts/faltung-sonde.py`, 26.09.2026, 8 Alben): keine geaenderte
        Antwort, keine neue Mehrdeutigkeit, keine Aufspaltung. Die Sonde
        bleibt im Repo; nach einem Release ist sie ein Aufruf.

        BENANNTE GRENZE: Nullbreiten-Zeichen werden NICHT entfernt. Ein
        `U+200B` im Namen bleibt ein Unterschied. Das waere eine zweite,
        eigenstaendige Entscheidung — sie zieht Namen zusammen, die in Immich
        verschieden heissen.
        """
        # `str()` statt einer Typzusicherung: Ein handbearbeiteter Nicht-String
        # (album_name: 42) liess die Wanderung bis zur zweiten Nacharbeit mit
        # AttributeError abbrechen, und `_load` machte daraus ein
        # "Configuration is invalid" — die App startete GAR NICHT MEHR, wo sie
        # vorher startete und erst beim Lesen der Alben scheiterte. Eine
        # Wanderung darf einen Bestand nicht unstartbar machen; die
        # Typpruefung gehoert ins Modell, nicht hierher.
        if album_name is None:
            return ""
        gefaltet = unicodedata.normalize("NFC", str(album_name)).strip().casefold()
        return unicodedata.normalize("NFC", gefaltet)

    @staticmethod
    def _name_key_vor_83(album_name) -> str:
        """Die Faltung, wie sie bis #83 galt — `strip().lower()`.

        Sie ist NICHT tot. `_name_key` ist seit #83 groeber, und Groeber hat
        eine Kehrseite: Traegt ein Bestand zwei Schreibweisen desselben Namens
        in VERSCHIEDENEN Gruppen, fallen ihre Schluessel jetzt zusammen, und
        die Mehrdeutigkeits-Regel aus #78 antwortet fuer BEIDE mit „keine
        Gruppe" — wo vorher jede ihre eigene fand.

        Und dieser Bestand ist nicht konstruiert: Er ist das ERGEBNIS des
        Fehlers, den #83 behebt. Der Nutzer fand seine Gruppe nicht und legte
        eine zweite an. Genau bei ihm haette die Verbesserung die Lage
        verschlechtert — `group_id_for_name` haette bei jedem Aufruf eine
        frische, dritte Gruppe gepraegt (gemessen von Blind- und Fremdpruefer,
        unabhaengig voneinander).

        Deshalb fragt `_gruppe_fuer_namen` zweistufig: erst die neue Faltung,
        und nur wo sie KEINE eindeutige Antwort liefert, diese hier. Das ist
        nicht nur der mehrdeutige Fall — gemessen (#111): Stufe 2 antwortet
        auch dann, wenn Stufe 1 LEER bleibt, also keinen einzigen Kandidaten
        findet.

        KEINE ALLGEMEINE BESSER-REGEL: Hier stand bis zur zweiten Nacharbeit
        an #98, die Antwort sei „nirgends schlechter als vor #83" — eine
        unbemessene Verallgemeinerung, vom Fremdpruefer widerlegt. Codepunkte
        statt Glyphen, aus demselben Grund wie in `test_namensfaltung.py`: Die
        Haelften sehen gleich aus. Gegenbeispiel (gemessen): `gA` traegt
        `U+1FB7` (kleines Alpha mit Iota subscriptum plus Perispomeni,
        VORKOMPONIERT), `gB` traegt `U+1FBC U+0342` (Grossbuchstabe, PLUS
        Perispomeni als eigenes Zeichen). Eine Anfrage mit `U+1FB3 U+0342`
        (dieselbe Glyphe wie `gA`s Name, aber nur TEILZERLEGT — `U+1FB3`
        selbst ist noch VORKOMPONIERT, nur die Perispomeni haengt als
        eigenes Zeichen daneben; kanonisch aequivalent zu `gA`s Namen,
        gemessen: NFC(`U+1FB3 U+0342`) == `U+1FB7`) antwortet heute mit `gA`
        — mit Stufe 2 allein (also „vor #83") waere die Antwort `gB`
        gewesen. Das ist eine ANDERE Antwort, keine SCHLECHTERE (siehe
        „KEINE ALLGEMEINE BESSER-REGEL" oben) — sie ist hier eher die
        naheliegendere, weil die Anfrage kanonisch mit `gA`s Namen
        uebereinstimmt.
        """
        if album_name is None:
            return ""
        return str(album_name).strip().lower()

    def _gruppe_fuer_namen(self, album_name, albums: Optional[list] = None) -> Optional[str]:
        """Welche Gruppe traegt diesen Namen — in zwei Stufen.

        Stufe 1 ist die heutige Faltung (`_name_key`, unicode-fest). Liefert
        sie genau einen Kandidaten, gilt er.

        Stufe 2 ist die Faltung von vor #83. Sie kommt zum Zug, wenn Stufe 1
        KEINE eindeutige Antwort liefert — gemessen sind zwei verschiedene
        Faelle, kein gemeinsamer Mechanismus:

        * MEHRDEUTIG (mehr als ein Kandidat): zwei Schreibweisen, die Stufe 2
          noch trennte, fallen unter der groeberen Stufe 1 zusammen (Beispiel
          „Strassenfest"/„Straßenfest" in zwei Gruppen — dort loest Stufe 2
          auf). Seit #98 kommt ZUSAETZLICH vor (Haeufigkeit unbemessen,
          #116): ein BYTEGLEICHER Name in zwei Gruppen (absichtlich erlaubt,
          kein Tippfehler) — dort hilft Stufe 2 NICHT: Beide Stufen sehen
          dieselben zwei Kandidaten, die
          Antwort bleibt `None` (gemessen: „Herbstfest" in `gruppe-1` UND
          `gruppe-2`).
        * LEER (kein Kandidat, gemessen #111): Stufe 1 ist fuer bestimmte
          Zeichenkombinationen FEINER als Stufe 2, nicht groeber — die
          griechischen Iota-subscriptum-Paare aus `test_namensfaltung.py`
          (`test_die_richtung_gilt_fuer_zeichen_nicht_fuer_namen`), wo
          `casefold` plus erste Normalform zwei Formen trennt, die `lower()`
          allein zusammenwuerfe.

        Die Begruendung fuer Stufe 2 selbst steht bei `_name_key_vor_83`.

        Beide Stufen halten die zwei Ausnahmen aus #78: ein leerer Name sagt
        nichts, ein mehrdeutiger auch nicht.

        SEIT #113 nur noch eine duenne Huelle um `group_candidates_for_name`:
        Diese Methode kollabiert dessen rohe Kandidatenmenge auf "eindeutig
        oder nichts"; wer die Kandidaten SELBST braucht (Vorschau bei
        Mehrdeutigkeit, `resolve_group_id`), ruft die andere Methode direkt —
        derselbe zweistufige Algorithmus, an EINER Stelle.
        """
        kandidaten = self.group_candidates_for_name(album_name, albums)
        return next(iter(kandidaten)) if len(kandidaten) == 1 else None

    def group_candidates_for_name(
        self, album_name, albums: Optional[list] = None
    ) -> set[str]:
        """Alle Gruppen, die dieser Name treffen koennte — roh, ohne Faltung
        auf "eindeutig oder nichts" (#113).

        `existing_group_for_name`/`_gruppe_fuer_namen` beantworten nur
        "genau eine oder keine" und kollabieren einen mehrdeutigen Namen auf
        `None` — fuer eine Vorschau, die dem Nutzer eine ECHTE Wahl anbietet,
        und fuer eine Ablehnung, die zwischen "kein Treffer" und "mehrdeutig"
        unterscheidet, reicht das nicht. Diese Methode laeuft denselben
        zweistufigen Algorithmus (Begruendung: `_gruppe_fuer_namen`), liefert
        aber bei Nicht-Eindeutigkeit die rohe Kandidatenmenge von Stufe 1 —
        und nur, wenn STUFE 1 LEER ist (kein einziger Kandidat), die von
        Stufe 2 —, statt sie zu verwerfen.

        Leere Menge heisst: der Name trifft keine Gruppe. Genau ein Element
        heisst: eindeutiger Treffer (identisch mit `existing_group_for_name`).
        Mehr als eins heisst: mehrdeutig — GENAU diese Gruppen kommen infrage.

        LOEST STUFE 2 NICHT AUF GENAU EINE GRUPPE AUF (Nacharbeit 1 zu #113,
        Blind W-1/Gegen F4): Dann gilt grundsaetzlich die Kandidatenmenge von
        STUFE 1, nicht die von Stufe 2 — MIT EINER KORREKTUR (Nacharbeit 2,
        Blind/Gegen NA1, „Faltungs-Rueckfall kippt in der Gegenrichtung"):
        Ist Stufe 1 selbst LEER (kein Kandidat), ist eine leere Antwort keine
        Information — dann gilt STATTDESSEN die rohe Kandidatenmenge von
        Stufe 2, und zwar UNVERAENDERT, auch wenn die ihrerseits mehrdeutig
        oder leer ist. Stufe 2 ERSETZT Stufe 1 also nicht erst, wenn sie sich
        auf GENAU EINE Gruppe festlegt (das waere der eindeutige Fall, der
        oben schon im Schleifenkoerper zurueckkehrt) — sondern schon dann,
        wenn Stufe 1 nichts zu bieten hat. Eine MEHRDEUTIGE, nicht-leere
        Stufe-1-Antwort dagegen ist selbst eine Information (genau diese
        Gruppen kommen infrage) und wird durch Stufe 2 NICHT ersetzt, auch
        wenn Stufe 2 anders mehrdeutig waere.
        Gemessen (Blindpruefer, Gegenpruefer, ß-Fall): Ein Bestand mit ZWEI
        Alben, beide BYTEGLEICH "Strassenfest" (verschiedene Gruppen), war
        unter beiden Stufen mehrdeutig — bis auf eine Anfrage mit scharfem S
        ("Straßenfest"): Stufe 1 faltet `ß`->`ss` und sieht weiterhin BEIDE
        Kandidaten (mehrdeutig, NICHT leer); Stufe 2 (`.lower()`, KEIN
        `ß`->`ss`) findet zum Schluessel "straßenfest" nichts in einem
        Bestand, der nur "strassenfest" kennt — LEER. Weil Stufe 1 hier
        NICHT leer ist, gewinnt sie (mehrdeutig, zwei Kandidaten) — dieselbe
        Antwort wie fuer die BYTEGLEICHE Schreibweise; unveraendert seit
        Nacharbeit 1.
        Gemessen (Nacharbeit 2, Iota-subscriptum-Fall): Ein Bestand mit ZWEI
        Alben in unterschiedlicher Unicode-Normalform desselben Namens mit
        Iota subscriptum (`U+1FBC`/`U+0342` in g1/g2), Anfrage mit einer
        WEITEREN Variante (`U+1FB3`/`U+0342`): Stufe 1 findet zu dieser
        exakten Schreibweise gar keinen Schluessel — LEER. Mit der Fassung
        aus Nacharbeit 1 gewann hier die leere Stufe-1-Antwort (`stufe_1 if
        stufe_1 is not None else kandidaten` liefert IMMER Stufe 1, sobald
        die Schleife sie einmal gesetzt hat — und das tut sie immer, ausser
        bei einem eindeutigen Treffer, der schon vorher zurueckkehrt): Die
        Vorschau zeigte `null`, und eine Anlage ohne ausdrueckliche Wahl
        (`expected_no_group`) legte still eine DRITTE Gruppe an — genau die
        stille Zuordnung, die `resolve_group_id` eigentlich verhindern soll
        (`CONTEXT.md`, Docstring dieser Klasse). Jetzt (`stufe_1 if stufe_1
        else kandidaten`) ist die leere Stufe-1-Menge falsy, also gewinnt
        Stufe 2 — die auf beide Alben faltet und mehrdeutig antwortet: Die
        Vorschau zeigt eine echte Wahl statt `null`.
        """
        if albums is None:
            albums = self._data.get("managed_albums", [])
        kandidaten: set[str] = set()
        stufe_1: Optional[set[str]] = None
        for stufe, faltung in enumerate((self._name_key, self._name_key_vor_83)):
            schluessel = faltung(album_name)
            if not schluessel:
                return set()
            kandidaten = self._gruppen_je_name(albums, faltung).get(schluessel, set())
            if len(kandidaten) == 1:
                return kandidaten
            if stufe == 0:
                stufe_1 = kandidaten
        # Stufe 2 hat sich NICHT auf genau eine Gruppe festgelegt: Stufe 1
        # gilt, AUSSER sie ist LEER — dann gilt Stufe 2, auch mehrdeutig
        # oder leer (Nacharbeit 2, siehe Docstring oben).
        return stufe_1 if stufe_1 else kandidaten

    def _backfill_group_ids(self, albums: list[dict]) -> bool:
        """Vergibt fehlende Gruppenkennungen aus der bisherigen Namensregel.

        VERHALTENSERHALTEND, AUSDRUECKLICH AUCH IM FALSCHEN: Zwei Alben, die
        zufaellig gleich heissen und nichts miteinander zu tun haben, bildeten
        bis hierher EINE Gruppe (#78, Fall A). Diese Wanderung uebernimmt das
        unveraendert. Aus den Daten allein ist nicht unterscheidbar, ob eine
        Gruppe gewollt war, und eine bestehende Gruppe still zu zerlegen ist
        der schwerere Fehler: Der Nutzer saehe Alben auseinanderfallen, ohne
        etwas getan zu haben.

        ZWEI AUSNAHMEN, in denen der Name NICHTS ueber Zugehoerigkeit sagt und
        deshalb nicht geraten wird — beide vom Panel gemessen:

        * MEHRDEUTIG: Tragen bereits zwei VERSCHIEDENE Gruppen denselben
          Namen, haengte die erste Fassung ein kennungsloses Album still an
          die in der Datei zuerst stehende. Vertauschte man zwei Zeilen,
          kippte das Ergebnis. Ein Zufall der Dateireihenfolge darf keine
          Zugehoerigkeit stiften.
        * LEER: Ein leerer Name (auch reiner Leerraum) ist keine Aussage. Die
          alte Namensregel verschmolz alle namenlosen Alben; das war
          voruebergehend, weil ein Name es aufloeste. Eine Kennung friert es
          dauerhaft ein.

        In beiden Faellen bekommt das Album eine EIGENE Gruppe. Das ist die
        einzige Abweichung von der Verhaltenserhaltung, und sie geht in die
        sichere Richtung — nicht weil sich das eine rueckgaengig machen
        liesse und das andere nicht (beides kann die App heute nicht), sondern
        weil die Folgen verschieden SICHTBAR sind: Eine falsche Trennung zeigt
        einen Vorschlag zu viel. Eine falsche Verschmelzung UNTERDRUECKT einen
        Vorschlag, und nichts deutet darauf hin, dass er fehlt.

        Zwei Durchgaenge, damit bereits vergebene Kennungen gewinnen. Sonst
        bekaeme ein Album, das zwischen zwei Starts dazukommt, eine neue
        Kennung und risse die Gruppe des ersten Starts entzwei.
        """
        bekannt = self._gruppen_je_name(albums)

        # Kennungslose Alben gleichen Namens bilden untereinander eine Gruppe —
        # das ist der Normalfall beim ersten Start, wo noch KEINE Kennung
        # existiert und die alte Namensgruppierung uebernommen werden muss.
        frisch: dict[str, str] = {}

        changed = False
        for album in albums:
            if album.get("group_id"):
                continue
            schluessel = self._name_key(album.get("album_name", ""))
            # ZWEISTUFIG wie die Abfrage, und hier zaehlt es doppelt: Diese
            # Zeile SCHREIBT eine Kennung, die dauerhaft bleibt. Ohne die
            # zweite Stufe bekaeme ein kennungsloses Album neben zwei
            # Schreibweisen in zwei Gruppen eine frische dritte — gemessen
            # von Blind- und Fremdpruefer.
            treffer = self._gruppe_fuer_namen(album.get("album_name", ""), albums)
            if not schluessel:
                album["group_id"] = str(uuid.uuid4())
            elif treffer:
                album["group_id"] = treffer
            elif bekannt.get(schluessel):
                # Mehrdeutig auf BEIDEN Stufen: Der Name sagt nichts.
                album["group_id"] = str(uuid.uuid4())
            else:
                album["group_id"] = frisch.setdefault(schluessel, str(uuid.uuid4()))
            changed = True
        return changed

    def _gruppen_je_name(self, albums: list[dict], faltung=None) -> dict[str, set[str]]:
        """Normalisierter Name -> alle Gruppenkennungen, die ihn tragen.

        Mehr als eine bedeutet: Der Name ist mehrdeutig geworden.

        `faltung` ist die Rueckfall-Stufe aus `_gruppe_fuer_namen` — ohne
        Angabe die heutige. Ein Parameter statt zweier Methoden, damit die
        Mehrdeutigkeits-Regel genau einmal im Code steht.
        """
        if faltung is None:
            faltung = self._name_key
        karte: dict[str, set[str]] = {}
        for album in albums:
            if album.get("group_id"):
                karte.setdefault(faltung(album.get("album_name", "")),
                                 set()).add(album["group_id"])
        return karte

    def existing_group_for_name(self, album_name: str) -> Optional[str]:
        """Kennung der Gruppe mit diesem Namen — None, wenn keine oder mehrere.

        Die ABFRAGE, getrennt von der VERGABE (#81). `group_id_for_name` gibt
        bei Nicht-Treffer eine frische Kennung zurueck; fuer eine Vorschau
        taugt das nicht, die braucht "trifft / trifft nicht".

        Die beiden Ausnahmen aus #78 gelten unveraendert: Ein leerer und ein
        mehrdeutiger Name sagen nichts ueber Zugehoerigkeit, also wird nicht
        geraten.

        DIE NORMALISIERUNG IST SEIT #83 UNICODE-FEST. Hier stand bis dahin
        als benannte Grenze, sie sei `strip().lower()` und zwei sichtbar
        gleiche Namen koennten deshalb als verschieden gelten — „Café" in NFC
        gegen NFD, „Strassenfest" gegen „Straßenfest". Seit #81 war das eine
        ZUSAGE AN DEN NUTZER, und sie war falsch. Behoben in `_name_key`;
        gemessen wurde vorher am echten Bestand, dass die Umstellung dort
        folgenlos ist (`scripts/faltung-sonde.py`).

        Die Abfrage laeuft seitdem ZWEISTUFIG (`_gruppe_fuer_namen`): neue
        Faltung, und wo sie KEINE eindeutige Antwort liefert — mehrdeutig ODER
        leer (gemessen #111) —, die alte. Ohne die zweite Stufe haette die
        Verbesserung genau denen geschadet, fuer die sie gebaut ist — wer zwei
        Schreibweisen in zwei Gruppen hat, verlor beide Antworten.
        """
        return self._gruppe_fuer_namen(album_name)

    def group_details(self, group_id: str) -> dict:
        """Wem tritt man bei — die Personen und Albumnamen einer Gruppe.

        Ohne das waere die Bestaetigung beim Anlegen eine leere Geste: Der
        Nutzer soll sehen, WEM er beitritt, nicht nur DASS er beitritt.

        Die Personen werden ueber Konto UND Person entdoppelt; zwei
        Immich-Instanzen koennen dieselbe Personen-Kennung vergeben.

        `owner_account_missing`/`too_few_people` (#124 B9): dieselben zwei
        Markierungen wie auf `ManagedAlbumOut` (#99, #112), hier auf
        GRUPPENEBENE aggregiert, weil eine Gruppe mehrere Alben mit
        verschiedenen Besitzern buendeln kann. `owner_account_missing` ist
        wahr, sobald IRGENDEIN Album der Gruppe verwaist ist — wer beitritt,
        soll das VORHER sehen, nicht erst nach dem Beitritt am einzelnen
        Album.

        `too_few_people` (Nacharbeit 1 zu #113/#119/#124, Gegen F3): zaehlte
        hier vorher die ENTDOPPELTE Personenmenge ueber alle Alben der Gruppe
        — der Owner-Entscheid zu #112/#123 sagt aber etwas anderes: markiert
        ist eine Gruppe, wenn EIN Album zu wenige Personen hat, also ODER
        JE ALBUM (genau wie `GET /api/sync/albums`/`ManagedAlbumOut.
        too_few_people`, die `len(album.person_refs) < 2` je Album prueft).
        Gemessen am Unterschied: Zwei Alben mit je EINER Person — 1+1, macht
        entdoppelt schon wieder 2 — galten hier vorher als NICHT zu wenig,
        obwohl JEDES einzelne Album fuer sich unvollstaendig ist — die
        Albumliste daneben markierte dieselbe Gruppe trotzdem als "zu wenige
        Personen". Jetzt rechnen beide Stellen dieselbe Eigenschaft.
        """
        alben = [a for a in self._data.get("managed_albums", [])
                 if a.get("group_id") == group_id]
        gesehen: set[str] = set()
        refs: list[dict] = []
        for album in alben:
            for ref in album.get("person_refs", []):
                schluessel = f"{ref.get('account_id')}::{ref.get('person_id')}"
                if schluessel not in gesehen:
                    gesehen.add(schluessel)
                    refs.append(ref)
        lebende_konten = {a.id for a in self.list_accounts()}
        return {
            "group_id": group_id,
            "album_names": sorted({a.get("album_name", "") for a in alben}),
            "person_refs": refs,
            "owner_account_missing": any(
                a.get("owner_account_id") not in lebende_konten for a in alben
            ),
            "too_few_people": any(
                len(a.get("person_refs", [])) < 2 for a in alben
            ),
        }

    def resolve_group_id(self, album_name: str, *,
                         chosen: Optional[str] = None,
                         force_new: bool = False,
                         expected_none: bool = False) -> str:
        """Welche Gruppe es WIRKLICH wird — einziger Eigentuemer der Regel.

        Ohne Angabe bleibt es beim heutigen Verhalten (der Name entscheidet) —
        MIT EINER Ausnahme seit #113: Ein mehrdeutiger Name (mehr als eine
        Gruppe traegt ihn) wird IMMER abgelehnt, wenn keine ausdrueckliche
        Wahl vorliegt. Vorher oeffnete `group_id_for_name` hier still eine
        DRITTE Gruppe — `existing_group_for_name` sieht "mehrdeutig" und
        "unbekannt" gleich (`None`) und kann das nicht unterscheiden; diese
        Methode fragt `group_candidates_for_name` direkt und sieht den
        Unterschied.

        Eine ausdrueckliche Wahl schlaegt den Namen; eine unbekannte Kennung
        wird ABGELEHNT, statt eine Gruppe zu erfinden — sonst legt ein
        Tippfehler eine Geistergruppe an, zu der nie ein zweites Album findet,
        und niemand sieht es, weil das Anlegen gelingt.

        `expected_none` (#119): Der Aufrufer bestaetigt hiermit, dass SEINE
        Vorschau zu diesem Namen "keine Gruppe" zeigte. Trifft der Name jetzt
        doch eine Gruppe — sei es, weil zwischen Vorschau und Klick eine
        andere Anfrage genau diesen Namen angelegt hat —, wird abgelehnt statt
        still beizutreten; die Oberflaeche laedt die Vorschau danach neu.
        Ohne dieses Flag (Vorgabe: aus, das heutige Verhalten fuer Aufrufer,
        die es nicht mitschicken — auch die rohe API) bleibt der stille
        Beitritt bestehen: Das ist genau der Fall, den #86 will (zwei
        GLEICHZEITIGE Anlagen desselben NEUEN Namens sollen in EINER Gruppe
        landen, nicht mit einer Ablehnung enden).
        """
        import errors

        # `is not None`, nicht Wahrheitswert: Eine ausdrueckliche leere
        # Kennung ist eine ANGABE, keine Auslassung. Mit dem Wahrheitswert
        # galt `group_id=""` als "nicht gesetzt" — der Widerspruch mit
        # force_new_group wurde nicht erkannt, und die Namensregel griff
        # still (Zweitstimme 21.09.2026, gemessen).
        angegeben = chosen is not None
        if angegeben and force_new:
            raise errors.group_choice_conflict()
        if force_new:
            return str(uuid.uuid4())
        if angegeben:
            bekannt = {a.get("group_id") for a in self._data.get("managed_albums", [])}
            if chosen not in bekannt:
                raise errors.group_not_found(chosen)
            return chosen

        kandidaten = self.group_candidates_for_name(album_name)
        if len(kandidaten) > 1:
            raise errors.group_choice_required(album_name)
        if len(kandidaten) == 1:
            [treffer] = kandidaten
            if expected_none:
                raise errors.group_situation_changed(album_name)
            return treffer
        return str(uuid.uuid4())

    def gruppen_schloss(self, album_name: str) -> asyncio.Lock:
        """Das Schloss fuer diesen Albumnamen.

        Der Aufrufer haelt es ueber die GANZE Strecke von der Aufloesung bis
        zum Speichern — sonst schuetzt es die Luecke nicht, um die es geht.
        Gesperrt wird nur gegen Anlagen mit DEMSELBEN Namen; alles andere
        laeuft weiter.

        GRENZE, gemessen (#108): Der Schluessel hier ist NUR Stufe 1 der
        Namensfaltung (`_name_key`); die Gruppenzuordnung (`_gruppe_fuer_namen`)
        greift zusaetzlich auf Stufe 2 zurueck. Es gibt Namen, die NUR in
        Stufe 2 kollidieren (`test_namensfaltung.py`,
        `test_im_kleinen_raum_sind_es_genau_drei_paare`) — sie begegnen sich
        in der Zuordnung, nehmen hier aber VERSCHIEDENE Schloesser. Ob das
        geschlossen wird, gehoert zu #95.
        """
        schluessel = (id(asyncio.get_running_loop()), self._name_key(album_name))
        return _gruppen_schloesser.setdefault(schluessel, asyncio.Lock())

    def treffer_schloss(self, match_id: str) -> asyncio.Lock:
        """Das Schloss fuer diesen Treffer.

        Der Aufrufer haelt es von der Pruefung "gibt es schon eins?" bis zum
        Speichern — sonst schuetzt es die Luecke nicht, um die es geht. Nur
        Anlagen fuer DENSELBEN Treffer warten aufeinander.

        Ohne Faltung: `match_id` ist eine Kennung, kein Anzeigetext. Sie
        kommt aus dem Treffer oder wird aus dem kanonischen Namen gebildet;
        beide Male ist sie schon normalisiert. Eine zweite Normalisierung
        hier wuerde zwei Kennungen zusammenziehen, die der Rest des Codes
        auseinanderhaelt.
        """
        schluessel = (id(asyncio.get_running_loop()), match_id)
        return _treffer_schloesser.setdefault(schluessel, asyncio.Lock())

    def group_id_for_name(self, album_name: str) -> str:
        """Kennung der Gruppe mit diesem Namen — sonst eine neue.

        Damit bleibt "Gruppieren durch gleiches Benennen" als Bedienmuster
        erhalten: Wer ein zweites Album genauso nennt, tritt der bestehenden
        Gruppe bei, wie bisher. Der Unterschied ist, dass die Zugehoerigkeit
        ab dem Anlegen festliegt und ein spaeteres Umbenennen sie nicht mehr
        aufloest.

        Dieselben zwei Ausnahmen wie in `_backfill_group_ids`: Bei einem
        mehrdeutigen oder leeren Namen wird nicht geraten, sondern eine eigene
        Gruppe geoeffnet.

        STAND #113: `resolve_group_id` — der eigentliche Eigentuemer der
        "welche Gruppe wird es wirklich"-Regel — ruft diese Methode NICHT
        mehr auf. Ihr "mehrdeutig -> stille neue Gruppe" ist seit #113 fuer
        Anlage/Verknuepfung FALSCH (dort lehnt `resolve_group_id` mehrdeutige
        Namen ohne ausdrueckliche Wahl ab, statt zu raten); `resolve_group_id`
        baut ihre eigene, kuerzere Fassung direkt auf
        `group_candidates_for_name`. Diese Methode bleibt als eigenstaendiges,
        oeffentliches "nur der Name entscheidet, notfalls neu"-Werkzeug
        bestehen (getestet in `test_config_store.py`), hat aber aktuell
        keinen Aufrufer in `routers/`.
        """
        treffer = self.existing_group_for_name(album_name)
        return treffer if treffer else str(uuid.uuid4())

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self._path.parent, 0o700)
        except OSError:
            logger.warning("Could not enforce 0700 on %s", self._path.parent)
        payload = json.dumps(self._data, indent=2, ensure_ascii=False)
        fd, temp_name = tempfile.mkstemp(prefix=_temp_praefix(self._path.name), dir=self._path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_name, 0o600)
            if self._path.exists():
                shutil.copy2(self._path, f"{self._path}.bak")
                os.chmod(f"{self._path}.bak", 0o600)
            os.replace(temp_name, self._path)
            os.chmod(self._path, 0o600)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    def list_accounts(self) -> list[Account]:
        return [Account(**v) for v in self._data["accounts"].values()]

    def get_account(self, account_id: str) -> Optional[Account]:
        raw = self._data["accounts"].get(account_id)
        return Account(**raw) if raw else None

    def add_account(self, data: AccountCreate, user_id: Optional[str] = None) -> Account:
        account = Account.from_create(data)
        account.user_id = user_id
        self._data["accounts"][account.id] = account.model_dump()
        self._save()
        return account

    def update_account(self, account_id: str, updates: dict) -> Optional[Account]:
        raw = self._data["accounts"].get(account_id)
        if not raw:
            return None
        raw.update({k: v for k, v in updates.items() if v is not None})
        self._save()
        return Account(**raw)

    async def delete_account(self, account_id: str) -> bool:
        """Entfernt ein Konto und seine Personen-Referenzen — sonst NICHTS.

        SEIT #117 SCHLOSSPFLICHTIG, SEIT NACHARBEIT 1 (#117/#121/#103) OHNE
        EIGENES WARTEN: `delete_account` schrieb urspruenglich OHNE jedes
        Albumschloss in `managed_albums`, direkt auf `self._data`. Die drei
        Schreiber eines Albums (Refresh/Umbenennen/Erweitern) lesen ihren
        Datensatz dagegen UNTER `sync_service._album_schloss` frisch
        (`_frisch`), warten auf Immich und schreiben am Ende den GANZEN
        Datensatz zurueck. Lief `delete_account` in diesem Wartefenster,
        gewann der spaeter fertige Schreiber mit seiner ALTEN Kopie und nahm
        die Loeschung wieder zurueck — gemessen (Panel zu #101, erzwungenes
        Fenster): `konto-3` stand nach `delete_account("konto-3")` parallel
        zu einer Erweiterung wieder in `person_refs`.

        Die ERSTE Fassung dieser Methode (nach #117) nahm dafuer je
        betroffenem Album SEQUENZIELL dessen `_album_schloss` — und wartete
        damit, in Summe, auf jedes gehaltene Schloss NACHEINANDER: Ein Aufruf
        hinter einem laufenden Sammelabgleich ueber vier Alben brauchte die
        SUMME aller vier Wartezeiten, bevor er ueberhaupt antwortete —
        gemessen 1,29 s bei vier mal 0,3 s Einzelwartezeit — und nach aussen
        war das Konto in dieser ganzen Zeit schon verschwunden (`GET
        /api/accounts` ohne das Konto), aber die Anfrage stand noch offen
        (Nacharbeit 1, Befund der Pruefstimmen, "Konvoi").

        DIE NEUE REGEL, SEIT NACHARBEIT 1 — dieselbe Regel, die JEDER
        Schreiber jetzt befolgt (`ConfigStore._ohne_tote_konten`, unter
        `add_managed_album`/`update_managed_album`): `delete_account` WARTET
        AUF KEIN ALBUMSCHLOSS. Es nimmt ein Schloss nur, wenn es SOFORT frei
        ist (`asyncio.Lock.locked()` unmittelbar vor `async with`, ohne
        dazwischenliegenden `await` — kein Zeitfenster, in dem das Schloss
        zwischen Pruefung und Zugriff von jemand anderem genommen werden
        koennte). Ist es das nicht, ueberspringt `delete_account` dieses
        Album einfach: Der Halter des Schlosses bereinigt die tote Referenz
        selbst, wenn ER seinen Datensatz zurueckschreibt — genau das leistet
        `_ohne_tote_konten` an JEDER Schreibstelle, nicht nur hier. Die
        Kontoloeschung selbst bleibt dadurch so schnell, wie es die Alben mit
        FREIEM Schloss erlauben, unabhaengig davon, wie viele Alben gerade von
        einer laufenden Operation gehalten werden (belegt:
        `test_konto_loeschung_ohne_konvoi.py`).

        HEILWEG, EBENFALLS NEU: Dieser Durchlauf raeumt nicht nur Referenzen
        auf DAS gerade geloeschte Konto, sondern auf JEDES Konto, das es
        nicht mehr gibt — unabhaengig davon, seit wann. Ein Album, dessen
        Bereinigung durch einen fruehreren Abbruch (Ausnahme, Prozessende)
        auf halbem Weg stehen blieb, wird beim NAECHSTEN Aufruf dieser
        Methode mitgeheilt, auch wenn `account_id` diesmal ein ANDERES Konto
        meint — oder eines, das es laengst nicht mehr gibt (siehe die
        Ergebnis-Zusicherung unten).

        Das Konto selbst (die `accounts`-Zeile) wird VOR der Album-Schleife
        entfernt und sofort gespeichert: Diese Zeile haengt an keinem
        Albumschloss, und je frueher sie verschwindet, desto frueher sehen
        die Besitzerpruefungen der drei Schreiber (#117 Nachtrag,
        `sync_service.rename_managed_album` u. a.), die den Besitzer JETZT
        ebenfalls frisch aus dem Store lesen, ein geloeschtes Konto als
        geloescht.

        Owner-Entscheid 28.09.2026 (#99, #112): Nichts verschwindet still.
        Diese Methode raeumte frueher weit mehr auf, als das Konto selbst
        betraf — jedes Album mit weniger als zwei verbliebenen Personen fiel
        still weg, `dismissed_match_ids` und `synced_name_match_ids` wurden
        GANZ geleert, und ein Protokolleintrag verschwand schon, wenn der
        Kontoname als Teilwort in seinem `details`-Text vorkam (gemessen am
        echten Store, #112: „Name 'Carlas Mama' abgeglichen" verschwand beim
        Loeschen von „Carla").

        Jetzt bleibt bestehen, was nicht am Konto selbst haengt:

        - Jedes Album, unabhaengig davon, wie viele Personen danach noch
          darin stehen (auch null). Ein Album ohne lebenden Besitzer gilt als
          verwaist — berechnet beim Lesen (`routers/albums.py`), nicht hier
          gespeichert (keine Schema-Aenderung dieser Datei).
        - `owner_account_id` bleibt UNVERAENDERT, auch wenn es auf das
          geloeschte Konto zeigt (Owner: markieren, nicht umschreiben — genau
          das erzeugt den verwaisten Zustand).
        - `dismissed_match_ids` und `synced_name_match_ids` bleiben
          vollstaendig: Eine Match-Kennung ist `md5(sortierte Personen-IDs)`
          (`face_matcher._match_id`, `pair_match_id`) und traegt kein Konto.
          Fuer Personen, die in einem Album stehen, LIEGEN die Personen-IDs
          hier durchaus vor (`person_refs`, bevor sie oben entfernt werden);
          ein gezieltes Entfernen waere fuer DIESE Paare technisch moeglich.
          Vollstaendig fehlen sie nur fuer Personen des Kontos, die nie in
          einem Album auftauchten. Behalten ist trotzdem die richtige Wahl,
          unabhaengig davon (Owner-Entscheid #112, technisch begruendet vom
          Agenten): Wird das Konto neu angelegt, tragen seine Immich-Personen
          dieselben IDs; eine alte Ablehnung gilt dann unveraendert weiter
          (`CONTEXT.md`, „Dismissed Match"). Ein gezieltes Raeumen wuerde das
          zerstoeren, ohne einen Nutzen, den „einfach behalten" nicht schon
          haette.
        - `sync_log` bleibt vollstaendig, auch Eintraege, deren `details`
          den Kontonamen erwaehnen oder deren `undo_data.account_id` auf das
          geloeschte Konto zeigt. Ein Rueckgaengig-Versuch auf einen solchen
          Eintrag lehnt der Server bereits ab (`errors.account_gone`); die
          Oberflaeche sperrt den Knopf zusaetzlich vorab.

        Einzig die `person_refs` toter Konten verschwinden aus jedem Album
        (nicht nur die des HIER geloeschten — siehe „Heilweg" oben), und
        `linked_match_ids` wird danach neu berechnet — beide haengen direkt
        am Konto, nicht am Datenbestand insgesamt. Seit #117 passiert das je
        Album UNTER dessen `_album_schloss`, auf einem dort frisch gelesenen
        Datensatz — seit Nacharbeit 1 nur noch fuer Alben, deren Schloss in
        diesem Moment FREI ist (siehe oben). Ein Album, dessen Schloss GERADE
        gehalten wird, raeumt seit Nacharbeit 2 der HALTER SELBST, bei JEDEM
        Ausgang seiner eigenen Operation (`sync_service.
        _raeume_tote_referenzen_synchron`, aufgerufen aus einem `finally`
        unter demselben Schloss — nicht nur beim Erfolg, siehe dort); bleibt
        ein Prozess davor stehen (Absturz), heilt spaetestens der naechste
        Start (`_migrate`, oben in dieser Datei).

        RUECKGABEWERT, SEIT NACHARBEIT 2 EIN ZWEITES MAL PRAEZISIERT: `True`,
        wenn diese Anfrage etwas bewirkt hat — entweder gab es das Konto noch
        (die Kontenzeile verschwindet) ODER GENAU DIESE Kennung hatte
        irgendwo im Bestand noch eine EIGENE Referenz, unabhaengig davon, ob
        sie in diesem Aufruf tatsaechlich geraeumt werden konnte (siehe
        „EIGENE Reste, nicht irgendwelche" unten). `False` nur, wenn WEDER
        das Konto existierte NOCH DIESE Kennung irgendwo eine eigene
        Referenz hatte — der Normalfall fuer eine erfundene Kennung. Ein
        zweites `DELETE` auf ein bereits geloeschtes Konto mit liegen
        gebliebenen EIGENEN Resten (etwa nach einer Ausnahme zwischen zwei
        Alben, siehe `test_konto_loeschung_ohne_konvoi.py::
        test_abbruch_zwischen_zwei_alben_heilt_beim_naechsten_versuch`) heilt
        die Reste und antwortet 204, nicht 404 — der Router
        (`routers/accounts.py::delete_account`) meldet `account_not_found`
        nur noch fuer den echten Nichttreffer: eine Kennung, die WEDER im
        Kontenbestand noch als Referenz irgendwo auftaucht. Ein Client, der
        sein eigenes `DELETE` wiederholt (Zeitueberschreitung, doppelter
        Klick), laeuft damit nicht in einen Fehler, der keiner ist — DELETE
        bleibt idempotent, wie die Projekt-Praemisse „nichts verschwindet
        still" es fuer eine aufraeumende Operation verlangt.

        EIGENE RESTE, NICHT IRGENDWELCHE (Nacharbeit 2, Blind W1/Gegen N4):
        Die vorherige Fassung meldete 204 fuer JEDE Kennung, sobald DER
        HEILWEG IRGENDWO im Bestand irgendeine tote Referenz raeumte — auch
        wenn diese Referenz zu einem GANZ ANDEREN, laengst geloeschten Konto
        gehoerte. `DELETE /api/accounts/<erfundene-kennung>` antwortete damit
        204 und leerte `thumbnail_cache`/`client_pool` fuer eine Kennung, die
        nie existiert hat, sobald irgendwo im Bestand ein Rest eines FRUEHER
        geloeschten Kontos lag (gemessen: Gegen N4). Geraeumt werden weiterhin
        ALLE toten Referenzen, unabhaengig davon, zu welchem Konto sie
        gehoeren — das leistet die Schleife unten unveraendert. Nur der
        RUECKGABEWERT haengt jetzt EIN AN DIESER Kennung: `eigene_reste`
        zaehlt Referenzen auf `account_id` selbst, VOR der Heilschleife und
        UNABHAENGIG vom Schlosszustand jedes Albums — auch in einem gerade
        gesperrten Album zaehlt eine eigene Referenz noch mit (K1: ein
        zweites `DELETE`, waehrend das Album mit dieser Referenz gesperrt
        ist, bleibt 204, nicht 404 — der Halter des Schlosses raeumt sie
        selbst, siehe `sync_service._raeume_tote_referenzen_synchron`).
        """
        # Lokaler Import: `sync_service` importiert `config_store` bereits
        # auf Modulebene (fuer `ConfigStore`) — ein Import auf Modulebene
        # HIER waere ein Kreislauf. Siehe die Begruendung beim Schlossregister
        # oben.
        from services import sync_service

        existierte = account_id in self._data["accounts"]
        if existierte:
            del self._data["accounts"][account_id]
            self._save()

        # VOR der Heilschleife und UNABHAENGIG vom Schlosszustand gemessen —
        # siehe „EIGENE RESTE, NICHT IRGENDWELCHE" oben. Eine Referenz in
        # einem gerade GESPERRTEN Album zaehlt hier trotzdem mit: Sie wird in
        # DIESEM Aufruf nicht geraeumt (die Schleife unten ueberspringt
        # gesperrte Alben weiterhin), aber sie war real und wird spaetestens
        # vom Halter des Schlosses selbst entfernt.
        eigene_reste = any(
            ref.get("account_id") == account_id
            for a in self._data.get("managed_albums", [])
            for ref in a.get("person_refs", [])
        )

        # Linked identities lose dead account profiles as well. Keep this
        # synchronous so album writers cannot observe partially pruned links.
        linked_people = self._data.get("linked_people", [])
        eigene_reste = eigene_reste or any(
            ref.get("account_id") == account_id
            for link in linked_people
            for ref in link.get("person_refs", [])
        )
        retained_links = []
        for link in linked_people:
            retained_refs = self._ohne_tote_konten(link.get("person_refs", []))
            if len({ref.get("account_id") for ref in retained_refs}) >= 2:
                retained_links.append({**link, "person_refs": retained_refs})
        if retained_links != linked_people:
            self._data["linked_people"] = retained_links
            self._save()

        lebende_konten = set(self._data["accounts"].keys())
        betroffene_alben = [
            a["id"] for a in self._data.get("managed_albums", [])
            if any(ref.get("account_id") not in lebende_konten
                   for ref in a.get("person_refs", []))
        ]
        for album_id in betroffene_alben:
            schloss = sync_service._album_schloss(album_id)
            # NICHT WARTEN (Nacharbeit 1, "Konvoi"): Ein anderer Schreiber
            # haelt dieses Schloss gerade. Er bereinigt tote Referenzen beim
            # eigenen Zurueckschreiben selbst (`_ohne_tote_konten`, ueber
            # `update_managed_album`) — `delete_account` muesste hier nur
            # warten, um danach dieselbe Arbeit ein zweites Mal zu tun.
            #
            # `schloss.locked()` ALLEIN REICHT NICHT (Nacharbeit 2, WICHTIG
            # 2, Gegen N2/N3): `asyncio.Lock` ist FAIR — gibt ein Halter das
            # Schloss frei, waehrend schon ein anderer Aufrufer in der
            # Warteschlange steht (`schloss._waiters`), wird DIESER Wartende
            # zuerst geweckt, nicht ein neuer Versuch von aussen.
            # `locked()` meldet in genau diesem Zwischenzustand `False` —
            # das Schloss ist "frei", aber ein `async with schloss:` HIER
            # wuerde sich HINTER den bereits geweckten Wartenden einreihen
            # und dessen GANZE Operation abwarten (gemessen: `delete_account`
            # brauchte dann so lange wie der wartende Schreiber, nicht
            # praktisch null). Deshalb zaehlt ein vorhandener Wartender
            # genauso als "belegt" wie `locked()` — auch er wird sein Album
            # am Ende seiner Operation selbst bereinigen
            # (`sync_service._raeume_tote_referenzen_synchron`). Kein `await`
            # zwischen dieser Pruefung und dem `async with` unten: Die
            # Pruefung ist deshalb verbindlich, nicht nur eine Momentaufnahme.
            if schloss.locked() or schloss._waiters:
                continue
            async with schloss:
                frisches = self.get_managed_album(album_id)
                if frisches is None:
                    # GEMESSEN UNERREICHT MIT DEM HEUTIGEN AUFRUFGRAPHEN
                    # (Nacharbeit 1, ehrlich benannt statt verschwiegen — die
                    # Mutation `if False:` an dieser Stelle ueberlebte die
                    # volle Suite): Diese Zeile schuetzte VOR Nacharbeit 1 vor
                    # einer echten Race — `delete_account` WARTETE damals
                    # selbst am Schloss, und ein gleichzeitiges
                    # `DELETE /api/sync/albums/{id}` (dasselbe Schloss) konnte
                    # das Album entfernen, WAEHREND diese Methode noch
                    # wartete. Seit Nacharbeit 1 WARTET `delete_account` auf
                    # kein gehaltenes Schloss mehr (siehe oben) — ist es
                    # gehalten, wird das Album uebersprungen, BEVOR dieser
                    # Zweig ueberhaupt erreicht wird; ist es frei, laeuft der
                    # gesamte Rumpf dieser Schleifenrunde OHNE ein einziges
                    # `await` (`get_managed_album`/`update_managed_album` sind
                    # synchron), also OHNE eine Stelle, an der ein
                    # `DELETE /api/sync/albums/{id}` dazwischenkommen koennte.
                    # Die Pruefung bleibt trotzdem stehen: Sie ist billig,
                    # und ein kuenftiger Umbau des Schlossmodells (etwa ein
                    # `await` zwischen Lesen und Schreiben) wuerde die
                    # Race sonst STILL wieder oeffnen, mit einem
                    # `AttributeError` statt eines klaren "nichts zu tun" als
                    # Folge.
                    continue
                # KEIN EIGENES FILTERN MEHR HIER (Nacharbeit 2, M19): Eine
                # fruehere Fassung filterte tote Konten hier EXPLIZIT, aus
                # reiner Lesbarkeit — `update_managed_album` filtert
                # (`_ohne_tote_konten`) ohnehin noch einmal, bevor es speichert.
                # Genau diese Doppelung machte die Zeile hier UNBEWEISBAR: Eine
                # Mutation, die den Vergleich auf `!= account_id` verengt
                # (filtert dann nur noch DAS gerade geloeschte Konto, nicht
                # jedes tote), ueberlebte die volle Suite unbemerkt — die
                # Zeile sah wie ein Schutz aus, ohne einer zu sein
                # (`docs/agents/lehren.md` §1, „gruen ohne bewiesen"). Die
                # tatsaechliche Garantie kommt ausschliesslich aus
                # `update_managed_album`; `frisches.person_refs` geht
                # deshalb UNVERAENDERT dorthin — sein eigener Filter deckt
                # jedes tote Konto, nicht nur `account_id`.
                self.update_managed_album(frisches)
        return existierte or eigene_reste

    # ------------------------------------------------------------------
    # Linked people
    # ------------------------------------------------------------------

    def get_linked_people(self) -> list[LinkedPerson]:
        return [LinkedPerson(**item) for item in self._data.get("linked_people", [])]

    def get_linked_person(self, linked_person_id: str) -> Optional[LinkedPerson]:
        return next((item for item in self.get_linked_people() if item.id == linked_person_id), None)

    def linked_person_conflicts(
        self,
        person_refs: list[MultiSyncPersonEntry | dict],
    ) -> bool:
        """Return whether refs would merge incompatible linked identities."""
        keys = {
            (
                raw.account_id if hasattr(raw, "account_id") else raw["account_id"],
                raw.person_id if hasattr(raw, "person_id") else raw["person_id"],
            )
            for raw in person_refs
        }
        overlapping = [
            link for link in self.get_linked_people()
            if keys & {(ref.account_id, ref.person_id) for ref in link.person_refs}
        ]
        if len(overlapping) > 1:
            return True
        if not overlapping:
            return False
        by_account = {
            ref.account_id: ref.person_id for ref in overlapping[0].person_refs
        }
        return any(
            account_id in by_account and by_account[account_id] != person_id
            for account_id, person_id in keys
        )

    def ensure_linked_person(
        self,
        display_name: str,
        person_refs: list[MultiSyncPersonEntry | dict],
    ) -> LinkedPerson:
        """Create, reuse, or compatibly extend a cross-account identity."""
        if self.linked_person_conflicts(person_refs):
            raise ValueError("profiles belong to incompatible linked people")

        normalized: list[PersonRef] = []
        for raw in person_refs:
            payload = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
            account = self.get_account(payload["account_id"])
            normalized.append(PersonRef(
                account_id=payload["account_id"],
                person_id=payload["person_id"],
                person_name=payload.get("person_name") or display_name,
                account_name=payload.get("account_name") or (account.name if account else ""),
                account_color=payload.get("account_color") or (account.color if account else "#6366f1"),
            ))
        keys = {(ref.account_id, ref.person_id) for ref in normalized}
        links = self.get_linked_people()
        overlapping = [
            link for link in links
            if keys & {(ref.account_id, ref.person_id) for ref in link.person_refs}
        ]

        if overlapping:
            link = overlapping[0]
            merged = list(link.person_refs)
            existing_keys = {(ref.account_id, ref.person_id) for ref in merged}
            changed = False
            normalized_name = display_name.strip()
            if normalized_name and normalized_name != link.display_name:
                link.display_name = normalized_name
                changed = True
            for ref in normalized:
                if (ref.account_id, ref.person_id) not in existing_keys:
                    merged.append(ref)
                    existing_keys.add((ref.account_id, ref.person_id))
                    changed = True
            if changed:
                link.person_refs = merged
                self.update_linked_person(link)
            return link

        if len({ref.account_id for ref in normalized}) < 2:
            raise ValueError("linked people require profiles from at least two accounts")
        if len({ref.account_id for ref in normalized}) != len(normalized):
            raise ValueError("linked people allow one profile per account")
        linked = LinkedPerson(
            id=str(uuid.uuid4()),
            display_name=display_name,
            person_refs=normalized,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._data.setdefault("linked_people", []).append(linked.model_dump())
        self._save()
        return linked

    def update_linked_person(self, linked: LinkedPerson) -> None:
        items = self._data.setdefault("linked_people", [])
        for index, item in enumerate(items):
            if item.get("id") == linked.id:
                items[index] = linked.model_dump()
                self._save()
                return

    def delete_linked_person(self, linked_person_id: str) -> bool:
        items = self._data.get("linked_people", [])
        retained = [item for item in items if item.get("id") != linked_person_id]
        if len(retained) == len(items):
            return False
        self._data["linked_people"] = retained
        self._save()
        return True

    # ------------------------------------------------------------------
    # Dismissed matches
    # ------------------------------------------------------------------

    def get_dismissed_ids(self) -> set[str]:
        return set(self._data.get("dismissed_match_ids", []))

    def dismiss_match(self, match_id: str) -> None:
        """Merkt eine abgelehnte Paarung — OHNE zu pruefen, ob es sie gibt.

        Das ist Absicht (Owner-Entscheid 21.09.2026, Issue #88), und der
        Grund liegt in der Natur der Sache: Eine Ablehnung ist eine Aussage
        ueber ZWEI PERSONEN, nicht ueber einen Vorschlag, der gerade auf dem
        Bildschirm steht. Vorschlaege werden aus den Gesichtsdaten gerechnet
        und nicht gespeichert; sie koennen verschwinden (Gesicht geloescht,
        Schwelle geaendert) und spaeter wiederkommen. Eine strenge Pruefung
        wuerde dann eine Ablehnung verweigern, die der Nutzer bewusst setzt.

        Der Preis ist benannt: Eine Kennung, die zu keinem Vorschlag gehoert
        — Tippfehler, veralteter Browser-Tab — wird angenommen und bleibt in
        der Liste. Das ist ein Eintrag je Fall und wird nicht geraeumt.
        """
        ids = self._data.setdefault("dismissed_match_ids", [])
        if match_id not in ids:
            ids.append(match_id)
            self._save()

    def undismiss_match(self, match_id: str) -> None:
        ids = self._data.get("dismissed_match_ids", [])
        if match_id in ids:
            ids.remove(match_id)
            self._save()

    # ------------------------------------------------------------------
    # Explicitly synced name matches
    # ------------------------------------------------------------------

    def get_synced_name_ids(self) -> set[str]:
        return set(self._data.get("synced_name_match_ids", []))

    def mark_all_pairs_synced(self, person_ids: list[str]) -> None:
        """Mark every pairwise combination of person_ids as names-synced."""
        for a, b in combinations(person_ids, 2):
            self.mark_names_synced(self.pair_match_id(a, b))

    def mark_names_synced(self, match_id: str) -> None:
        ids = self._data.setdefault("synced_name_match_ids", [])
        if match_id not in ids:
            ids.append(match_id)
            self._save()

    # ------------------------------------------------------------------
    # Sync log
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_log_timestamp(entry: dict) -> Optional[datetime]:
        """Best-effort parse of a raw log entry's timestamp. Returns None if
        the entry has no usable clock (missing key, not a string, not valid
        ISO-8601) — that is a signal to the caller to treat the entry as
        "can't prove it's old", not an error.

        A timestamp without a UTC offset (e.g. from data written before
        timezone-awareness was consistent) is interpreted as UTC, since every
        timestamp this app writes itself is UTC — otherwise comparing it
        against the (timezone-aware) retention cutoff raises TypeError.
        """
        try:
            timestamp = datetime.fromisoformat(entry["timestamp"])
        except (KeyError, TypeError, ValueError):
            return None
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp

    def _apply_log_retention(self, entries: list[dict]) -> list[dict]:
        """Apply the configured retention window (`log_retention_days`) and the
        500-entry cap to a list of raw sync-log dicts. Used by both the write
        path (`append_log`) and the read path (`get_log`) so the rule holds
        regardless of whether a write ever happens.

        An entry whose timestamp can't be read is kept rather than dropped —
        a broken/missing clock is not evidence the entry is old, and silently
        discarding a log entry because we can't read its clock is exactly the
        kind of quiet data loss this store avoids elsewhere. (Entries that
        are corrupted in some other way — e.g. missing a different required
        field entirely — are handled separately by `_build_log_entries`,
        which is the actual self-healing step; see there.)
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._log_retention_days)
        retained = []
        for entry in entries:
            timestamp = self._parse_log_timestamp(entry)
            if timestamp is not None and timestamp < cutoff:
                continue
            retained.append(entry)
        return retained[-500:]

    @staticmethod
    def _build_log_entries(entries: list[dict]) -> list[SyncLogEntry]:
        """Turn raw sync-log dicts into SyncLogEntry models, skipping (and
        logging) any entry that cannot be built at all — e.g. one missing a
        required field such as `id`, which can happen after a manual/partial
        recovery of accounts.json.

        This is deliberately distinct from `_apply_log_retention`'s "keep an
        unreadable timestamp" rule: a bad timestamp is still a *valid* entry
        (SyncLogEntry.timestamp is a plain str, so any string round-trips),
        but an entry a model can't be constructed from at all is genuinely
        corrupt, not just clock-less. Both `append_log` and `get_log` call
        this, so a single corrupt entry can never take down the whole log —
        and because `append_log` persists its result, such an entry is
        dropped for good on the next write, the same self-healing the store
        already had before this method existed.
        """
        result = []
        for entry in entries:
            try:
                result.append(SyncLogEntry(**entry))
            except ValidationError as exc:
                logger.warning(
                    "Sync log: dropping entry %r that could not be built: %s",
                    entry.get("id", "?"), exc,
                )
        return result

    def append_log(self, entries: list[SyncLogEntry]) -> None:
        # Work on a copy — self._data["sync_log"] must stay untouched until
        # retention + validation have both succeeded. Mutating the live list
        # in place (the previous `setdefault(...).extend(...)` did exactly
        # that) meant a failure partway through this method left the growing,
        # not-yet-pruned list sitting in self._data, ready to be flushed to
        # disk in full by any *unrelated* future _save() call.
        log = list(self._data.get("sync_log", []))
        log.extend(e.model_dump() for e in entries)
        retained = self._apply_log_retention(log)
        self._data["sync_log"] = [e.model_dump() for e in self._build_log_entries(retained)]
        self._save()

    def get_log(self) -> list[SyncLogEntry]:
        # Retention is enforced on read too, not just as a side effect of
        # append_log — otherwise entries only age out when something is
        # written, which is not what "retained for 90 days" promises. This
        # does NOT persist the filtered result: get_log() backs GET
        # /api/sync/log, which the frontend polls every 30s, and rewriting
        # the project's one JSON file on every poll would be a bad trade for
        # pruning a handful of already-invisible, already-capped rows.
        filtered = self._apply_log_retention(self._data.get("sync_log", []))
        return self._build_log_entries(filtered)

    def clear_log(self) -> None:
        self._data["sync_log"] = []
        self._save()

    def mark_log_undone(self, entry_id: str, undone_at: str) -> None:
        for entry in self._data.get("sync_log", []):
            if entry.get("id") == entry_id:
                entry["undone_at"] = undone_at
                self._save()
                return

    # ------------------------------------------------------------------
    # Managed albums
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Auto-sync config
    # ------------------------------------------------------------------

    def get_auto_sync_config(self) -> dict:
        """Returns {"enabled": bool, "time": "HH:MM"}."""
        return dict(self._data.setdefault("auto_sync", {"enabled": False, "time": "01:00"}))

    def set_auto_sync_config(self, enabled: bool, time: str) -> None:
        self._data["auto_sync"] = {"enabled": enabled, "time": time}
        self._save()

    # ------------------------------------------------------------------
    # Managed albums
    # ------------------------------------------------------------------

    def get_managed_albums(self) -> list[ManagedAlbum]:
        return [ManagedAlbum(**a) for a in self._data.get("managed_albums", [])]

    def get_managed_album(self, album_id: str) -> ManagedAlbum | None:
        """Ein einzelnes Album, frisch aus dem Bestand.

        Dafuer da, dass ein Aufrufer INNERHALB seines Schlosses neu lesen kann.
        `get_managed_albums()` baut bei jedem Aufruf neue Objekte, ein
        Schnappschuss von vorher ist also eine echte Kopie — und
        `update_managed_album` ersetzt den Datensatz GANZ. Wer mit einer alten
        Kopie schreibt, macht damit jede Aenderung rueckgaengig, die zwischen
        seinem Lesen und seinem Schreiben liegt.
        """
        for a in self._data.get("managed_albums", []):
            if a["id"] == album_id:
                return ManagedAlbum(**a)
        return None

    def _ohne_tote_konten(self, person_refs: list[dict]) -> list[dict]:
        """Referenzen auf Konten, die es nicht mehr gibt, werden verworfen.

        NACHARBEIT 1 (#117/#121/#103): EINE Regel fuer ALLE Schreiber
        (Abgleich, Umbenennen, Erweitern, Auto-Sync, Anlegen/Verknuepfen) —
        statt sie an jeder Schreibstelle einzeln nachzubauen, sitzt sie hier,
        am einzigen Ort, an dem jeder Schreiber ohnehin vorbeikommt
        (`add_managed_album`/`update_managed_album`). Ein Konto, das
        zwischen dem Lesen eines Schreibers und seinem Zurueckschreiben
        geloescht wurde, kann sich damit nie wieder in einen Datensatz
        schreiben — unabhaengig davon, WANN genau der Schreiber es in seine
        Kopie aufgenommen hat (vor, waehrend oder nach der Loeschung). Das
        schliesst den BLOCKER aus der Nacharbeit strukturell: `extend_match`
        haengt `new_account` an `managed.person_refs` an, bevor es hierher
        schreibt — war das Konto zu DIESEM Zeitpunkt (dem Schreiben, nicht
        dem Anhaengen) schon weg, verschwindet die Referenz hier wieder,
        auch wenn der Immich-Aufruf mit dem alten Schluessel bereits
        zu Ende gelaufen ist (ein laufender Aufruf wird nicht abgebrochen —
        siehe die Docstrings der Aufrufer).

        Referenzen werden NIE neu angehaengt, nur entfernt — das Gegenstueck
        (ein Konto zurueckholen) gibt es hier nicht und braucht es nicht.
        """
        lebende_konten = set(self._data.get("accounts", {}).keys())
        return [r for r in person_refs if r.get("account_id") in lebende_konten]

    def add_managed_album(self, album: ManagedAlbum) -> None:
        # Dieselbe Regel wie beim Zurueckschreiben (siehe `_ohne_tote_konten`):
        # Ein waehrend der Anlage geloeschtes Konto darf nicht in einem NEUEN
        # Album landen (Nacharbeit 1, Tuer 2/4 — gemessen ueber
        # `link_existing_album`). Die Anlage-Schloesser selbst
        # (`gruppen_schloss`/`treffer_schloss`, `resolve_group_id`) bleiben
        # unberuehrt — diese Zeile filtert nur das Ergebnis vor dem Speichern.
        album.person_refs = self._ohne_tote_konten(album.person_refs)
        # Always compute linked_match_ids before saving
        album.linked_match_ids = self._album_linked_match_ids(album)
        albums = self._data.setdefault("managed_albums", [])
        albums.append(album.model_dump())
        self._save()

    def update_managed_album(self, album: ManagedAlbum) -> None:
        """Ersetzt den gespeicherten Datensatz GANZ — wirft, wenn er fehlt.

        Warf frueher NICHTS: Eine unbekannte `album.id` liess die Schleife
        unten ohne Treffer durchlaufen, die Methode kehrte erfolgreich zurueck
        und speicherte STILL NICHTS (#103 Punkt 1, gemessen: Datensatz vorher
        geloescht, Aufrufer meldete trotzdem Erfolg im Protokoll). Niemand
        erfuhr davon — genau die Klasse „stille Fehlgrenze", die dieses
        Projekt schon anderswo getroffen hat (`docs/agents/lehren.md` §17).

        Jetzt WIRFT ein Aufruf mit unbekannter Kennung. Das ist sicher, weil
        JEDER heutige Aufrufer (`_refresh_managed_album_unlocked`,
        `_rename_managed_album_unlocked`, `_extend_match_unlocked` in
        `sync_service.py`, sowie diese Klasse selbst in `delete_account`)
        den Datensatz UNTER DEMSELBEN Albumschloss frisch gelesen hat
        (`_frisch`/`get_managed_album`), bevor er hierher schreibt. Das
        Schloss selbst — nicht die Abwesenheit von `await` zwischen Lesen und
        Schreiben, die es an mehreren Stellen durchaus gibt (Immich-Aufrufe
        in `_refresh_managed_album_unlocked` u. a.) — ist es, was ein
        Verschwinden DES ALBUMS zwischen jenem Lesen und diesem Schreiben
        ausschliesst: Ein zweiter Schreiber oder `delete_managed_album`
        braeuchte fuer denselben Schritt dasselbe Schloss (Nacharbeit 1 —
        vorher stand hier faelschlich „kein await dazwischen"). Trifft die
        Ausnahme trotzdem, ist das ein Fehler in genau dieser Verdrahtung —
        ein neuer Aufrufer, der die Schlossregel nicht einhaelt — und kein
        normaler Betriebsfall, den ein Aufrufer abfangen muesste.

        SEIT NACHARBEIT 1 FILTERT AUCH DIESE METHODE tote Kontoreferenzen
        heraus (`_ohne_tote_konten`) — siehe dort fuer die Begruendung. Das
        gilt fuer JEDEN Aufrufer gleichermassen, auch fuer `delete_account`
        selbst, das denselben Weg nimmt.
        """
        album.person_refs = self._ohne_tote_konten(album.person_refs)
        # Always recompute linked_match_ids before saving
        album.linked_match_ids = self._album_linked_match_ids(album)
        albums = self._data.get("managed_albums", [])
        for i, a in enumerate(albums):
            if a["id"] == album.id:
                albums[i] = album.model_dump()
                self._save()
                return
        raise LookupError(
            f"update_managed_album: Album {album.id!r} steht nicht (mehr) im "
            "Bestand. Aufrufer muessen den Datensatz unter demselben "
            "Albumschloss frisch gelesen haben (siehe sync_service._frisch)."
        )

    def delete_managed_album(self, album_id: str) -> bool:
        albums = self._data.get("managed_albums", [])
        new_albums = [a for a in albums if a["id"] != album_id]
        if len(new_albums) == len(albums):
            return False
        self._data["managed_albums"] = new_albums
        self._save()
        return True
