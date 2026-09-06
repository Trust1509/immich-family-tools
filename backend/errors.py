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

  - Wer die Schnittstelle direkt anspricht, merkt von der Aenderung nichts.
    Ein Objekt unter `detail` waere eine echte Bruchstelle gewesen.
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

from typing import Any, Optional

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
        400, "err_album_name_required", "album_name erforderlich für neues Album"
    )


def album_already_managed() -> AppError:
    return AppError(
        409,
        "err_album_already_managed",
        "Für diese manuelle Zuordnung existiert bereits ein verwaltetes Album",
    )


def min_two_people() -> AppError:
    return AppError(400, "err_min_two_people", "Mindestens 2 Personen erforderlich")


def not_undoable() -> AppError:
    return AppError(
        409, "err_not_undoable", "Aktion kann nicht rückgängig gemacht werden"
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
        400, "err_invalid_time_format", "Invalid time format. Use HH:MM (e.g. 01:00)"
    )


def unsupported_immich_version(major: object, minor: object) -> AppError:
    return AppError(
        422,
        "err_unsupported_immich_version",
        f"Immich-Version {major}.{minor} wird nicht unterstützt — dieses Tool "
        "benötigt Immich v3.x (Server meldet Version über /api/server/version).",
        {"major": str(major), "minor": str(minor)},
    )


# ── Meldungen mit Werten ───────────────────────────────────────────────────
#
# Die Werte kommen aus den Daten des Nutzers (Account-Namen, Album-Namen,
# IDs) und gehen an genau den Nutzer zurueck, dem sie gehoeren. Das ist in
# Ordnung — aber `params` darf deshalb NICHT unbesehen in ein Log oder eine
# Fehlersammlung wandern. Wer das je einbaut, entscheidet das bewusst.


def account_id_not_found(account_id: str) -> AppError:
    return AppError(
        404,
        "err_account_id_not_found",
        f"Account {account_id} nicht gefunden",
        {"id": str(account_id)},
    )


def owner_account_id_not_found(owner_id: str) -> AppError:
    return AppError(
        404,
        "err_owner_account_id_not_found",
        f"Owner-Account {owner_id} nicht gefunden",
        {"id": str(owner_id)},
    )


def person_validation_failed(account_name: str) -> AppError:
    return AppError(
        422,
        "err_person_validation_failed",
        f"Person in Account '{account_name}' konnte nicht validiert werden",
        {"account": str(account_name)},
    )


def match_album_exists(album_name: str) -> AppError:
    return AppError(
        409,
        "err_match_album_exists",
        f"Für diesen Match existiert bereits ein verwaltetes Album: '{album_name}'.",
        {"album": str(album_name)},
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
