from pydantic import field_validator
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

    # NACHARBEIT 1 zu #68 (H1, Mutationsluecke): `docker build --build-arg
    # GIT_SHA=` OHNE Wert (Direktbau ohne die Owner-Freigabe-Zeile aus dem
    # Release-Ritual) setzt das Docker-`ARG` auf eine LEERE Zeichenkette,
    # nicht auf "unknown" — `ENV IMMICH_FAMILY_TOOLS_GIT_SHA=` wird dann
    # ebenfalls leer, und `pydantic-settings` behandelt eine GESETZTE, aber
    # leere Umgebungsvariable als Wert (nicht als "fehlt") und liefert `""`
    # statt des Vorgabewerts. `/api/health` haette dann `"commit":""`
    # ausgegeben statt ehrlich `"unknown"` zu sagen (gemessen: ohne diesen
    # Validator liefert `Settings(git_sha="")` `git_sha == ""`). `mode="before"`
    # laeuft VOR der Typpruefung, damit eine leere Zeichenkette denselben Weg
    # nimmt wie ein ganz fehlender Wert.
    #
    # NACHARBEIT 2 (KLEIN): `.strip()` VOR dem Leer-Vergleich, nicht nur
    # `wert == ""` — eine Umgebungsvariable, die nur aus Leerraum besteht
    # (`IMMICH_FAMILY_TOOLS_GIT_SHA=" "`, z. B. durch ein Shell-Quoting-
    # Versehen im Baubefehl), bestand den blossen Gleichheitsvergleich nicht
    # und lief ungeprueft durch — `/api/health` haette `"commit":" "`
    # ausgegeben, kein Absturz, aber auch keine ehrliche Aussage. Nur bei
    # einem String ueberhaupt geprueft: ein Nicht-String (z. B. ein versehentlich
    # als Zahl gesetzter Wert) faellt der Typpruefung DANACH zu, nicht dieser
    # Stelle.
    @field_validator("git_sha", mode="before")
    @classmethod
    def _leerer_git_sha_wird_unknown(cls, wert: object) -> object:
        if isinstance(wert, str) and wert.strip() == "":
            return "unknown"
        return wert

    class Config:
        env_prefix = "IMMICH_FAMILY_TOOLS_"
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
