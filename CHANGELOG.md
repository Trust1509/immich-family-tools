# Changelog

All notable changes to Immich Family Tools are documented here.

## [1.4.3] – 2026-08-07

- TypeScript migrated staged 5.9.3 → 6.0.3 → 7.0.2 (nativer Compiler), tracked in #50; the PR #44 build failure was `noUncheckedSideEffectImports` (new default `true` since 6.0) catching a missing `vite/client` type reference, not a tsconfig incompatibility with 7.0
- `frontend/tsconfig.json` modernized for the new TS 6.0/7.0 defaults: added `frontend/src/vite-env.d.ts`, plus explicit `esModuleInterop`, `noUncheckedSideEffectImports`, `types: []`

### Upgrade notes

- No data migration; rebuild the container

## [1.4.2] – 2026-08-07

- Per-item results of album asset additions are now evaluated — totals count real successes, real failures are logged, duplicates are ignored silently (#46)
- Unified pagination contract for search/metadata with progress guard against endless loops (#47)

### Upgrade notes

- No data migration; rebuild the container

## [1.4.1] – 2026-08-07

- Version guard for Immich <3 on account add/update (#45)
- CI now builds the frontend with Node 22, matching the shipped image (#48)
- README confidence documentation reflects embedding unavailability on Immich v3.1 (#49)

### Upgrade notes

- No data migration; rebuild the container

## [1.4.0] – 2026-08-07

### Localization (#39)

- Sync Log messages and album sync results are now fully localized (DE/EN): log entries carry a structured `message_key` + `message_params`, rendered through the frontend translation layer in all four consumers (Sync Log, Albums overview, Manual Matching, Extend Match)
- Entries persisted before this release keep their original German text as fallback

### API robustness

- Name Sync uses the documented `PUT /api/people/:id` endpoint again instead of the undocumented `PATCH` variant (result of a three-voice external code review; PUT is the stable primary endpoint in Immich v3.1 and also works on v2)
- README now states Immich v3.x as the required minimum version

### Maintenance

- Dependency updates: fastapi 0.141.1, uvicorn 0.52.1, @types/react 19.2.18, @types/react-dom 19.2.4, actions/setup-python v7
- TypeScript 7 major update deliberately deferred (tracked in PR #44)
- Review follow-ups filed as issues #45–#49

### Upgrade notes

- No persisted-data migration required; existing accounts, managed albums and sync history remain compatible
- Rebuild the container so backend and frontend both report version `1.4.0`

## [1.3.0] – 2026-08-02

### Immich v3 compatibility

- Added tested compatibility with Immich v3.1
- Migrated person asset discovery to the paginated `POST /api/search/metadata` API
- Updated people pagination to use Immich v3's `size` parameter
- Updated Name Sync to modify people through `PATCH`
- Deduplicated paginated asset IDs and prevented assets already present in an album from being added again

### Auto-Sync reliability

- Auto-Sync now records the executed date and configured time as one slot
- Changing the configured time allows one intentional additional run on the same day
- An unchanged time slot remains protected against duplicate runs during the polling window

### Maintenance and verification

- Updated tested backend, frontend and GitHub Actions dependencies
- Added regression coverage for Immich v3 album search, people pagination, Name Sync and scheduled synchronization
- Verified manual and automatic album synchronization against Immich v3.1 in production
- Backend tests, frontend tests, typecheck, production build, audits, secret scan and container build pass

### Upgrade notes

- No persisted-data migration is required
- Existing `.env`, accounts, managed albums and sync history remain compatible
- Rebuild the container from this release so the backend and frontend both report version `1.3.0`

## [1.2.1] – 2026-06-21

### Maintenance

- Updated backend runtime dependencies to their tested current minor/patch releases
- Updated React and React DOM together to 19.2.7 with matching type packages
- Updated Lucide, pytest and pytest-asyncio after compatibility testing
- Updated GitHub checkout and Node setup actions
- Fixed Gitleaks authentication for Dependabot pull requests
- Grouped and limited Dependabot updates to reduce pull-request noise

### Verification

- Backend tests, frontend tests, production build and container build pass
- npm audit, pip-audit and Gitleaks report no known findings
- No application features, persisted data or Immich API behavior changed

## [1.2.0] – 2026-06-20

### Security

- Added shared-token login with signed HttpOnly sessions, logout and login rate limiting
- Immich API keys never leave the backend; account responses expose only configuration status
- Restricted album sharing to accounts participating in the selected match
- Disabled HTTP redirects for Immich API requests and validated configured URLs
- Added Same-Origin browser policy, security headers and no-store caching for sensitive API data
- Hardened `accounts.json` with schema validation, atomic writes, backups and restrictive permissions

### Reliability

- Fixed name-sync undo by reading and storing the previous name before mutation
- Added preflight validation, duplicate protection, partial state and per-album synchronization locks
- Account removal now clears local references and caches without modifying Immich
- Automatic matching now covers all named people with bounded embedding concurrency; unnamed people remain manual
- Sync logs are retained for 90 days / 500 entries and can be cleared
- Added consistent application versioning and a minimal Docker health check

### Engineering

- Added backend and frontend tests, GitHub Actions CI, Dependabot and security scans
- Added reproducible frontend installs through a committed lockfile
- Added security, privacy, threat-model and backup/restore documentation

## [1.1.3] – 2026-06-01

### New Features

**Nightly Auto-Sync**

- Background task checks every 30 seconds if the configured time has been reached (server local time); fires exactly once per day
- Refreshes all managed albums automatically — no manual interaction needed
- `GET/PUT /api/sync/autosync-config` endpoint persists `{enabled, time}` in `accounts.json`; survives container restarts
- Toggle switch + time picker (`<input type="time">`) in the Albums view, next to "Sync all"
- Shows "Next sync: today/tomorrow at HH:MM"
- **Timezone:** container must have `TZ` set to your local timezone (default `Europe/Vienna`). Set `TZ=Europe/Berlin` etc. in `.env` for other timezones. Without this, the container runs in UTC and the sync fires at the wrong local time.

**Bulk Sync Results — Visual Feedback**

- "Sync all" now shows results per album card incrementally as each album finishes
- Each card shows a spinner while its albums are being processed, then immediately displays log entries (new assets / no new assets / errors)
- Consistent display with the individual "Sync now" button on each card

### Bug Fixes

- Auto-sync toggle now updates immediately without page refresh (missing `queryClient.invalidateQueries` on mutation success)

---

## [1.1.2] – 2026-05-31

### Bug Fixes

**Match Suggestions — Album & Multi-Account State Now Fully Consistent**

The match suggestion view was not correctly showing "Album linked" and the multi-account hint for all pairwise combinations of a connected person (e.g. Manuel across Manu, Majo and Jojo accounts).

Root cause: the logic relied on `linked_match_ids` stored per album, which were sometimes stale or incomplete after the album was extended.

Fix — transitive person-ref grouping (same logic in backend and frontend):

- Albums are grouped by normalised name; all `person_ids` across the group are collected; all pairwise combinations are derived from that set
- No reliance on stored `linked_match_ids` — derived fresh from `person_refs` on every request
- Works correctly regardless of how the connection was created (Match Suggestions, Manual Match, Extend Match)
- Covers transitive connections: Manu↔Majo + Majo↔Jojo in albums named "Manuel" → Manu↔Jojo is also correctly shown as connected

**ManualMatch — Removed "Create Shared Album" Checkbox**
Album creation is the core purpose of the page. The checkbox was removed; the album section is always visible.

**Version Display**
Sidebar now correctly shows v1.1.2 (was stuck at v1.1.0 in previous patch releases).

---

## [1.1.1] – 2026-05-31

### Bug Fixes

- **Photo count**: People grid lazy-loads count per person as fallback when Immich API returns `assetCount: 0` in list responses
- **ManualMatch alignment**: Page is now left-aligned (removed `mx-auto`)
- **ManualMatch album options**: Added owner account selector, mode toggle (new/existing album), existing album picker per owner

### New Backend

- `POST /api/sync/names-multi` now supports `existing_album_id` to link an existing album instead of creating a new one

---

## [1.1.0] – 2026-05-31

### New Features

#### Manuelles Matching / Manual Matching

- New page to manually match people across accounts when the automatic matcher misses them
- Per-account searchable person dropdowns (text filter, thumbnail preview, asset count)
- Assign a shared canonical name and optionally create a shared album in one step
- Accounts already selected in other rows are disabled to prevent duplicates
- Hint banner warns that this page is for new matches only → use _Match erweitern_ to extend existing ones

#### Match erweitern / Extend Match

- New page to add a new account/person to an existing shared album
- Shows all managed albums as selectable cards with full info: owner, linked persons (with coloured account badges), photo count, last sync date
- Only shows accounts not yet in the selected match
- Searchable person dropdown with thumbnail previews
- Checkbox "Namen synchronisieren" renames the new person to match the existing canonical name
- Backend shares the Immich album with the new account, adds the person's assets, and updates the stored `person_refs`

#### Account bearbeiten / Edit Accounts

- Accounts can now be edited in-place (name, Immich URL, API key, colour)
- Changes to URL or API key automatically re-validate the connection and refresh the Immich user ID
- Colour picker with 10 presets + full custom HTML colour input
- Edit form opens inline per account card; save is disabled until a change is made

#### Account-Farben / Account Colours

- Account colours are now shown consistently as coloured badges everywhere a person's account is referenced: People grid, Match suggestions, Albums overview, Extend Match, Manual Match
- `account_color` is now stored in all `person_refs` entries when albums are created or extended
- Frontend falls back to a live account lookup when older stored entries lack the colour field

#### DE / EN Sprachumschalter / Language Toggle

- Full German and English translation of all UI strings (~80 keys)
- Toggle button in the sidebar footer; preference is persisted in localStorage
- All dynamic strings (plurals, interpolated names) supported via typed translation function

### Improvements

#### People Grid — Paralleles Laden / Parallel Loading

- People are now fetched per account in parallel using `useQueries` instead of one aggregated call
- Results appear as each account responds — no more waiting for the slowest account
- Progress indicator shows `1/3 Accounts` with an animated progress bar while loading

#### Albums Overview — Gruppierung / Grouping

- Albums with the same name are merged into a single card
- Merged card shows all unique linked persons across all grouped entries
- Photo count uses the most-recently-synced entry (instead of incorrectly summing all entries)
- "Jetzt synchronisieren" and "Verknüpfung entfernen" operate on all entries in the group
- Owner name always resolved from live account data (no more UUID shown as owner)

#### Match Suggestions — Smarte Badges / Smart Badges

- `has_album` badge now correctly shows on all pairwise match cards that share a person appearing in any managed album — including albums created via _Match erweitern_
- `names_synced` badge now detected from live person names: if both persons already share the same non-empty name, the badge appears without requiring an explicit tool sync

### Bug Fixes

- `(0)` no longer appears next to person names in dropdowns when `asset_count` is zero
- "Unbekannt" / "?" in person_refs display now falls back to the album name for legacy entries that lack a stored `person_name`
- "Alle konfigurierten Accounts enthalten" warning no longer appears immediately after a successful extend (it is now hidden when a result is already shown)
- `"Albumen"` plural bug fixed → now correctly shows `"Alben"` / `"albums"`
- `"Namen erneut sync"` corrected to `"Namen erneut synchronisieren"`
- Account owner in Albums overview and Extend Match now always shows the account name, never the raw UUID

### API Changes (Backend)

| Method | Path                    | Description                                      |
| ------ | ----------------------- | ------------------------------------------------ |
| `PUT`  | `/api/accounts/{id}`    | Edit account (name, URL, API key, colour)        |
| `POST` | `/api/sync/names-multi` | Sync name + create album for N persons at once   |
| `POST` | `/api/sync/extend`      | Add new account/person to existing managed album |

---

## [1.0.0] – 2026-05-30

Initial release.

### Features

- Multi-account Immich support (add/remove accounts via API key)
- Unified people grid across all accounts
- Automatic match suggestions (name similarity + face embeddings + shared assets)
- Name sync and shared album creation for matched person pairs
- Sync log with undo support for name syncs
- Thumbnail proxy with LRU cache (50 MB)
- Docker single-container deployment
- TrueNAS Scale / ZFS POSIX ACL support
