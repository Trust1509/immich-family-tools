import asyncio
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import get_settings
from services.config_store import ConfigStore
from services.immich_client import ImmichClient
from services.thumbnail_cache import ThumbnailCache
from routers import accounts, people, faces, albums

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="Immich Family Tools",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# Simple bearer token guard (optional – only enforced when secret ≠ default)
# ------------------------------------------------------------------
UNPROTECTED = {"/api/health", "/api/docs", "/api/redoc", "/api/openapi.json"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if settings.secret == "changeme":
        return await call_next(request)
    if request.url.path in UNPROTECTED or not request.url.path.startswith("/api/"):
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {settings.secret}":
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


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
    """Check every 60 s whether it is time to run the nightly auto-sync."""
    last_run_date = None
    while True:
        await asyncio.sleep(60)
        try:
            cfg = app_state.store.get_auto_sync_config()
            if not cfg.get("enabled"):
                continue
            now = datetime.now()
            raw_time = cfg.get("time", "01:00")
            h, m = map(int, raw_time.split(":"))
            if now.hour == h and now.minute == m and now.date() != last_run_date:
                last_run_date = now.date()
                logger.info("Auto-sync triggered at %s", raw_time)
                await _run_auto_sync(app_state)
        except Exception as exc:
            logger.error("Auto-sync loop error: %s", exc)


async def _backfill_user_ids(store: ConfigStore) -> None:
    """Fetch and store missing user_ids for accounts added before this feature."""
    for account in store.list_accounts():
        if account.user_id:
            continue
        try:
            client = ImmichClient(account.immich_url, account.api_key)
            user_info = await client.validate()
            user_id = user_info.get("id")
            if user_id:
                raw = store._data["accounts"].get(account.id)
                if raw:
                    raw["user_id"] = user_id
                    store._save()
                    logger.info("Backfilled user_id for account '%s'", account.name)
        except Exception as exc:
            logger.warning("Could not backfill user_id for '%s': %s", account.name, exc)


@app.on_event("startup")
async def startup():
    app.state.settings = settings
    app.state.store = ConfigStore(settings.config_path)
    app.state.thumbnail_cache = ThumbnailCache(settings.thumbnail_cache_max_bytes)
    logger.info("Immich Family Tools started on port %d", settings.port)
    # Backfill user_ids for accounts added before this feature (runs in background)
    asyncio.create_task(_backfill_user_ids(app.state.store))
    asyncio.create_task(_auto_sync_loop(app.state))


# ------------------------------------------------------------------
# Routers
# ------------------------------------------------------------------

app.include_router(accounts.router)
app.include_router(people.router)
app.include_router(faces.router)
app.include_router(albums.router)


@app.get("/api/health")
async def health():
    store = app.state.store
    cache = app.state.thumbnail_cache
    return {
        "status": "ok",
        "accounts": len(store.list_accounts()),
        "thumbnail_cache_entries": cache.entry_count,
        "thumbnail_cache_bytes": cache.size_bytes,
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
