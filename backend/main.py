import asyncio
import logging
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
