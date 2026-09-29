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
UI removes it from `accounts.json` immediately, regardless of age — but, as
with any write, the pre-clear state (including the log it just replaced)
lands in `accounts.json.bak` and stays readable there until the next save;
see the `.bak` paragraphs below.

**Container logs are a separate channel this file does not cover.** Several
operations log account and album names to the container's standard output —
for example a failed nightly sync (`main.py`), a background account-ID
backfill (`main.py`), and a failed name sync (`services/sync_service.py`).
These lines are not part of `accounts.json`; they persist according to
whatever log driver and retention the container runtime is configured with,
outside this application's control.

Removing an account deletes the account record itself and clears its face
thumbnail/embedding caches immediately. Its entries in every managed album's
linked-people list — including the person's name — follow, but not always in
the same instant: an album not currently being synced/renamed/extended loses
the entry right away; an album that IS in the middle of one of those
operations at that moment keeps it until that operation's own end (win or
lose — it is removed regardless of whether that operation itself succeeds),
because a concurrent write to the same album record would otherwise be able
to overwrite the removal with a stale copy of its own; and if the process is
killed before that end is ever reached (crash, forced restart), the entry is
removed at the very latest the next time the application starts
(`backend/services/config_store.py`, `_migrate`). None of this delay is
observable through the affected album's own actions in the meantime — a sync
or rename in progress at the moment of removal still completes normally, it
only carries the stale entry for the remainder of its own run. This does
**not** delete photos, people, albums, or users in Immich. Owner decision
2026-09-28 (#99, #112): several other kinds of
local data about that account deliberately survive the removal instead of
disappearing silently. One of the three below now has a precise removal path,
but **only for orphaned albums specifically, not for managed albums in
general** (updated 2026-09-29, #123 — see the first bullet); one still only a
**blunt** one — it removes more than just the traces of this one account, and
nothing lets you target just those traces; and the third, updated 2026-09-29
(#123) to say so plainly, has currently **no removal path at all**, blunt or
otherwise:

- Its managed albums stay in the tool, marked as orphaned (owner account
  missing) or as having too few linked people. Since 2026-09-29 (#123), an
  orphaned album can be removed **individually** — even out of a mixed group
  that still has a healthy sibling album — not only as part of removing the
  whole group at once; either way, removal clears only the tool's record,
  never the album or its photos in Immich. A re-added account never heals an
  orphaned album either: this tool assigns a fresh random identifier to every
  added account, which can never match the identifier already stored on the
  old album.
- The synchronization log is untouched, including entries whose text mentions
  the account by name or whose undo data points at the removed account
  (attempting to undo such an entry is refused instead of silently allowed).
  This one does eventually age out — see the retention paragraph above — and
  clearing the log in the UI removes it (and every other entry) from
  `accounts.json` immediately, at any age, subject to the same `.bak` caveat
  as above; neither path lets you remove just the entries about one account.
- Dismissed-match and name-sync markers are untouched — and unlike the two
  above, **nothing in this application currently removes them**, at any age,
  in bulk or individually. The code path to unmark a dismissed match exists
  (`ConfigStore.undismiss_match`) but no API endpoint or UI action calls it;
  there is no "clear all markers for this account" action either. A marker
  set today persists in `accounts.json` indefinitely, independent of whether
  the account it originally concerned still exists.

**The ordinary save leaves one more generation behind, and it is not the
rollback copy described below.** Every write to `accounts.json` —
`ConfigStore._save` — copies the file's _current on-disk content_ to
`accounts.json.bak` before writing the new state, but **only if
`accounts.json` already exists at that point**
(`backend/services/config_store.py`, `_save`: `if self._path.exists():
shutil.copy2(...)`). Read directly against that code, this cuts both ways:
the very first save of a fresh instance creates **no** `.bak` at all — there
is nothing on disk yet to copy. From the second save onward, the backup
always lags by exactly one save, because it holds whatever was on disk right
before the write that just happened. Concretely — `clear_log()` sets the
in-memory log to empty and then calls `_save()`; since the file on disk still
carries the old log at that point (and, ordinarily, already exists), `_save()`
copies it into `accounts.json.bak` before writing the now-empty log to
`accounts.json` itself. The old log stays readable in `.bak` until the _next_
write to `accounts.json` (any write, not only another log change) overwrites
the backup with a newer snapshot. The same mechanism applies to
`delete_account()`, but **not with a single `_save()` call** — that was true
before 2026-09-29 and is corrected here (#117/#121/#103): removing the
account row is one `_save()`; each managed album whose lock is free at that
moment and therefore gets its dead references cleaned up in the same request
is a **further** `_save()` of its own (measured: three total for two
affected, unlocked albums — one for the account row, one per album). Since
each `_save()` re-copies whatever is _currently_ on disk into
`accounts.json.bak` before writing, and the account row is always removed
**first**, `accounts.json.bak` after such a deletion holds an on-disk state
from which the account row is **already gone** — measured directly: the
removed account's API key was **not** present in `.bak` afterwards, contrary
to what this paragraph used to claim. What can still be in `.bak` is a
managed album's now-stale reference to the removed account — including that
account's person name — if a further album's own cleanup save happened
_after_ the save that produced the currently-readable `.bak` (measured: with
two affected albums, `.bak` still carried the removed account's person name,
because it captured the state after the first album's cleanup but before the
second's). An album whose lock was **not** free at deletion time is not
cleaned up by this call at all (see the paragraph above) and its stale
reference can persist across many further saves until that lock's holder
finishes or the application restarts — `.bak` reflects whichever on-disk
state preceded the _last_ save this particular `DELETE` triggered, not
necessarily the very first one. `accounts.json.bak` is written with the same restrictive
permissions as the primary file, but it is a second file on disk carrying the
same secrets. **Its lifetime is bounded by the _next save_, not by elapsed
time — calling it "short" would be wrong.** A dormant instance (auto-sync
disabled, nobody acting on it) may go a long time between saves, during which
`.bak` — and anything it captured, such as a just-removed account's API key —
stays exactly as it was. Read-only access (browsing accounts, matches, the
log) does not write to `accounts.json` and therefore does not touch `.bak`
either — but **starting the application can**, and this is not hypothetical:
`ConfigStore._migrate()` calls `_save()` on load whenever it backfills a
field it finds missing (`backend/services/config_store.py`, `_migrate`, the
`if changed: ... self._save()` near the end of the method), and `main.py`'s
startup schedules `_backfill_user_ids()` in the background, which calls
`update_account()` — and therefore `_save()` — for every account still
missing a `user_id`. Either path exchanges `.bak` for the pre-start snapshot
exactly like any other save; only a run with nothing left to backfill and no
account missing a `user_id` leaves `.bak` untouched. This is easy to mistake
for "already gone" precisely because it looks stale, not because it is.

**Rollback copies are the exception, and the operator has to act on it.** Before
anything it cannot undo — a schema migration, an album-identifier assignment —
the app writes `accounts.json.vor-schema-<N>.bak` or
`accounts.json.vor-kennungsvergabe.bak`. These hold the full configuration at
that moment: API keys, including those of accounts removed afterwards, and log
entries past the retention window. Nothing rotates or deletes them; none of the
retention or removal behavior described above applies to them at all — and
unlike the ordinary `accounts.json.bak` above, they are not overwritten on the
next unrelated save either. Delete them once an upgrade is confirmed good —
`docs/BACKUP_RESTORE.md` says where and when.

## Operator responsibility

The operator determines the lawful purpose, access permissions, backup policy,
and whether household-use exemptions apply. Face embeddings used to identify a
person may be biometric data. This document is technical information, not legal
advice.
