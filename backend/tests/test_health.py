"""#68: `/api/health` meldet zusaetzlich den Build-Commit (`GIT_SHA`).

Fehlt das Docker-Build-Argument, bleibt `commit` beim Vorgabewert "unknown"
und die App startet trotzdem — beides wird hier ueber die ECHTE HTTP-Tuer
geprueft (`main.app.router.lifespan_context`), nicht nur an der Funktion
`health()` direkt, weil das die Stelle ist, die der Produktivpfad wirklich
nimmt (Startroutine + Router)."""
import httpx
import pytest

import main


@pytest.mark.asyncio
async def test_health_meldet_gesetzten_commit(tmp_path, monkeypatch):
    monkeypatch.setattr(main.settings, "secret", "health-test-geheim", raising=False)
    monkeypatch.setattr(main.settings, "config_path", str(tmp_path / "accounts.json"), raising=False)
    monkeypatch.setattr(main.settings, "git_sha", "abc123def456", raising=False)

    async with main.app.router.lifespan_context(main.app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://t"
        ) as c:
            r = await c.get("/api/health")

    assert r.status_code == 200
    body = r.json()
    assert body == {"status": "ok", "version": main.APP_VERSION, "commit": "abc123def456"}


@pytest.mark.asyncio
async def test_health_ohne_git_sha_meldet_unknown_und_die_app_startet(tmp_path, monkeypatch):
    monkeypatch.setattr(main.settings, "secret", "health-test-geheim", raising=False)
    monkeypatch.setattr(main.settings, "config_path", str(tmp_path / "accounts.json"), raising=False)
    # git_sha bewusst auf den dokumentierten Vorgabewert gesetzt statt dem
    # Zufall der Umgebung ueberlassen: fehlt das Docker-Build-Argument, steht
    # in `backend/config.py` genau dieser Wert.
    monkeypatch.setattr(main.settings, "git_sha", "unknown", raising=False)

    async with main.app.router.lifespan_context(main.app):  # darf nicht werfen
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://t"
        ) as c:
            r = await c.get("/api/health")

    assert r.status_code == 200
    assert r.json()["commit"] == "unknown"


def test_health_ist_ohne_login_erreichbar():
    """Der Uptime-Kuma-Waechter (`docs/betrieb/erreichbarkeit.md`) und der
    Rueckstands-Check rufen `/api/health` ohne Session auf — die Route muss
    in der Ausnahmeliste der Auth-Middleware bleiben."""
    assert "/api/health" in main.UNPROTECTED
