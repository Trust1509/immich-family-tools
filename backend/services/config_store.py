"""
Persistent config storage: accounts + dismissed match IDs + sync log + managed albums.
Backed by a JSON file on the Docker volume.
"""
import asyncio
import hashlib
import json
import logging
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from models.account import Account, AccountCreate
from models.match import ManagedAlbum, SyncLogEntry

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

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
                if not isinstance(self._data, dict) or not isinstance(self._data.get("accounts", {}), dict):
                    raise ValueError("invalid configuration schema")
                self._data.setdefault("managed_albums", [])
                logger.info("Config loaded from %s", self._path)
                self._migrate()
            except Exception as exc:
                raise RuntimeError(
                    f"Configuration {self._path} is invalid and was left untouched. "
                    f"Restore a ZFS snapshot, {self._path}.vor-schema-*.bak "
                    f"(the state before the last schema migration) or "
                    f"{self._path}.bak (may already carry the migrated state)."
                ) from exc

    def _sichere_vor_schemasprung(self, *, einmalig: bool) -> None:
        """Einmalige, versionierte Sicherung vor einem Schemasprung.

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
            fd, temp_name = tempfile.mkstemp(prefix=f".{ziel.name}.", dir=ziel.parent)
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
            logger.warning("Sicherung vor Schemasprung nicht moeglich: %s", ziel)
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
        logger.info("Sicherung vor Schemasprung: %s", ziel)

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
        """One-time repair of managed_albums: fill missing fields from live account data."""
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

        for album in albums:
            album_name = album.get("album_name", "")

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
            computed = self.compute_linked_match_ids(album.get("person_refs", []))
            if set(album.get("linked_match_ids", [])) != set(computed):
                album["linked_match_ids"] = computed
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
        return str(album_name).strip().lower()

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
            kandidaten = bekannt.get(schluessel, set())
            if not schluessel or len(kandidaten) > 1:
                album["group_id"] = str(uuid.uuid4())
            elif len(kandidaten) == 1:
                album["group_id"] = next(iter(kandidaten))
            else:
                album["group_id"] = frisch.setdefault(schluessel, str(uuid.uuid4()))
            changed = True
        return changed

    def _gruppen_je_name(self, albums: list[dict]) -> dict[str, set[str]]:
        """Normalisierter Name -> alle Gruppenkennungen, die ihn tragen.

        Mehr als eine bedeutet: Der Name ist mehrdeutig geworden.
        """
        karte: dict[str, set[str]] = {}
        for album in albums:
            if album.get("group_id"):
                karte.setdefault(self._name_key(album.get("album_name", "")),
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

        BENANNTE DRITTE GRENZE, gemessen statt behauptet: Die Normalisierung
        ist `strip().lower()` — keine Unicode-Normalform, kein `casefold`.
        Zwei sichtbar gleiche Namen koennen daher als verschieden gelten
        (NFC gegen NFD bei "Café", "istanbul" gegen "İstanbul", ein
        unsichtbares Trennzeichen davor), und dann sagt diese Abfrage "keine
        Gruppe", obwohl eine da ist. Das ist Erbe aus #78 — neu ist, dass
        daraus seit #81 eine ZUSAGE AN DEN NUTZER wird. Als Folge-Issue
        vermerkt, nicht hier behoben: Eine Normalisierung aendert die
        Schluessel und ist damit selbst eine Datenwanderung.
        """
        schluessel = self._name_key(album_name)
        if not schluessel:
            return None
        kandidaten = self._gruppen_je_name(self._data.get("managed_albums", [])).get(
            schluessel, set()
        )
        return next(iter(kandidaten)) if len(kandidaten) == 1 else None

    def group_details(self, group_id: str) -> dict:
        """Wem tritt man bei — die Personen und Albumnamen einer Gruppe.

        Ohne das waere die Bestaetigung beim Anlegen eine leere Geste: Der
        Nutzer soll sehen, WEM er beitritt, nicht nur DASS er beitritt.

        Die Personen werden ueber Konto UND Person entdoppelt; zwei
        Immich-Instanzen koennen dieselbe Personen-Kennung vergeben.
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
        return {
            "group_id": group_id,
            "album_names": sorted({a.get("album_name", "") for a in alben}),
            "person_refs": refs,
        }

    def resolve_group_id(self, album_name: str, *,
                         chosen: Optional[str] = None,
                         force_new: bool = False) -> str:
        """Welche Gruppe es WIRKLICH wird — einziger Eigentuemer der Regel.

        Ohne Angabe bleibt es beim heutigen Verhalten (der Name entscheidet).
        Eine ausdrueckliche Wahl schlaegt den Namen; eine unbekannte Kennung
        wird ABGELEHNT, statt eine Gruppe zu erfinden — sonst legt ein
        Tippfehler eine Geistergruppe an, zu der nie ein zweites Album findet,
        und niemand sieht es, weil das Anlegen gelingt.
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
        return self.group_id_for_name(album_name)

    def gruppen_schloss(self, album_name: str) -> asyncio.Lock:
        """Das Schloss fuer diesen Albumnamen.

        Der Aufrufer haelt es ueber die GANZE Strecke von der Aufloesung bis
        zum Speichern — sonst schuetzt es die Luecke nicht, um die es geht.
        Gesperrt wird nur gegen Anlagen mit DEMSELBEN Namen; alles andere
        laeuft weiter.
        """
        schluessel = (id(asyncio.get_running_loop()), self._name_key(album_name))
        return _gruppen_schloesser.setdefault(schluessel, asyncio.Lock())

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

        Einziger Eigentuemer dieser Regel — die Stellen, die frueher je eigene
        Namensgruppen bildeten, fragen ab jetzt nur noch nach group_id.
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
        fd, temp_name = tempfile.mkstemp(prefix=f".{self._path.name}.", dir=self._path.parent)
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

    def delete_account(self, account_id: str) -> bool:
        if account_id not in self._data["accounts"]:
            return False
        account_name = self._data["accounts"][account_id].get("name", "")
        del self._data["accounts"][account_id]
        cleaned_albums = []
        for album in self._data.get("managed_albums", []):
            album["person_refs"] = [
                ref for ref in album.get("person_refs", [])
                if ref.get("account_id") != account_id
            ]
            if len(album["person_refs"]) >= 2:
                album["linked_match_ids"] = self.compute_linked_match_ids(album["person_refs"])
                cleaned_albums.append(album)
        self._data["managed_albums"] = cleaned_albums
        self._data["dismissed_match_ids"] = []
        self._data["synced_name_match_ids"] = []
        self._data["sync_log"] = [
            entry for entry in self._data.get("sync_log", [])
            if (entry.get("undo_data") or {}).get("account_id") != account_id
            and (not account_name or account_name not in entry.get("details", ""))
        ]
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

    def add_managed_album(self, album: ManagedAlbum) -> None:
        # Always compute linked_match_ids before saving
        album.linked_match_ids = self.compute_linked_match_ids(album.person_refs)
        albums = self._data.setdefault("managed_albums", [])
        albums.append(album.model_dump())
        self._save()

    def update_managed_album(self, album: ManagedAlbum) -> None:
        # Always recompute linked_match_ids before saving
        album.linked_match_ids = self.compute_linked_match_ids(album.person_refs)
        albums = self._data.get("managed_albums", [])
        for i, a in enumerate(albums):
            if a["id"] == album.id:
                albums[i] = album.model_dump()
                self._save()
                return

    def delete_managed_album(self, album_id: str) -> bool:
        albums = self._data.get("managed_albums", [])
        new_albums = [a for a in albums if a["id"] != album_id]
        if len(new_albums) == len(albums):
            return False
        self._data["managed_albums"] = new_albums
        self._save()
        return True
