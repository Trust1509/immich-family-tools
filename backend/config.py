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

    class Config:
        env_prefix = "IMMICH_FAMILY_TOOLS_"
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
