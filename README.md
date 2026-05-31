# Immich Family Tools

> A companion web app for self-hosted [Immich](https://immich.app) instances with multiple user accounts

[![Built with Claude Code](https://img.shields.io/badge/Built%20with-Claude%20Code-orange?logo=anthropic)](https://claude.ai/claude-code)
[![Vibe Coded](https://img.shields.io/badge/Vibe%20Coded-100%25-blueviolet)](https://claude.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Solving the missing cross-account face recognition problem via the Immich REST API, without touching your existing Immich installation.

## The Problem

Immich does not share face recognition across user accounts. If your family runs several separate Immich accounts on the same server, each account builds its own independent person database — even though 90% of the faces are the same people.

This tool bridges that gap.

## Features

### Core
- **People overview** — All recognized faces from all accounts in one unified view, loaded per-account in parallel with progress indicator
- **Match suggestions** — Automatically detects the same person across accounts using name similarity, face embeddings (if available), and shared assets
- **Name sync** — Set a canonical name across all matched persons with one click; bulk-sync for high-confidence matches
- **Shared album** — Create a shared album containing all photos of a matched person, populated from each account's own API key
- **Sync log** — Full history of all actions with undo support for name syncs

### Manual Matching
- **Manuelles Matching** — Pick one person per account from searchable dropdowns, assign a shared name, and optionally create a shared album in one step — for cases the automatic matcher missed
- **Match erweitern** — Add a new account/person to an existing shared album (e.g. when a new family member joins); shares the album, adds photos, and optionally renames the person

### Account Management
- **Account bearbeiten** — Edit name, Immich URL, API key and colour for any account; changes re-validate the connection automatically
- **Custom colours** — Each account has an assignable colour (10 presets + custom picker) shown consistently as badges everywhere in the UI

### UI & Internationalisation
- **DE / EN language toggle** — Full German and English UI, persisted in localStorage
- **Album grouping** — Albums with the same name are merged into one card in the overview, showing all linked persons across accounts
- **Smart badges** — "Names synced" and "Album linked" badges on match cards now correctly detect matches extended via *Match erweitern*

## Screenshots

> _Add screenshots here_

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

**Face embeddings** are fetched via `GET /api/faces?id={assetId}` — experimental, not available in all Immich versions. Falls back gracefully to name-only matching.

**Shared assets** — reserved for future use (e.g. partner library sync). Asset IDs differ across accounts even for identical photos.

#### Why does "same name" only score ~75%?

Same name, no embeddings → **~75%** (correct match likely, unconfirmed)  
Same name, embeddings match → **~85–95%** (high confidence)  
Same name, different person → mark as *"Not the same person"* to dismiss permanently

The minimum threshold to appear as a suggestion is **25%**.

## Quick Start

### Prerequisites

- Docker + Docker Compose
- A running Immich instance
- API keys for each Immich account (User Settings → API Keys in Immich)

### 1. Clone

```bash
git clone https://github.com/Trust1509/immich-family-tools.git
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

When creating API keys in Immich (**User Settings → API Keys → Create new key**), enable exactly these permissions:

| Permission | Purpose |
|---|---|
| `user.read` | Validate API key, fetch user ID for album sharing |
| `person.read` | Load people list + thumbnails |
| `person.update` | Rename person (name sync) |
| `person.statistics` | Load photo count per person |
| `asset.read` | Load person's photos for album population |
| `asset.view` | Fetch thumbnail bytes |
| `face.read` | Face embeddings for matching (experimental) |
| `album.read` | List existing albums, check current album members |
| `album.create` | Create new shared album |
| `album.update` | Update album metadata |
| `album.share` | Share album with other users |
| `albumAsset.create` | Add photos to album |
| `albumUser.create` | Add users as editors to album |
| `albumUser.update` | Update user roles in album |

> **Note:** All accounts (owner and editors) need the same set of permissions since each account's API key is used to add its own assets to shared albums.

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
│   │   ├── accounts.py     # CRUD + edit + live status check
│   │   ├── people.py       # Aggregated people + thumbnail proxy
│   │   ├── faces.py        # Match computation + 5-min cache
│   │   └── albums.py       # Sync actions: names, album, extend, log, undo
│   └── services/
│       ├── immich_client.py   # Async Immich REST client (httpx)
│       ├── face_matcher.py    # Cosine similarity + Levenshtein
│       ├── sync_service.py    # Name/album/extend sync
│       ├── config_store.py    # JSON persistence (accounts.json)
│       └── thumbnail_cache.py # LRU in-memory cache (50 MB)
└── frontend/               # React 18 + TypeScript + Tailwind (dark mode)
    └── src/
        ├── i18n.tsx                     # DE/EN translations + LanguageProvider
        ├── components/
        │   ├── AccountManager.tsx       # Page 1: manage + edit accounts + colour picker
        │   ├── PeopleGrid.tsx           # Page 2: unified people view (parallel loading)
        │   ├── MatchSuggestions.tsx     # Page 3: match + sync actions
        │   ├── ManualMatch.tsx          # Page 4: manual cross-account matching
        │   ├── ExtendMatch.tsx          # Page 5: extend existing matches
        │   ├── AlbumsOverview.tsx       # Page 6: managed albums (grouped by name)
        │   └── SyncPanel.tsx            # Page 7: sync log + undo
        └── api/client.ts                # Typed API client
```

**No database required** — all data is loaded live from the Immich API. Only `accounts.json` (API keys + dismissed matches + managed albums + sync log) is persisted on the Docker volume.

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
- All write operations (rename, create album, extend match) require explicit user confirmation in the UI

## Contributing

PRs welcome! Some ideas for future improvements:

- [ ] Face thumbnail side-by-side zoom view
- [ ] Export match report as CSV
- [ ] Immich shared library support
- [ ] Docker Hub image publishing
- [ ] Notification when new persons are detected

## Related

- [Immich GitHub Discussions – Cross-account face recognition](https://github.com/immich-app/immich/discussions)
- [Immich API Documentation](https://immich.app/docs/api)

## License

MIT — see [LICENSE](LICENSE)
