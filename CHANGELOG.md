# Changelog

All notable changes to Immich Family Tools are documented here.

## [1.1.0] – 2026-05-31

### New Features

#### Manuelles Matching / Manual Matching
- New page to manually match people across accounts when the automatic matcher misses them
- Per-account searchable person dropdowns (text filter, thumbnail preview, asset count)
- Assign a shared canonical name and optionally create a shared album in one step
- Accounts already selected in other rows are disabled to prevent duplicates
- Hint banner warns that this page is for new matches only → use *Match erweitern* to extend existing ones

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
- `has_album` badge now correctly shows on all pairwise match cards that share a person appearing in any managed album — including albums created via *Match erweitern*
- `names_synced` badge now detected from live person names: if both persons already share the same non-empty name, the badge appears without requiring an explicit tool sync

### Bug Fixes

- `(0)` no longer appears next to person names in dropdowns when `asset_count` is zero
- "Unbekannt" / "?" in person_refs display now falls back to the album name for legacy entries that lack a stored `person_name`
- "Alle konfigurierten Accounts enthalten" warning no longer appears immediately after a successful extend (it is now hidden when a result is already shown)
- `"Albumen"` plural bug fixed → now correctly shows `"Alben"` / `"albums"`
- `"Namen erneut sync"` corrected to `"Namen erneut synchronisieren"`
- Account owner in Albums overview and Extend Match now always shows the account name, never the raw UUID

### API Changes (Backend)

| Method | Path | Description |
|--------|------|-------------|
| `PUT` | `/api/accounts/{id}` | Edit account (name, URL, API key, colour) |
| `POST` | `/api/sync/names-multi` | Sync name + create album for N persons at once |
| `POST` | `/api/sync/extend` | Add new account/person to existing managed album |

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
