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

USER appuser

EXPOSE 3100

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3100", "--workers", "1"]
