# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:22-alpine AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build
# Output is at /build/frontend/dist


# ── Stage 2: Python backend + static files ───────────────────────────────────
FROM python:3.12-slim

# Timezone support + non-root user matching TrueNAS convention
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && \
    rm -rf /var/lib/apt/lists/*
RUN groupadd -g 3006 appgroup && \
    useradd -u 3006 -g 3006 -s /bin/sh -M appuser

WORKDIR /app

# Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend source
COPY backend/ ./

# Frontend build output → served as static files by FastAPI
COPY --from=frontend-builder /build/frontend/dist ./static/

# Volume mount point for config persistence
RUN mkdir -p /app/data && chown -R appuser:appgroup /app

# #68 NACHARBEIT 1: der Commit, aus dem dieses Abbild gebaut wird — `docker
# build --build-arg GIT_SHA=$(git rev-parse HEAD)`. Fehlt das Argument,
# bleibt es beim Vorgabewert "unknown"; `/api/health` gibt genau das aus, und
# die App startet trotzdem (backend/config.py, backend/main.py). BEWUSST GANZ
# AM ENDE, NACH `apt-get`/`pip install`/den `COPY`-Schichten — vorher stand
# dieser Block VOR ihnen: `ARG`/`ENV` aendern ihren Wert bei JEDEM Commit (der
# SHA ist ja der Commit), und Docker verwirft den Layer-Cache ab der ERSTEN
# Schicht, deren Instruktion sich geaendert hat, UND ALLEN danach — auch wenn
# deren eigener Inhalt (Paketliste, `requirements.txt`) gleich blieb. Jeder
# neue Commit baute dadurch `apt-get` UND `pip install` komplett neu, mit
# vollem Netzbedarf (gemessen: mit `ARG` vor `apt-get` bleibt dessen Schicht
# bei einem SHA-Wechsel nicht `CACHED`; mit `ARG` hier am Ende, nach der
# teuren Schicht, bleibt sie es). Das ist der
# Unterschied zwischen einem Rollout, der ohne Netz klappt, und einem, der
# genau dann scheitert, wenn man es am wenigsten brauchen kann.
ARG GIT_SHA=unknown
ENV IMMICH_FAMILY_TOOLS_GIT_SHA=${GIT_SHA}

USER appuser

EXPOSE 3100

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3100", "--workers", "1"]
