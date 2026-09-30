"""Fehlermeldungen mit Schluessel, damit das Frontend sie uebersetzen kann.

DAS TRAGENDE PRINZIP: DER DEUTSCHE TEXT BLEIBT IN DER ANTWORT.

Die Antwort traegt beides — den Schluessel UND den Klartext:

    {
      "detail": "Account nicht gefunden",
      "error_key": "err_account_not_found",
      "error_params": {}
    }

`detail` bleibt eine Zeichenkette und bleibt deutsch. Das ist Absicht und
keine Bequemlichkeit:

  - Wer eine Meldung schon vorher ueber `AppError` bekam, merkt von der
    Erweiterung um `error_key`/`error_params` nichts — `detail` aendert sich
    fuer sie nicht. EINE Ausnahme, ehrlich benannt (Nacharbeit 1 zu #85):
    FastAPIs eigene Validierungsfehler (`RequestValidationError`) lieferten
    VORHER `detail` als LISTE, kein `error_key`. Seit #85 liefert auch dieser
    Pfad einen Zeichenketten-`detail` in derselben Form
    (`backend/main.py`, `_validation_error_handler`) — das IST eine
    sichtbare Aenderung fuer jeden, der die Schnittstelle direkt anspricht
    und bisher FastAPIs Listenform las.
  - Der Rueckfall steckt in der Antwort SELBST. Ein Frontend, das den
    Schluessel nicht kennt — eine aeltere Fassung, eine neue Meldung, ein
    Tippfehler — zeigt den deutschen Satz statt gar nichts. Der teuerste
    Fehler dieses Pfades waere "Error:" gefolgt von Leere; genau den kann es
    so nicht geben.

Das Muster ist nicht neu hier: Der Sync-Log fuehrt seit v1.4.0 `message_key` +
`message_params` statt Klartext (`models/match.py`, `services/sync_service.py`).
Dies ist dasselbe fuer den Fehlerpfad.

WER EINEN SCHLUESSEL HINZUFUEGT, traegt ihn auch in `frontend/src/i18n.tsx`
ein. Die beiden Mengen werden von einem Test verglichen
(`backend/tests/test_errors.py`), damit sie nicht auseinanderlaufen — eine
Regel, die nur als Kommentar existiert, ist keine.
"""

from typing import Any, Callable, Optional

from fastapi import HTTPException


class AppError(HTTPException):
    """HTTPException mit Uebersetzungs-Schluessel.

    `text` ist der deutsche Klartext und landet unverandert in `detail`;
    `key` und `params` kommen als eigene Felder daneben. Das Zusammensetzen
    der Antwort macht der Handler in `main.py`.
    """

    def __init__(
        self,
        status_code: int,
        key: str,
        text: str,
        params: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=text)
        self.key = key
        self.params = params or {}


# ── Die Meldungen ──────────────────────────────────────────────────────────
#
# DIE STATUSCODES SIND ABGESCHRIEBEN, NICHT GEWAEHLT. Beim ersten Anlauf habe
# ich vier davon "aufgeraeumt" (422 -> 400 bzw. 409), weil sie mir passender
# schienen — im selben Commit, der behauptete, an der Schnittstelle aendere
# sich nichts. Ein Statuscode ist der haertere Teil des Vertrags als der Text:
# Fremdkonsumenten verzweigen darauf. Von der blinden Panel-Stimme gefunden,
# die es an der laufenden App gegen den Elternstand gemessen hat.
# Wer hier einen Code aendert, aendert die Schnittstelle. Das ist ein eigener
# Slice, kein Nebeneffekt.
#
# Als Funktionen und nicht als Konstanten, weil einige Parameter tragen und
# weil ein Aufruf an der Fundstelle lesbarer ist als ein Konstantenname.
# Die Statuscodes stehen HIER und nicht an den Fundstellen: derselbe Fehler
# hat sonst an neun Stellen die Chance, einen anderen Code zu bekommen.


def account_not_found() -> AppError:
    return AppError(404, "err_account_not_found", "Account nicht gefunden")


def account_gone() -> AppError:
    return AppError(404, "err_account_gone", "Account nicht mehr vorhanden")


def owner_account_not_found() -> AppError:
    return AppError(404, "err_owner_account_not_found", "Owner-Account nicht gefunden")


def match_not_found() -> AppError:
    return AppError(404, "err_match_not_found", "Match nicht gefunden")


def managed_album_not_found() -> AppError:
    return AppError(404, "err_managed_album_not_found", "Managed Album nicht gefunden")


def log_entry_not_found() -> AppError:
    return AppError(404, "err_log_entry_not_found", "Log-Eintrag nicht gefunden")


def no_thumbnail() -> AppError:
    return AppError(404, "err_no_thumbnail", "Kein Thumbnail vorhanden")


def immich_unreachable() -> AppError:
    return AppError(
        422,
        "err_immich_unreachable",
        "Immich API nicht erreichbar oder Token ungültig",
    )


def immich_request_failed() -> AppError:
    return AppError(502, "err_immich_request_failed", "Immich-Anfrage fehlgeschlagen")


def album_name_required() -> AppError:
    return AppError(
        # Neutral, weil dieselbe Meldung seit #79 auch beim Umbenennen kommt.
        422, "err_album_name_required", "album_name erforderlich"
    )


def manual_match_id_collision(album_name: str) -> AppError:
    """Gleiche manuelle Kennung, ANDERE Personen.

    Die manuelle Kennung ist `manual_<name>_<owner[:8]>` — die ausgewaehlten
    Personen stehen NICHT darin. Zwei verschiedene Gruppen mit demselben
    kanonischen Namen und demselben Eigentuemer teilen sie sich also.

    Das ist KEIN Doppelklick und darf nicht als einer behandelt werden: Der
    Aufrufer will ein Album fuer ANDERE Personen. Hier wird abgelehnt, und
    zwar VOR jedem Schreibvorgang — der Aufrufer soll den Namen aendern.
    """
    gekuerzt = _gekuerzt(album_name)
    return AppError(
        409,
        "err_manual_match_id_collision",
        f"Unter diesem Namen gibt es bereits das Album '{gekuerzt}', und es "
        f"gehört zu einer anderen Personenauswahl. Erweitere dieses Album, "
        f"oder wähle einen anderen Namen.",
        {"album": gekuerzt},
    )


def min_two_people() -> AppError:
    return AppError(422, "err_min_two_people", "Mindestens 2 Personen erforderlich")


def not_undoable() -> AppError:
    return AppError(
        422, "err_not_undoable", "Aktion kann nicht rückgängig gemacht werden"
    )


def invalid_token() -> AppError:
    # Wird nie angezeigt — AuthGate bildet 401 auf einen eigenen Schluessel ab.
    # Traegt trotzdem einen, damit die Regel "jede Meldung hat einen" ohne
    # Ausnahme gilt und der Abgleich-Test nicht mit Sonderfaellen anfaengt.
    return AppError(401, "err_invalid_token", "Invalid token")


def too_many_login_attempts() -> AppError:
    # Ebenfalls nie angezeigt (429 -> eigener Schluessel in AuthGate).
    return AppError(
        429,
        "err_too_many_login_attempts",
        "Too many login attempts. Try again in one minute.",
    )


def invalid_time_format() -> AppError:
    return AppError(
        422, "err_invalid_time_format", "Invalid time format. Use HH:MM (e.g. 01:00)"
    )


def unsupported_immich_version(major: object, minor: object) -> AppError:
    gekuerzt_major, gekuerzt_minor = _gekuerzt(major), _gekuerzt(minor)
    return AppError(
        422,
        "err_unsupported_immich_version",
        f"Immich-Version {gekuerzt_major}.{gekuerzt_minor} wird nicht unterstützt — "
        "dieses Tool benötigt Immich v3.x (Server meldet Version über "
        "/api/server/version).",
        {"major": gekuerzt_major, "minor": gekuerzt_minor},
    )


# ── Meldungen mit Werten ───────────────────────────────────────────────────
#
# Die Werte kommen aus den Daten des Nutzers (Account-Namen, Album-Namen,
# IDs) und gehen an genau den Nutzer zurueck, dem sie gehoeren. Das ist in
# Ordnung — aber `params` darf deshalb NICHT unbesehen in ein Log oder eine
# Fehlersammlung wandern. Wer das je einbaut, entscheidet das bewusst.
#
# UND: EIN ZURUECKGESPIEGELTER WERT IST EIN KANAL, KEINE GRENZE (#85 Punkt 4).
# `group_not_found` reichte eine vom Aufrufer gewaehlte Kennung ungekuerzt in
# `detail` UND `error_params` zurueck — eine sehr lange Kennung (im Issue
# gemessen, mehrere tausend Zeichen) kam vollstaendig zurueck. Jede Funktion
# hier unten, die einen Client-Wert in die Antwort schreibt, kuerzt ihn
# deshalb ueber `_gekuerzt()` — EINE Stelle, damit eine neue Meldung mit
# Wert die Kappung automatisch mitbekommt, statt sie an der Fundstelle neu zu
# erfinden (und dort zu vergessen).

_MAX_GESPIEGELTE_LAENGE = 200


def _gekuerzt(wert: object) -> str:
    """Kappt einen vom Client stammenden, in eine Fehlermeldung
    zurueckgespiegelten Wert auf `_MAX_GESPIEGELTE_LAENGE` Zeichen —
    genauer: Wird gekuerzt, kommt zusaetzlich EIN Ellipsis-Zeichen dazu, das
    Ergebnis ist dann `_MAX_GESPIEGELTE_LAENGE + 1` Zeichen lang, nicht
    exakt `_MAX_GESPIEGELTE_LAENGE` (Nacharbeit 1 zu #85 — vorher stand hier
    die ungenaue Behauptung "auf N Zeichen", tatsaechlich sind es bis zu
    N + 1).

    Ohne diese Kappung bestimmt der Client die Laenge der Antwort — nicht nur
    fuer eine gezielt lange Kennung, sondern auch fuer einen Feldnamen aus
    einem abgelehnten Zusatzfeld (`extra="forbid"` spiegelt den vom Client
    GEWAEHLTEN Feldnamen zurueck, siehe `validation_failed` unten): Beides
    ist Text, den der Aufrufer frei waehlt, keiner, den das Schema vorgibt.
    """
    text = str(wert)
    if len(text) <= _MAX_GESPIEGELTE_LAENGE:
        return text
    return text[:_MAX_GESPIEGELTE_LAENGE] + "…"


def account_id_not_found(account_id: str) -> AppError:
    gekuerzt = _gekuerzt(account_id)
    return AppError(
        404,
        "err_account_id_not_found",
        f"Account {gekuerzt} nicht gefunden",
        {"id": gekuerzt},
    )


def owner_account_id_not_found(owner_id: str) -> AppError:
    gekuerzt = _gekuerzt(owner_id)
    return AppError(
        404,
        "err_owner_account_id_not_found",
        f"Owner-Account {gekuerzt} nicht gefunden",
        {"id": gekuerzt},
    )


def person_validation_failed(account_name: str) -> AppError:
    gekuerzt = _gekuerzt(account_name)
    return AppError(
        422,
        "err_person_validation_failed",
        f"Person in Account '{gekuerzt}' konnte nicht validiert werden",
        {"account": gekuerzt},
    )


# ── Die Middleware-Pfade ───────────────────────────────────────────────────
#
# main.py baut seine Fehlerantworten VOR jedem Router von Hand als
# JSONResponse. Ein Exception-Handler greift dort nicht — die drei Faelle
# muessen dieselbe Form selbst erzeugen. Deshalb stehen sie hier und nicht
# als AppError: `antwort()` unten liefert das Woerterbuch, das sie brauchen.


def request_too_large() -> AppError:
    return AppError(413, "err_request_too_large", "Request body too large")


def invalid_content_length() -> AppError:
    return AppError(400, "err_invalid_content_length", "Invalid Content-Length")


def unauthorized() -> AppError:
    return AppError(401, "err_unauthorized", "Unauthorized")


def antwort(fehler: AppError) -> dict[str, Any]:
    """Die Antwortform als Woerterbuch — fuer Wege, die keine Ausnahme werfen.

    EINE Stelle erzeugt die Form, damit der Handler und die Middleware nicht
    auseinanderlaufen koennen. Genau diese Doppelung waere sonst der Ort, an
    dem ein Pfad still beim alten Format bleibt.
    """
    return {
        "detail": fehler.detail,
        "error_key": fehler.key,
        "error_params": fehler.params,
    }


def group_choice_conflict() -> AppError:
    return AppError(
        422, "err_group_choice_conflict",
        "Entweder eine bestehende Gruppe wählen ODER eine eigene anlegen, nicht beides",
    )


def group_not_found(group_id: str) -> AppError:
    gekuerzt = _gekuerzt(group_id)
    return AppError(
        404, "err_group_not_found",
        f"Gruppe {gekuerzt} existiert nicht",
        {"group_id": gekuerzt},
    )


def group_choice_required(album_name: str) -> AppError:
    """Mehrdeutiger Name, keine ausdrueckliche Wahl (#113).

    `existing_group_for_name` kollabiert "mehrdeutig" auf dasselbe `None` wie
    "unbekannt" — dort war deshalb nicht zu unterscheiden. `resolve_group_id`
    fragt seit #113 die rohen Kandidaten (`group_candidates_for_name`) und
    lehnt hiermit ab, statt still eine dritte Gruppe zu oeffnen. 409, nicht
    422: Es liegt kein fehlerhaftes Feld vor, sondern ein bestehender
    Zustand (mehrere Gruppen), der eine Angabe ERFORDERLICH macht, die noch
    fehlt — dieselbe Familie wie `manual_match_id_collision`.
    """
    gekuerzt = _gekuerzt(album_name)
    return AppError(
        409,
        "err_group_choice_required",
        f"Der Name '{gekuerzt}' gehört zu mehreren Gruppen — wähle eine "
        f"davon oder lege eine eigene Gruppe an.",
        {"album": gekuerzt},
    )


def group_situation_changed(album_name: str) -> AppError:
    """Der Aufrufer erwartete "keine Gruppe", jetzt gibt es eine (#119).

    Trifft zu, wenn ein Client `expected_no_group=true` mitschickt (seine
    Vorschau zeigte "keine Gruppe"), aber zwischen Vorschau und Anfrage eine
    ANDERE Anfrage genau diesen Namen einer Gruppe zugeordnet hat. 409 wie
    `group_choice_required`: kein fehlerhaftes Feld, ein Zustand, der sich
    seit der Vorschau des Aufrufers geaendert hat.
    """
    gekuerzt = _gekuerzt(album_name)
    return AppError(
        409,
        "err_group_situation_changed",
        f"Die Gruppenlage zu '{gekuerzt}' hat sich seit der Vorschau "
        f"geändert — bitte erneut prüfen.",
        {"album": gekuerzt},
    )


# ── Der house-form-Vertrag fuer FastAPIs EIGENE Validierungsfehler ─────────
#
# #85 Punkt 1: FastAPI/Pydantic werfen `RequestValidationError` fuer jeden
# fehlerhaften Request-Koerper oder -Query-Parameter, BEVOR ein Router
# ueberhaupt laeuft — das trifft auch `extra="forbid"` (Punkt 2 oben). Ohne
# diese Funktion antwortete dieser Pfad mit FastAPIs Standardform
# (`{"detail": [...]}`, eine LISTE, kein `error_key`) und brach damit genau
# die Zusage, die dieses Modul allen ANDEREN Fehlern gibt. `main.py` registriert
# den Handler; hier steht nur das Zusammensetzen der Antwortform, aus
# demselben Grund wie bei jeder anderen Meldung in dieser Datei.


# Wie viele eindeutige Feldnamen die Meldung EINZELN nennt, bevor der Rest
# in einem "... und N weitere" zusammengefasst wird (Nacharbeit 1 zu #85,
# Punkt 1/3). Eine reine Lesbarkeits-/Groessenentscheidung, KEINE Messung —
# nicht mit den Zeitangaben im Docstring unten verwechseln, die sind
# gemessen. 20 haelt `detail`/`error_params` auch bei einer riesigen Anzahl
# Client-Feldnamen auf wenige tausend Zeichen begrenzt, unabhaengig von der
# Kappung je einzelnem Namen.
_MAX_ANGEZEIGTE_FELDER = 20


def validation_failed(field_names: list[str]) -> AppError:
    """Baut die Hausform aus den Feldnamen von `RequestValidationError.errors()`.

    JEDER Feldname wird ueber `_gekuerzt()` gekappt (#85 Punkt 4): Bei
    `extra="forbid"` ist der "Feldname" im Fehler exakt das, was der Client
    als Schluessel geschickt hat — ein Client kann dort denselben beliebig
    langen Text unterbringen wie frueher in einer Gruppen-Kennung.

    Die Meldung ist absichtlich ZAHL-INVARIANT formuliert ("... fuer: a, b")
    statt mit einem Substantiv, das im Singular und Plural verschieden
    dekliniert werden muesste ("Feld"/"Felder") — dieselbe Konstruktion traegt
    einen wie mehrere Feldnamen grammatisch korrekt, ohne dass Uebersetzung
    UND Kappung zusaetzlich eine Anzahl durchreichen muessten.

    NEU (Nacharbeit 1 zu #85, Punkt 1): Die Dedopplung prueft ueber eine
    MENGE (`gesehen`), nicht mehr ueber `name not in eindeutig` auf einer
    LISTE — Letzteres war quadratisch in der Anzahl der Fehler. Gemessen,
    isoliert (diese Funktion direkt aufgerufen, ausserhalb der Testsuite,
    Entwicklungsrechner, vor diesem Fix): 10 000 Feldnamen 0,31 s, 30 000
    Feldnamen 2,70 s, 50 000 Feldnamen 8,23 s — deutlich mehr als linear.
    Nach dem Fix, dieselbe Messung: 50 000 Feldnamen 0,005 s.

    NEU (Punkt 3): Selbst mit O(n) waechst `detail`/`error_params` sonst
    weiter mit dem Client-Input — bei vielen tausend eindeutigen Feldnamen
    eine unbegrenzte Antwort. Deshalb werden nur die ersten
    `_MAX_ANGEZEIGTE_FELDER` einzeln genannt, der Rest als Zahl.
    """
    gesehen: set[str] = set()
    eindeutig: list[str] = []
    for roh in field_names:
        name = _gekuerzt(roh)
        if name not in gesehen:
            gesehen.add(name)
            eindeutig.append(name)
    gesamt = len(eindeutig)
    if gesamt > _MAX_ANGEZEIGTE_FELDER:
        rest = gesamt - _MAX_ANGEZEIGTE_FELDER
        liste = ", ".join(eindeutig[:_MAX_ANGEZEIGTE_FELDER]) + f", … und {rest} weitere"
    else:
        liste = ", ".join(eindeutig) if eindeutig else "?"
    return AppError(
        422,
        "err_validation_failed",
        # "Ungueltiger Wert" traf den Fall "Feld fehlt" oder "unbekanntes
        # Feld" nie wirklich (da liegt kein WERT vor, der ungueltig waere).
        # Genaues Unterscheiden von "unbekannt"/"fehlt"/"falscher Typ" je
        # Fehlerart wurde geprueft und zurueckgestellt (Bericht, KLEIN-Punkt
        # "Unbekanntes Feld/fehlt/falscher Typ") — der neutralere Wortlaut
        # hier ist der im Bau-Brief benannte Ersatz dafuer.
        f"Ungültige oder unbekannte Angabe für: {liste}",
        {"fields": liste},
    )


def invalid_json_body() -> AppError:
    """Kaputtes JSON bekommt einen eigenen Wortlaut (Nacharbeit 1 zu #85,
    KLEIN).

    Pydantic meldet einen kaputten Anfrage-Koerper als `type: "json_invalid"`
    mit `loc: ("body", <Byte-Position>)` — eine ZAHL, kein Feldname. Lief das
    durch `validation_failed()` (der generische Pfad), lautete `detail`
    "Ungültige oder unbekannte Angabe für: 15" — eine Byte-Position, die
    niemand als Feldname liest. `main._validation_error_handler` erkennt
    `json_invalid` VOR dem generischen Pfad und ruft stattdessen hier an.
    """
    return AppError(422, "err_invalid_json_body", "Anfrage ist kein gültiges JSON")


# Bekannte Texte EIGENER Validatoren (`ValueError` mit fest formuliertem
# deutschem/englischem Text, geworfen von `models/account.py`), zugeordnet
# auf eine eigene, uebersetzbare Meldung (Nacharbeit 1 zu #85, KLEIN:
# "Fehlergrund eigener Validatoren geht verloren"). Ohne diese Zuordnung lief
# ein `ValueError` aus einem `field_validator` durch denselben generischen
# Pfad wie jeder andere Validierungsfehler — der eigentliche GRUND (welche
# Regel genau verletzt wurde) ging verloren, `detail` nannte nur noch den
# Feldnamen ("Ungültige oder unbekannte Angabe für: immich_url"). Die
# Zuordnung ist bewusst ueber den TEXT der Ausnahme, nicht ueber eine eigene
# Ausnahmeklasse: `field_validator` erwartet `ValueError`/`AssertionError`/
# `PydanticCustomError`, keine `AppError` (die ist eine `HTTPException` und
# wuerde im Pydantic-Validierungslauf nicht sauber behandelt). Nur die ZWEI
# im Bau-Brief gemessenen Faelle sind hier abgedeckt — ein dritter eigener
# Validator braucht einen eigenen Eintrag, sonst faellt sein Grund weiterhin
# auf den generischen Pfad zurueck (kein Absturz, nur wieder der alte
# Zustand fuer diesen EINEN Fall).
def credentials_in_url() -> AppError:
    return AppError(
        422, "err_credentials_in_url",
        "Zugangsdaten sind in der Immich-URL nicht erlaubt",
    )


def disallowed_network_address() -> AppError:
    return AppError(422, "err_disallowed_network_address", "Diese Netzadresse ist nicht erlaubt")


EIGENE_VALIDATOR_GRUENDE: dict[str, Callable[[], AppError]] = {
    "Credentials are not allowed inside the Immich URL": credentials_in_url,
    "This network address is not allowed": disallowed_network_address,
}


def duplicate_query_param(name: str) -> AppError:
    """Derselbe Query-Parameter kam mehrfach (#85 Punkt 5).

    `?album_name=A&album_name=B` liess bisher still EINEN der beiden Werte
    gewinnen — welchen, ist eine Eigenschaft der Bibliothek, keine Zusage
    dieser Schnittstelle. Vorschau und das anschliessende POST konnten so
    unbemerkt auf verschiedene Namen auflaufen. `name` ist hier immer ein
    Parametername aus unserem eigenen Schema, kein Client-Freitext — die
    Kappung laeuft trotzdem mit, aus demselben Grund wie bei jeder anderen
    Meldung mit Wert: eine Ausnahme waere eine zweite Regel, die man sich
    merken muesste.
    """
    gekuerzt = _gekuerzt(name)
    return AppError(
        422,
        "err_duplicate_query_param",
        f"Parameter '{gekuerzt}' darf nicht mehrfach angegeben werden",
        {"name": gekuerzt},
    )
