import asyncio
import logging
import hmac
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import get_settings
from services.config_store import ConfigStore
from services.immich_client import ClientPool
from services.match_cache import MatchCache
from services.thumbnail_cache import ThumbnailCache
from routers import accounts, people, faces, albums, auth
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


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > settings.max_request_bytes:
                    from fastapi.responses import JSONResponse
                    return JSONResponse(status_code=413, content={"detail": "Request body too large"})
            except ValueError:
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length"})
    if request.url.path not in UNPROTECTED and request.url.path.startswith("/api/"):
        bearer = request.headers.get("Authorization", "")
        bearer_ok = bearer.startswith("Bearer ") and hmac.compare_digest(
            bearer.removeprefix("Bearer "), settings.secret
        )
        cookie_ok = verify_session(request.cookies.get("ift_session"), settings.secret)
        if not (bearer_ok or cookie_ok):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
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
    """Refresh all managed albums — called by the auto-sync background task."""
    from services.sync_service import refresh_managed_album
    store = app_state.store
    albums = store.get_managed_albums()
    all_accounts = store.list_accounts()
    logger.info("Auto-sync: refreshing %d managed albums", len(albums))
    for album in albums:
        try:
            logs = await refresh_managed_album(album, all_accounts, store)
            store.append_log(logs)
            logger.info("Auto-sync: album '%s' done (%d log entries)", album.album_name, len(logs))
        except Exception as exc:
            logger.error("Auto-sync: album '%s' failed: %s", album.album_name, exc)


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
    return {
        "status": "ok",
        "version": APP_VERSION,
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
