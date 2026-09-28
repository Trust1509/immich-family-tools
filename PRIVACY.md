# Privacy

Immich Family Tools is self-hosted and contains no telemetry or analytics.

## Processed data

The application processes Immich account identifiers, internal URLs, API keys,
person IDs and names, face thumbnails, transient face embeddings, match scores,
album membership, and synchronization logs.

API keys remain on the backend. Face embeddings and thumbnails are held only in
memory and are cleared on restart or account removal. Automatic matching is
limited to named people; unnamed people can be selected manually.

## Storage and retention

`accounts.json` stores account configuration, API keys, managed-album metadata,
match decisions, and synchronization logs. It is written with restrictive file
permissions.

The synchronization log is capped at 500 entries and, by default, at 90 days
(`IMMICH_FAMILY_TOOLS_LOG_RETENTION_DAYS`, operator-configurable; the
500-entry cap itself is not). Both limits are enforced **only when a new log
entry is written** (`ConfigStore.append_log`) — reading the log already hides
entries past the window, but that alone does not rewrite the file. An entry
older than the window stays in `accounts.json` on disk until the next
successful write to the log; measured directly against the store: a 200-day-old
entry was still present on disk right after removing its account, because
removing an account does not itself write a log entry. Clearing the log in the
UI removes it immediately, regardless of age.

**Container logs are a separate channel this file does not cover.** Several
operations log account and album names to the container's standard output —
for example a failed nightly sync (`main.py`), a background account-ID
backfill (`main.py`), and a failed name sync (`services/sync_service.py`).
These lines are not part of `accounts.json`; they persist according to
whatever log driver and retention the container runtime is configured with,
outside this application's control.

Removing an account deletes the account record itself, removes that account's
entries from every managed album's linked-people list, and clears its face
thumbnail/embedding caches. It does **not** delete photos, people, albums, or
users in Immich. Owner decision 2026-09-28 (#99, #112): several other kinds of
local data about that account deliberately survive the removal instead of
disappearing silently — and for two of them, there is currently **no removal
path at all**, not merely a delay:

- Its managed albums stay in the tool, marked as orphaned (owner account
  missing) or as having too few linked people. Removing the album entry itself
  (not just the account) is the only way to clear it — and even that removes
  only the tool's record, never the album or its photos in Immich. A re-added
  account never heals an orphaned album either: this tool assigns a fresh
  random identifier to every added account, which can never match the
  identifier already stored on the old album.
- The synchronization log is untouched, including entries whose text mentions
  the account by name or whose undo data points at the removed account
  (attempting to undo such an entry is refused instead of silently allowed).
  This one does eventually age out — see the retention paragraph above.
- Dismissed-match and name-sync markers are untouched — and unlike the two
  above, **nothing in this application currently removes them**, at any age.
  The code path to unmark a dismissed match exists
  (`ConfigStore.undismiss_match`) but no API endpoint or UI action calls it;
  there is no "clear all markers for this account" action either. A marker
  set today persists in `accounts.json` indefinitely, independent of whether
  the account it originally concerned still exists.

**Rollback copies are the exception, and the operator has to act on it.** Before
anything it cannot undo — a schema migration, an album-identifier assignment —
the app writes `accounts.json.vor-schema-<N>.bak` or
`accounts.json.vor-kennungsvergabe.bak`. These hold the full configuration at
that moment: API keys, including those of accounts removed afterwards, and log
entries past the retention window. Nothing rotates or deletes them; none of the
retention or removal behavior described above applies to them at all. Delete
them once an upgrade is confirmed good — `docs/BACKUP_RESTORE.md` says where
and when.

## Operator responsibility

The operator determines the lawful purpose, access permissions, backup policy,
and whether household-use exemptions apply. Face embeddings used to identify a
person may be biometric data. This document is technical information, not legal
advice.
