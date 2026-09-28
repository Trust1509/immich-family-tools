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
permissions. Logs are retained for at most 90 days and 500 entries and can be
cleared in the UI.

Removing an account deletes the account record itself and clears its face
thumbnail/embedding caches. It does **not** delete photos, people, albums, or
users in Immich, and — since the owner decision of 2026-09-28 (#99, #112) —
several kinds of local metadata about that account deliberately survive the
removal instead of disappearing silently:

- Its managed albums stay in the tool, marked as orphaned (owner account
  missing) or as having too few linked people; only removing the album entry
  itself (not just the account) clears it. A re-added account never heals an
  orphaned album — this tool assigns a fresh random identifier to every added
  account, so it can never match the identifier stored on the old album.
- Dismissed-match and synced-name markers are untouched, including ones
  involving that account's people.
- The synchronization log is untouched, including entries whose text mentions
  the account by name or whose undo data points at the removed account
  (attempting to undo such an entry is refused instead of silently allowed).

What eventually removes this: the log's own 90-day/500-entry retention window,
manually clearing the log in the UI, and manually removing an orphaned album
from the tool's management (each independent of the others).

**Rollback copies are the exception, and the operator has to act on it.** Before
anything it cannot undo — a schema migration, an album-identifier assignment —
the app writes `accounts.json.vor-schema-<N>.bak` or
`accounts.json.vor-kennungsvergabe.bak`. These hold the full configuration at
that moment: API keys, including those of accounts removed afterwards, and log
entries past the 90-day window. Nothing rotates or deletes them.

The two statements above therefore hold for `accounts.json`, not for those
copies. Delete them once an upgrade is confirmed good — `docs/BACKUP_RESTORE.md`
says where and when.

## Operator responsibility

The operator determines the lawful purpose, access permissions, backup policy,
and whether household-use exemptions apply. Face embeddings used to identify a
person may be biometric data. This document is technical information, not legal
advice.
