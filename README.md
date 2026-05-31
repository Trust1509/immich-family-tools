# Immich Family Tools

> A companion web app for self-hosted [Immich](https://immich.app) instances with multiple user accounts — solving the missing cross-account face recognition problem via the Immich REST API, without touching your existing Immich installation.

## The Problem

Immich does not share face recognition across user accounts. If your family runs 4 separate Immich accounts on the same server, each account builds its own independent person database — even though 90% of the faces are the same people.

This tool bridges that gap.

## Features

- **People overview** — All recognized faces from all accounts in one unified view
- **Match suggestions** — Automatically detects the same person across accounts using name similarity, face embeddings (if available via API), and shared assets
- **Name sync** — Set a canonical name on both persons with one click
- **Shared album** — Create an album containing all photos of a matched person
- **Sync log** — Full history of all actions with undo support
- **Read-first design** — All write operations require explicit confirmation; nothing happens automatically

## Screenshots

> _Add screenshots here once the UI is stable_

## How It Works

```
Immich Account A:  "Leonie" (own face DB)
Immich Account B:  "Leonie" (own face DB)
                        ↕
              Immich Family Tools detects:
              "Same person — 87% confidence"
                        ↕
         Actions: sync name · create shared album
         → Both face DBs remain untouched
```

**Match confidence** is calculated from up to three signals:

| Signal | Weight (with embeddings) | Weight (without) |
|---|---|---|
| Face embedding cosine similarity | 60% | — |
| Name similarity (Levenshtein distance) | 30% | 75% |
| Shared asset IDs | 10% | 25% |

When embeddings are unavailable, the remaining weights are scaled up to 100%.

#### Signal details

**Name similarity** uses Levenshtein distance normalized to 0–1:
- `"Leonie"` vs `"Leonie"` → 100%
- `"Manuel"` vs `"Manu"` → 67%
- Any unnamed person → 0% (no signal)

**Face embeddings** are fetched via `GET /api/faces?id={assetId}` — experimental, not available in all Immich versions. Cosine similarity of ~0.9+ indicates the same person. Falls back gracefully to name-only matching.

**Shared assets** — if the same physical photo was imported into multiple accounts, the asset IDs will differ (Immich assigns new UUIDs per import), so this signal rarely fires in practice. It is reserved for future use (e.g. partner library sync).

#### Why does "same name" only score ~75%?

Name similarity alone contributes at most 75% of the total score (without embeddings). The remaining 25% comes from shared assets — which are almost always 0 across separate accounts, even for identical photos. This means:

- Same name, no embeddings → **~75%** (correct match likely, but unconfirmed)
- Same name, embeddings match → **~85–95%** (high confidence)
- Same name, different person → **~75%** → mark as *"Not the same person"* to dismiss permanently

The minimum threshold to appear as a suggestion is **25%**.

## Quick Start

### Prerequisites

- Docker + Docker Compose
- A running Immich instance
- API keys for each Immich account (User Settings → API Keys in Immich)

### 1. Clone

```bash
git clone https://github.com/YOUR_USERNAME/immich-family-tools.git
cd immich-family-tools
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env if you want to set a bearer token secret
# Leave as "changeme" for internal-only deployments (auth guard disabled)
```

### 3. Start

```bash
docker compose up -d --build
```

Open **http://localhost:3100** and add your Immich accounts.

## TrueNAS Scale Deployment

If you run Immich on TrueNAS Scale, ZFS volumes require POSIX ACLs. Run this **before** the first `docker compose up`:

```bash
# Create POSIX datasets (never mount Docker volumes directly on NFSv4 datasets)
zfs create -o acltype=posix -o xattr=sa HDDs/Applications/immich-family-tools
zfs create -o acltype=posix -o xattr=sa HDDs/Applications/immich-family-tools/data

# Set ownership for container user (UID/GID 3006)
chown -R 3006:3006 /mnt/HDDs/Applications/immich-family-tools/data
```

The `docker-compose.yml` is pre-configured for this layout.

## API Key Permissions

When creating API keys in Immich, only these permissions are required:

| Permission | Purpose |
|---|---|
| `user.read` | Validate API key on add |
| `person.read` | Load people + thumbnails |
| `person.update` | Rename person (name sync) |
| `asset.read` | Load person's photos |
| `asset.view` | Fetch thumbnail bytes |
| `face.read` | Face embeddings (optional) |
| `album.read` | Check for existing albums |
| `album.create` | Create shared album |
| `albumAsset.create` | Add photos to album |

## Architecture

Single-container deployment (multi-stage Docker build):

```
immich-family-tools/
├── Dockerfile              # Stage 1: Node/Vite build · Stage 2: Python runtime
├── docker-compose.yml
├── backend/                # FastAPI (Python 3.12)
│   ├── main.py             # Entry point, static file serving
│   ├── config.py           # ENV settings (pydantic-settings)
│   ├── routers/
│   │   ├── accounts.py     # CRUD + live status check
│   │   ├── people.py       # Aggregated people + thumbnail proxy
│   │   ├── faces.py        # Match computation + 5-min cache
│   │   └── albums.py       # Sync actions + log + undo
│   └── services/
│       ├── immich_client.py   # Async Immich REST client (httpx)
│       ├── face_matcher.py    # Cosine similarity + Levenshtein
│       ├── sync_service.py    # Name/album sync
│       ├── config_store.py    # JSON persistence (accounts.json)
│       └── thumbnail_cache.py # LRU in-memory cache (50 MB)
└── frontend/               # React 18 + TypeScript + Tailwind (dark mode)
    └── src/
        ├── components/
        │   ├── AccountManager.tsx   # Page 1: manage accounts
        │   ├── PeopleGrid.tsx       # Page 2: unified people view
        │   ├── MatchSuggestions.tsx # Page 3: match + sync actions
        │   └── SyncPanel.tsx        # Page 4: sync log + undo
        └── api/client.ts            # Typed API client
```

**No database required** — all data is loaded live from the Immich API. Only `accounts.json` (API keys + dismissed matches + sync log) is persisted on the Docker volume.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `IMMICH_FAMILY_TOOLS_SECRET` | `changeme` | Bearer token for the API. Auth disabled when set to `changeme`. |
| `CONFIG_PATH` | `/app/data/accounts.json` | Path to the config file inside the container |
| `LOG_LEVEL` | `info` | uvicorn log level |

## Security Notes

- API keys are stored in `accounts.json` on the Docker volume
- This tool is designed for **internal network use only** (no HTTPS, no user management)
- Do not expose it to the internet without adding authentication (e.g. Authelia, Caddy basic auth)
- All write operations (rename, create album) require explicit user confirmation in the UI

## Contributing

PRs welcome! Some ideas for future improvements:

- [ ] Duplicate album detection (check before creating)
- [ ] Batch operations across all account pairs
- [ ] Face thumbnail side-by-side zoom view
- [ ] Export match report as CSV
- [ ] Immich shared library support
- [ ] Docker Hub image publishing

## Related

This tool was built to address a commonly requested Immich feature. See also:
- [Immich GitHub Discussions – Cross-account face recognition](https://github.com/immich-app/immich/discussions)
- [Immich API Documentation](https://immich.app/docs/api)

## License

MIT — see [LICENSE](LICENSE)
