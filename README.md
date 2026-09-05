# Immich Family Tools

> A companion web app for self-hosted [Immich](https://immich.app) instances with multiple user accounts

[![Built with Claude Code](https://img.shields.io/badge/Built%20with-Claude%20Code-orange?logo=anthropic)](https://claude.ai/claude-code)
[![Vibe Coded](https://img.shields.io/badge/Vibe%20Coded-100%25-blueviolet)](https://claude.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy_me_a_coffee-support-FFDD00?logo=buymeacoffee&logoColor=000000)](https://buymeacoffee.com/trust1509)

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

- **DE / EN / PT-BR language toggle** — Full German, English and Brazilian Portuguese UI, persisted in localStorage
- **Album grouping** — Albums with the same name are merged into one card in the overview, showing all linked persons across accounts
- **Smart badges** — "Names synced" and "Album linked" badges on match cards now correctly detect matches extended via _Match erweitern_

## Screenshots

|         Accounts & Colour Picker         |                     Match Suggestions                      |
| :--------------------------------------: | :--------------------------------------------------------: |
| ![Accounts](screenshots/01-accounts.png) | ![Match Suggestions](screenshots/02-match-suggestions.png) |

|                 Manual Matching                  |                   Extend Match                   |
| :----------------------------------------------: | :----------------------------------------------: |
| ![Manual Match](screenshots/03-manual-match.png) | ![Extend Match](screenshots/04-extend-match.png) |

|                    Albums Overview                     |
| :----------------------------------------------------: |
| ![Albums Overview](screenshots/05-albums-overview.png) |

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

**Automatic match suggestions are limited to named people.** Unnamed people
remain available in Manual Matching. Name similarity is the primary signal;
face embeddings — where the Immich instance still exposes them — add a
secondary boost on top:

| Signal                                                | Weight    |
| ----------------------------------------------------- | --------- |
| Name similarity (Levenshtein distance)                | up to 75% |
| Face embedding cosine similarity (legacy, if exposed) | up to 25% |

#### Signal details

**Name similarity** uses Levenshtein distance normalized to 0–1:

- `"Leonie"` vs `"Leonie"` → 100%
- `"Manuel"` vs `"Manu"` → 67%
- Any unnamed person → 0% (no signal)

**Face embeddings** are fetched via `GET /api/faces?id={assetId}`, on Immich versions that still expose embeddings through this endpoint. **Immich v3.1 no longer returns embeddings here**, so on current instances matching relies on name similarity alone; when embeddings are unavailable, matching falls back gracefully to names.

#### Why does "same name" only score ~75%?

Same name → **~75%** (correct match likely, unconfirmed) — this is the practical ceiling on Immich v3.1, since embeddings are no longer exposed there.  
Same name, embeddings also match (older Immich versions that still expose embeddings) → **~85–95%** (high confidence)  
Same name, different person → mark as _"Not the same person"_ to dismiss permanently

The minimum threshold to appear as a suggestion is **25%**.

## Quick Start

### Prerequisites

- Docker + Docker Compose
- A running Immich instance, **version 3.x required** (tested against v3.1)
- API keys for each Immich account (User Settings → API Keys in Immich)

> **Immich v2 or older is not supported** since v1.3.0: album synchronization and people pagination rely on v3 API behavior (`size` pagination parameter, album inventory via `POST /api/search/metadata`). Because Immich does not backport fixes to older major versions, the latest stable Immich release is recommended.

### 1. Clone

```bash
git clone https://github.com/Trust1509/immich-family-tools.git
cd immich-family-tools
```

### 2. Configure

```bash
cp .env.example .env
# Set IMMICH_FAMILY_TOOLS_SECRET to a long random token.
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

| Permission          | Purpose                                           |
| ------------------- | ------------------------------------------------- |
| `user.read`         | Validate API key, fetch user ID for album sharing |
| `person.read`       | Load people list + thumbnails                     |
| `person.update`     | Rename person (name sync)                         |
| `person.statistics` | Load photo count per person                       |
| `asset.read`        | Load person's photos for album population         |
| `asset.view`        | Fetch thumbnail bytes                             |
| `face.read`         | Face embeddings for matching (experimental)       |
| `album.read`        | List existing albums, check current album members |
| `album.create`      | Create new shared album                           |
| `album.update`      | Update album metadata                             |
| `album.share`       | Share album with other users                      |
| `albumAsset.create` | Add photos to album                               |
| `albumUser.create`  | Add users as editors to album                     |
| `albumUser.update`  | Update user roles in album                        |

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
        ├── i18n.tsx                     # DE/EN/PT-BR translations + LanguageProvider
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

| Variable                                | Default                   | Description                                                                                                                                                              |
| --------------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `IMMICH_FAMILY_TOOLS_SECRET`            | required                  | Shared login token; there is intentionally no user management                                                                                                            |
| `IMMICH_FAMILY_TOOLS_SESSION_TTL_HOURS` | `168`                     | Session lifetime                                                                                                                                                         |
| `IMMICH_FAMILY_TOOLS_COOKIE_SECURE`     | `false`                   | Set to `true` behind local HTTPS                                                                                                                                         |
| `CONFIG_PATH`                           | `/app/data/accounts.json` | Path to the config file inside the container                                                                                                                             |
| `LOG_LEVEL`                             | `info`                    | uvicorn log level                                                                                                                                                        |
| `TZ`                                    | `Europe/Vienna`           | Container timezone. **Required for auto-sync to fire at the correct local time.** Set this to your timezone (e.g. `Europe/Berlin`, `Europe/London`, `America/New_York`). |

> **Auto-Sync timezone note:** The nightly auto-sync compares the configured time against the container's local clock. Without a matching `TZ`, the container defaults to UTC — a sync scheduled for `01:00` would fire at `01:00 UTC`, which is `03:00` in `Europe/Vienna` (CEST). Set `TZ` in your `.env` file or directly in `docker-compose.yml`.

## Security Notes

- API keys are stored server-side in `accounts.json` and are never returned to the browser
- `accounts.json` is written atomically with mode `0600`; the data directory uses `0700`
- The shared-token login creates an HttpOnly, SameSite=Strict session cookie
- This tool is designed for **internal network use only** and has no user management
- Do not expose it to the internet without HTTPS and an authenticated reverse proxy
- Shared albums are granted only to accounts participating in the selected match
- Sync logs are retained for 90 days and at most 500 entries
- All write operations (rename, create album, extend match) require explicit user confirmation in the UI

See [Security Policy](SECURITY.md), [Privacy](PRIVACY.md),
[Threat Model](docs/THREAT_MODEL.md), and [Backup & Restore](docs/BACKUP_RESTORE.md).

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

## Support

I build and maintain open-source tools for self-hosted software. If this project helps you, consider [buying me a coffee](https://buymeacoffee.com/trust1509) to support continued development and maintenance.

[![Buy Me a Coffee](https://img.shields.io/badge/Buy_me_a_coffee-support-FFDD00?logo=buymeacoffee&logoColor=000000)](https://buymeacoffee.com/trust1509)

## License

MIT — see [LICENSE](LICENSE)
