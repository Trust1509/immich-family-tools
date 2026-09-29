from pydantic import BaseModel, Field
from typing import Callable, Optional
from enum import Enum


class MatchReason(str, Enum):
    name_similarity = "name_similarity"
    embedding_similarity = "embedding_similarity"
    manual = "manual"


class MatchStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    dismissed = "dismissed"


class PersonRef(BaseModel):
    person_id: str
    person_name: Optional[str]
    account_id: str
    account_name: str
    account_color: str


class Match(BaseModel):
    id: str  # deterministic: sorted(personA_id, personB_id) joined
    person_a: PersonRef
    person_b: PersonRef
    confidence: float  # 0.0 – 1.0
    reasons: list[MatchReason]
    status: MatchStatus = MatchStatus.pending
    # Enriched fields (set by router, not by face_matcher)
    has_album: bool = False
    names_synced: bool = False


class ManagedAlbum(BaseModel):
    """An album created and managed by this tool."""
    id: str                      # internal UUID
    match_id: str                # original match or manual ID
    album_id: str                # Immich album UUID (in owner account)
    album_name: str              # reiner Anzeigetext — NICHT der Gruppenschluessel
    # Stabile Gruppenkennung (#78). Alben mit derselben Kennung gehoeren
    # zusammen; ihre Personen gelten als transitiv verbunden.
    #
    # PFLICHTFELD OHNE VORGABEWERT, und das ist Absicht: Ein
    # `Optional[str] = None` gaebe jedem Album ohne Kennung denselben
    # Schluessel und verschmoelze alle zu EINER Gruppe — genau der Defekt,
    # den diese Kennung behebt, nur schlimmer. Eine vergessene Zuweisung
    # muss laut scheitern. Fuer Altbestaende fuellt `_migrate()` das Feld.
    #
    # `min_length=1`, weil der Kommentar sonst mehr behauptet als der Typ
    # haelt: Gemessen vom Panel blieb die Mutation `group_id=""` an beiden
    # Erzeugungsstellen gruen — und eine leere Kennung tut genau das, wovor
    # der Absatz oben warnt, nur ohne den lauten Fehler.
    group_id: str = Field(min_length=1)
    owner_account_id: str        # account that owns the album
    person_refs: list[dict]      # [{"account_id", "person_id", "person_name", "account_name", "account_color"}]
    linked_match_ids: list[str] = Field(default_factory=list)
    created_at: str
    last_synced_at: Optional[str] = None
    total_assets: int = 0
    status: str = "active"  # pending | active | partial


class ManagedAlbumOut(ManagedAlbum):
    """`ManagedAlbum` plus zwei beim LESEN berechnete Markierungen (#99, #112).

    Eigenes Antwortmodell statt neuer Felder auf `ManagedAlbum` selbst: Die
    Basisklasse ist auch das Speicherformat — `ConfigStore.add_managed_album`
    und `.update_managed_album` schreiben sie ueber `album.model_dump()`
    direkt in `accounts.json`. Ein Feld dort wuerde mit jedem Speichern
    mitgeschrieben, auch wenn es nie vom Nutzer gesetzt wird — genau die
    Schema-Aenderung, die dieser Slice ausdruecklich NICHT vornehmen soll.
    Nur `routers/albums.py::list_managed_albums` baut dieses Modell, aus dem
    aktuellen Kontenbestand, bei jedem Aufruf neu.

    `owner_account_missing`: das Besitzerkonto (`owner_account_id`) existiert
    nicht mehr im Kontenbestand — das verwaiste Album aus `CONTEXT.md`.
    `too_few_people`: weniger als zwei Referenzen in `person_refs` zeigen auf
    ein NOCH LEBENDES Konto (Nacharbeit 1, #117/#121/#103) — kann unabhaengig
    vom Besitzerkonto eintreten (ein Teilnehmer, nicht der Besitzer, wurde
    geloescht) und blockiert fuer sich allein weder Umbenennen noch
    Abgleichen. Eine Referenz auf ein bereits geloeschtes Konto zaehlt NICHT
    mit — sie kann liegen bleiben, bis zum ENDE DER GERADE LAUFENDEN
    BEARBEITUNG dieses Albums (ihr Album war beim Loeschen gerade durch ein
    anderes Schloss belegt), spaetestens aber bis zum naechsten Start
    (Nacharbeit 2, #117/#121/#103 — `sync_service._raeume_tote_referenzen_
    synchron` raeumt sie im `finally` jedes Schloss-Wrappers, unabhaengig
    davon, wie dieser endet; `ConfigStore._migrate` raeumt beim Start, falls
    zwischenzeitlich keine dieser Bearbeitungen mehr lief).
    """
    owner_account_missing: bool = False
    too_few_people: bool = False


class SyncNamesRequest(BaseModel):
    match_id: str
    name: str  # The canonical name to set on both persons


class MultiSyncPersonEntry(BaseModel):
    account_id: str
    person_id: str


class SyncNamesMultiRequest(BaseModel):
    persons: list[MultiSyncPersonEntry]        # one entry per account, min 2
    canonical_name: str
    album_name: Optional[str] = None           # if set, create new shared album
    existing_album_id: Optional[str] = None    # if set, link existing album instead
    owner_account_id: Optional[str] = None     # album owner; defaults to first person's account
    # Ausdrueckliche Gruppenwahl (#81). Ohne beides entscheidet wie bisher
    # der Name; `group_id` tritt einer BESTEHENDEN Gruppe bei, `force_new_group`
    # erzwingt eine eigene. Beides zugleich wird abgelehnt.
    group_id: Optional[str] = None
    force_new_group: bool = False


class ExtendMatchRequest(BaseModel):
    managed_album_id: str     # which ManagedAlbum to extend
    account_id: str           # new account to add
    person_id: str            # person in that account
    person_name: Optional[str] = None     # display name of the person (for person_refs)
    canonical_name: Optional[str] = None  # if set, rename person to this


class SyncAlbumRequest(BaseModel):
    match_id: str
    owner_account_id: str
    album_name: Optional[str] = None        # for new album
    existing_album_id: Optional[str] = None # for linking existing album
    # Ausdrueckliche Gruppenwahl (#81). Ohne beides entscheidet wie bisher
    # der Name; `group_id` tritt einer BESTEHENDEN Gruppe bei, `force_new_group`
    # erzwingt eine eigene. Beides zugleich wird abgelehnt.
    group_id: Optional[str] = None
    force_new_group: bool = False


class RenameManagedAlbumRequest(BaseModel):
    album_name: str


# Test-only Erweiterungspunkt fuer die Laufzeitpruefung des Sync-Log-Vertrags
# (#115, Nacharbeit 2 -- siehe `backend/tests/conftest.py`). Ausserhalb von
# Tests bleibt dieser Name IMMER `None`, und `SyncLogEntry.model_post_init`
# tut dann buchstaeblich nichts -- das Produktionsverhalten aendert sich
# dadurch NICHT: kein Log, kein Abbruch eines Abgleichs wegen eines
# Uebersetzungsfehlers, kein sonstiger Seiteneffekt, solange kein Test den
# Haken einhaengt. Die Fixture in `conftest.py` haengt sich NUR fuer die
# Dauer eines einzelnen Tests ein und haengt sich in ihrem `finally` wieder
# aus -- dieser Name traegt also nie Zustand ueber einen Test hinaus.
#
# Warum hier und nicht ausschliesslich in den Tests: Eine reine Testfixture
# kann `__init__` monkeypatchen, sieht damit aber `model_validate`/
# `model_construct`/den `response_model`-Weg von FastAPI nicht (Pydantic v2
# ruft dafuer nicht `__init__`, sondern validiert ueber den generierten
# Validator, der `model_post_init` unabhaengig vom Konstruktionsweg aufruft).
# Diese eine Zeile Produktionscode ist damit die einzige Stelle, die ALLE
# Konstruktionswege einheitlich sieht, ohne fuer jeden einzeln einen eigenen
# Monkeypatch zu brauchen.
_SYNC_LOG_LAUFZEIT_HAKEN: Optional[Callable[["SyncLogEntry"], None]] = None


class SyncLogEntry(BaseModel):
    id: str
    timestamp: str
    action: str
    details: str
    status: str  # "success" | "error"
    error_message: Optional[str] = None
    undo_data: Optional[dict] = None
    undone_at: Optional[str] = None
    correlation_id: Optional[str] = None
    # Structured message for localized frontend rendering. `details` (German)
    # remains the fallback for entries persisted before this was introduced.
    message_key: Optional[str] = None
    message_params: Optional[dict] = None

    def model_post_init(self, __context) -> None:
        """Test-only Erweiterungspunkt (#115, Nacharbeit 2) -- siehe
        `_SYNC_LOG_LAUFZEIT_HAKEN` oben und `backend/tests/conftest.py`.
        Ausserhalb von Tests ist der Haken `None` und diese Methode ist ein
        reines No-Op; Pydantic ruft sie nach JEDER erfolgreichen
        Konstruktion auf, unabhaengig vom Weg (`__init__`, `model_validate`,
        `model_construct`, der `response_model`-Validierungspfad von
        FastAPI) -- deckt damit auch Unterklassen ab, da sie diese Methode
        erben, sofern sie sie nicht selbst ueberschreiben."""
        if _SYNC_LOG_LAUFZEIT_HAKEN is not None:
            _SYNC_LOG_LAUFZEIT_HAKEN(self)
