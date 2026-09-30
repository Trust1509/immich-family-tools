from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    port: int = 3100
    secret: str = "changeme"
    config_path: str = "/app/data/accounts.json"
    log_level: str = "info"
    # In-memory thumbnail cache ceiling in bytes (default 50 MB)
    thumbnail_cache_max_bytes: int = 50 * 1024 * 1024
    # Match cache TTL in seconds
    match_cache_ttl: int = 300
    session_ttl_hours: int = 168
    cookie_secure: bool = False
    allow_insecure_no_auth: bool = False
    log_retention_days: int = 90
    max_request_bytes: int = 1024 * 1024
    # #68: der Commit, aus dem das laufende Abbild gebaut wurde — gesetzt vom
    # Dockerfile (`ARG GIT_SHA` -> `ENV IMMICH_FAMILY_TOOLS_GIT_SHA`) beim
    # `docker build --build-arg GIT_SHA=<sha>`. Fehlt das Argument (lokaler
    # Lauf ohne Docker, alter Baubefehl ohne das Argument), bleibt es beim
    # Vorgabewert — die App startet trotzdem, `/api/health` zeigt dann
    # ehrlich "unknown" statt eine falsche Zahl zu erfinden.
    git_sha: str = "unknown"

    class Config:
        env_prefix = "IMMICH_FAMILY_TOOLS_"
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
