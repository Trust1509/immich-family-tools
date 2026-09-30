import asyncio
import logging
import hmac
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from config import get_settings
from services.config_store import ConfigStore
from services.immich_client import ClientPool
from services.match_cache import MatchCache
from services.thumbnail_cache import ThumbnailCache
from routers import accounts, people, faces, albums, auth
import errors
from services.auth_service import verify_session
from version import APP_VERSION

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="Immich Family Tools",
    version=APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ------------------------------------------------------------------
# Single-secret session guard
# ------------------------------------------------------------------
UNPROTECTED = {"/api/health", "/api/auth/login"}


def _fehler_antwort(fehler: errors.AppError) -> JSONResponse:
    """Die Antwortform fuer Wege, die keine Ausnahme werfen koennen.

    Die Middleware laeuft VOR jedem Router und vor dem Exception-Handler; sie
    baut ihre Antworten selbst. Beide Wege holen die Form aus errors.antwort(),
    damit nicht einer von beiden still beim alten Format bleibt.
    """
    return JSONResponse(status_code=fehler.status_code, content=errors.antwort(fehler))


@app.exception_handler(errors.AppError)
async def _app_error_handler(request: Request, fehler: errors.AppError) -> JSONResponse:
    """Haengt Schluessel und Werte neben den deutschen Klartext.

    `detail` bleibt eine Zeichenkette und bleibt deutsch — wer die
    Schnittstelle direkt anspricht, merkt von der Aenderung nichts, und ein
    Frontend, das den Schluessel nicht kennt, hat trotzdem etwas anzuzeigen.
    """
    return _fehler_antwort(fehler)


def _feldnamen_aus_validierungsfehlern(exc: RequestValidationError) -> list[str]:
    """Ein lesbarer Feldname je Fehler aus `exc.errors()`.

    `loc` ist ein Tupel wie `("body", "group_id")` oder, bei einem
    abgelehnten Zusatzfeld unter `extra="forbid"`, `("body", "groupId")` —
    das erste Glied nennt nur die Quelle (Koerper/Query/Pfad), kein Feld.
    Ein verschachteltes Modell (z. B. `SyncNamesMultiRequest.persons`) liefert
    mehr als zwei Glieder; die werden mit "." verbunden, damit der Pfad
    lesbar bleibt, statt nur das letzte (moeglicherweise mehrdeutige) Glied
    zu nennen.
    """
    namen = []
    for fehler in exc.errors():
        loc = tuple(fehler.get("loc", ()))
        rest = loc[1:] if len(loc) > 1 else loc
        namen.append(".".join(str(teil) for teil in rest) or "?")
    return namen


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """FastAPIs eigener Validierungsfehler in Hausform (#85 Punkt 1).

    FastAPI wirft `RequestValidationError` fuer jeden fehlerhaften
    Request-Koerper oder -Query-Parameter, BEVOR ein Router laeuft — das ist
    keine `errors.AppError` und lief am Handler oben vorbei. Ohne diesen
    Handler antwortete dieser Pfad mit FastAPIs eigener Form (`detail` als
    LISTE, kein `error_key`), obwohl diese Datei zusagt: `detail` bleibt eine
    Zeichenkette. Trifft JEDEN Validierungsfehler, nicht nur die neuen Felder
    aus #85 — auch ein abgelehntes Zusatzfeld (`extra="forbid"`, Punkt 2)
    laeuft hier durch, weil Pydantic es als denselben Fehlertyp meldet.

    NEU (Nacharbeit 1 zu #85, KLEIN): Zwei Sonderfaelle werden VOR dem
    generischen Pfad erkannt, weil `errors.validation_failed()` fuer beide
    die falsche Antwort waere:

      - `json_invalid` (kaputtes JSON): `loc` ist dort `("body", <Byte-
        Position>)` — eine ZAHL, kein Feldname. Der generische Pfad zeigte
        vorher "Ungültige oder unbekannte Angabe für: 15".
      - GENAU EIN `value_error` mit einem BEKANNTEN Text aus einem eigenen
        `field_validator` (`models/account.py`): Der generische Pfad kennt
        nur den FELDNAMEN, nicht den GRUND — "Zugangsdaten in der URL" und
        "nicht erlaubte Netzadresse" sahen beide gleich aus ("Ungültige oder
        unbekannte Angabe für: immich_url"). `errors.EIGENE_VALIDATOR_GRUENDE`
        bildet den bekannten `ValueError`-Text auf eine eigene, uebersetzbare
        Meldung ab. Bei MEHR als einem Fehler oder einem unbekannten Text
        faellt das auf den generischen Pfad zurueck — kein Absturz, nur der
        Grund bleibt dann (wie vorher) auf den Feldnamen begrenzt.

    Beide Sonderfaelle bleiben — wie jede andere Meldung — mehrsprachig
    (`frontend/src/i18n.tsx`), keine deutsche Klartext-Ausnahme.
    """
    rohe_fehler = exc.errors()
    if any(f.get("type") == "json_invalid" for f in rohe_fehler):
        return _fehler_antwort(errors.invalid_json_body())
    if len(rohe_fehler) == 1 and rohe_fehler[0].get("type") == "value_error":
        grund = str((rohe_fehler[0].get("ctx") or {}).get("error", ""))
        fabrik = errors.EIGENE_VALIDATOR_GRUENDE.get(grund)
        if fabrik is not None:
            return _fehler_antwort(fabrik())
    fehler = errors.validation_failed(_feldnamen_aus_validierungsfehlern(exc))
    return _fehler_antwort(fehler)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.max_request_bytes:
                    return _fehler_antwort(errors.request_too_large())
            except ValueError:
                return _fehler_antwort(errors.invalid_content_length())
        else:
            # Nacharbeit 1 zu #85, Punkt 3, zweiter Teil: OHNE
            # Content-Length-Header (z. B. chunked transfer encoding) kam
            # die Pruefung oben nie zum Zug — FastAPI liest den Koerper
            # trotzdem vollstaendig ein, bevor irgendein Router ihn sieht.
            # Gemessen (Gegenpruefer #85, vorbestehend): ein 1,25-MB-Koerper
            # ohne Content-Length kam vollstaendig durch, obwohl
            # `settings.max_request_bytes` bei 1 MiB liegt. Der Koerper wird
            # deshalb hier selbst, bytesweise eingelesen und SOFORT
            # abgebrochen, sobald er das Limit ueberschreitet.
            #
            # `request._body` danach zu setzen ist KEIN Seiteneffekt auf
            # fremdes Verhalten, sondern der Weg, den Starlettes eigene
            # `_CachedRequest` (`starlette/middleware/base.py`) fuer genau
            # diesen Fall vorsieht: `wrapped_receive()` prueft zuerst dieses
            # Attribut und spiegelt seinen Inhalt an den naechsten Leser
            # weiter (Router/Pydantic), STATT den (hier schon verbrauchten)
            # rohen ASGI-Stream erneut zu lesen — sonst saehe der Router
            # einen leeren Koerper. Das ist derselbe Mechanismus, den
            # `Request.body()` selbst benutzt, nur mit einer Groessengrenze
            # WAEHREND des Lesens statt danach.
            gelesen = 0
            teile: list[bytes] = []
            async for teil in request.stream():
                gelesen += len(teil)
                if gelesen > settings.max_request_bytes:
                    return _fehler_antwort(errors.request_too_large())
                teile.append(teil)
            request._body = b"".join(teile)
    if request.url.path not in UNPROTECTED and request.url.path.startswith("/api/"):
        bearer = request.headers.get("Authorization", "")
        bearer_ok = bearer.startswith("Bearer ") and hmac.compare_digest(
            bearer.removeprefix("Bearer "), settings.secret
        )
        cookie_ok = verify_session(request.cookies.get("ift_session"), settings.secret)
        if not (bearer_ok or cookie_ok):
            return _fehler_antwort(errors.unauthorized())
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
        "font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ------------------------------------------------------------------
# App state
# ------------------------------------------------------------------

async def _run_auto_sync(app_state) -> None:
    """Refresh all managed albums — called by the auto-sync background task.

    Alben ohne lebenden Besitzer werden UEBERSPRUNGEN statt abgeglichen
    (Owner-Entscheid 28.09.2026, #99): Ohne Besitzerkonto liefert der
    Abgleich ohnehin nur `log_owner_account_missing` — jede Nacht, fuer
    dasselbe Album, bis das Album aus der Verwaltung entfernt wird. EIN NEU
    ANGELEGTES KONTO HEILT DAS NICHT: `Account.from_create` vergibt jedem
    Konto eine frische, zufaellige Kennung (`uuid.uuid4()`), auch fuer
    dieselbe Immich-Instanz mit denselben Zugangsdaten — sie trifft nie
    wieder auf das `owner_account_id` des alten Albums. Ein wiederkehrendes,
    bekanntes Fehlersignal verdeckt echte Funde (`docs/agents/lehren.md`
    §45); die Oberflaeche markiert diese Alben bereits (`GET
    /api/sync/albums`).

    Der manuelle Weg ueber `POST /api/sync/album/{id}/refresh` selbst laeuft
    weiterhin unveraendert ueber `sync_service.refresh_managed_album` und
    meldet den Grund. Die BEIDEN Knoepfe in der Albumuebersicht
    ("Jetzt synchronisieren" je Gruppe, "Alle synchronisieren"), die diesen
    Weg aufrufen, ueberspringen verwaiste Alben seit Nacharbeit 1 zu #99/#112
    inzwischen ABER SELBST, BEVOR sie den Endpunkt ueberhaupt erreichen
    (`AlbumsOverview.tsx`, `gesundeAlben`) — eine eigene, technische
    Entscheidung des Hauptagenten, nicht Teil dieses Owner-Entscheids und
    nicht Gegenstand dieses Skips hier. Dieser Skip hier betrifft
    ausschliesslich den naechtlichen Auto-Sync.

    PRAEZISIERT (Nacharbeit 1, #117/#121/#103, Fund „KLEIN"): „Verwaiste
    Alben werden uebersprungen" gilt nur fuer Alben, die schon VOR diesem
    Lauf verwaist waren — `lebende_konten` ist eine Momentaufnahme direkt zu
    Beginn dieser Funktion. Ein Album, dessen Besitzer WAEHREND dieses Laufs
    geloescht wird (waehrend ein FRUEHERES Album in der Schleife noch
    abgeglichen wird), steht zu diesem Zeitpunkt noch in `albums` und wird
    ganz normal an `refresh_managed_album` uebergeben — es entsteht dafuer
    GENAU EIN `log_owner_account_missing`-Eintrag fuer diesen Lauf (aus
    `_refresh_managed_album_unlocked`'s eigenem, frischen Besitzer-Check),
    kein taeglich wiederkehrender: Der naechste Lauf sieht das Konto beim
    ERNEUTEN Aufbau von `lebende_konten` schon als tot und ueberspringt das
    Album dann regulaer ueber den Weg oben.
    """
    from services.sync_service import refresh_managed_album
    store = app_state.store
    albums = store.get_managed_albums()
    all_accounts = store.list_accounts()
    lebende_konten = {a.id for a in all_accounts}
    uebersprungen = [a for a in albums if a.owner_account_id not in lebende_konten]
    albums = [a for a in albums if a.owner_account_id in lebende_konten]
    if uebersprungen:
        logger.info(
            "Auto-sync: %d Album/Alben ohne lebendes Besitzerkonto uebersprungen: %s",
            len(uebersprungen), ", ".join(a.id for a in uebersprungen),
        )
    logger.info("Auto-sync: refreshing %d managed albums", len(albums))
    for album in albums:
        try:
            logs = await refresh_managed_album(album, all_accounts, store)
            store.append_log(logs)
            # Die Kennung, nicht der Name: Der Name in dieser Kopie kann alt
            # sein — die Liste wurde EINMAL vor der Schleife gelesen.
            logger.info("Auto-sync: album %s done (%d log entries)", album.id, len(logs))
        except errors.AppError as exc:
            # #121/#103 Punkt 3/4: Vorher `exc.status_code == 404` — das trifft
            # zufaellig auch auf ANDERE Fehlerarten zu, die denselben
            # Statuscode tragen (z. B. `err_owner_account_not_found`), auch
            # wenn `refresh_managed_album` diesen konkreten Weg heute nicht
            # geht. Die Fehlerart entscheidet, nicht der Statuscode: Nur ein
            # zwischendurch entferntes Album ist kein Fehler des Auto-Syncs.
            if exc.key == "err_managed_album_not_found":
                # #101, Nacharbeit 2: Ein Album, das zwischen dem Lesen der
                # Liste und dieser Runde entfernt wurde (`refresh_managed_
                # album` wirft dann `errors.managed_album_not_found()`), ist
                # kein Fehler des Auto-Syncs — es ist genau das, was ein
                # Nutzer wollte. Doppelte Namen sind erlaubt (#98), also die
                # KENNUNG loggen, nicht `album.album_name`.
                logger.info("Auto-sync: album %s removed, skipped", album.id)
            else:
                # Die Kennung, nicht der (womoeglich veraltete) Name aus der
                # Kopie von vor der Schleife — dieselbe Begruendung wie oben,
                # bisher aber nur fuer die Erfolgszeile umgesetzt (#121 Punkt
                # 3, #103 Punkt 4).
                logger.error("Auto-sync: album '%s' failed: %s", album.id, exc)
        except Exception as exc:
            logger.error("Auto-sync: album '%s' failed: %s", album.id, exc)


async def _auto_sync_loop(app_state) -> None:
    """Check every 30 s if it is time to run the nightly auto-sync.
    Fires exactly once per configured local-time slot."""
    last_run_slot = None
    while True:
        await asyncio.sleep(30)
        try:
            cfg = app_state.store.get_auto_sync_config()
            if not cfg.get("enabled"):
                continue
            now = datetime.now()
            h, m = map(int, cfg.get("time", "01:00").split(":"))
            current_slot = (now.date(), h, m)
            if now.hour == h and now.minute == m and current_slot != last_run_slot:
                last_run_slot = current_slot
                logger.info("Auto-sync triggered at %02d:%02d", h, m)
                await _run_auto_sync(app_state)
        except Exception as exc:
            logger.error("Auto-sync loop error: %s", exc)


async def _backfill_user_ids(store: ConfigStore, pool: ClientPool) -> None:
    """Fetch and store missing user_ids for accounts added before this feature."""
    for account in store.list_accounts():
        if account.user_id:
            continue
        try:
            client = pool.get_for_account(account)
            user_info = await client.validate()
            user_id = user_info.get("id")
            if user_id:
                store.update_account(account.id, {"user_id": user_id})
                logger.info("Backfilled user_id for account '%s'", account.name)
        except Exception as exc:
            logger.warning("Could not backfill user_id for '%s': %s", account.name, exc)


@app.on_event("startup")
async def startup():
    if settings.secret == "changeme" and not settings.allow_insecure_no_auth:
        raise RuntimeError(
            "IMMICH_FAMILY_TOOLS_SECRET must be changed. "
            "Set IMMICH_FAMILY_TOOLS_ALLOW_INSECURE_NO_AUTH=true only for isolated development."
        )
    app.state.settings = settings
    app.state.store = ConfigStore(settings.config_path, settings.log_retention_days)
    app.state.thumbnail_cache = ThumbnailCache(settings.thumbnail_cache_max_bytes)
    app.state.client_pool = ClientPool()
    app.state.match_cache = MatchCache()
    logger.info("Immich Family Tools started on port %d", settings.port)
    # Backfill user_ids for accounts added before this feature (runs in background)
    asyncio.create_task(_backfill_user_ids(app.state.store, app.state.client_pool))
    asyncio.create_task(_auto_sync_loop(app.state))
    # Genau EIN verzoegerter zweiter Aufraeumdurchlauf fuer liegengebliebene
    # Temp-Dateien (siehe `ConfigStore.zweiter_aufraeum_durchlauf`): Der
    # Start-Scan meldet einen zu jungen Rest nur, entfernt ihn aber nicht —
    # dieser Durchlauf holt genau den Fall spaeter, in DERSELBEN laufenden
    # Instanz, statt auf den naechsten vollen Neustart zu warten. Referenz auf
    # `app.state`, damit `shutdown` unten die Aufgabe sauber abbrechen kann.
    app.state.zweiter_aufraeum_task = asyncio.create_task(
        app.state.store.zweiter_aufraeum_durchlauf()
    )


@app.on_event("shutdown")
async def shutdown():
    # Sauberer Abbruch des zweiten Aufraeumdurchlaufs (siehe `startup` oben):
    # Ein Fehler oder eine haengende Aufgabe hier darf das Herunterfahren
    # nicht verzoegern oder mit einer Ausnahme quittieren — `CancelledError`
    # aus dem `await` ist der ERWARTETE, nicht der Fehler-Fall.
    task = getattr(app.state, "zweiter_aufraeum_task", None)
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ------------------------------------------------------------------
# Routers
# ------------------------------------------------------------------

app.include_router(accounts.router)
app.include_router(people.router)
app.include_router(faces.router)
app.include_router(albums.router)
app.include_router(auth.router)


@app.get("/api/health")
async def health():
    # #68: `commit` schliesst die Luecke, die `version` allein laesst — ein
    # Commit NACH dem Tag ohne Versionsbump meldet weiterhin die alte,
    # getaggte Nummer. Der Rueckstands-Check kann so Commit gegen Commit
    # vergleichen statt Version gegen Version (docs/betrieb/erreichbarkeit.md).
    # `settings.git_sha` bleibt "unknown", wenn das Docker-Build-Argument
    # `GIT_SHA` fehlte — kein Absturz, keine erfundene Zahl.
    return {
        "status": "ok",
        "version": APP_VERSION,
        "commit": settings.git_sha,
    }


# ------------------------------------------------------------------
# Serve React SPA (must be last)
# ------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = STATIC_DIR / "index.html"
        return FileResponse(str(index))
else:
    logger.warning("Static frontend directory not found at %s – frontend not served", STATIC_DIR)
