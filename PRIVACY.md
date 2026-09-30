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
(`backend/services/config_store.py`, `_migrate`). This delay is not
observable through the affected album's own actions in the _ordinary_ case —
a sync or rename in progress at the moment of removal still completes
normally, it only carries the stale entry for the remainder of its own run.
**One case makes it observable for longer than "the remainder of one run",**
measured directly (#127): a second caller already queued behind that album's
lock, woken the instant the first holder releases it but not yet resumed
again, can itself be cancelled before it ever reaches its own body — its own
end-of-run cleanup then never runs at all for that call. `GET
/api/sync/albums` keeps showing the removed account's person name for that
album until the application is restarted, not just until "the remainder of
its own run" as the sentence above (correctly) promises for the ordinary
case. This does
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
account row is always exactly one `_save()`; each managed album whose lock is
free at that moment and therefore gets its dead references cleaned up in the
same request is a **further** `_save()` of its own (measured: three total for
two affected, unlocked albums — one for the account row, one per album).
Since each `_save()` re-copies whatever is _currently_ on disk into
`accounts.json.bak` before writing, **what ends up in `.bak` depends on how
many saves happened and in what order — there is no single answer.** An
earlier version of this paragraph claimed one anyway ("the removed account's
API key was not present in `.bak` afterwards"); measured directly (#127)
against four distinguishable cases, that claim is wrong for two of them:

- **The account is referenced by no managed album at all** at the moment of
  deletion — the account-row removal is the ONLY save. `.bak` then holds the
  on-disk state from _before_ that save, i.e. from before the account was
  removed at all: it **does** still carry the removed account's own API key
  (measured).
- **A referenced album's lock is free**, so this call cleans that album up
  too — a _further_ save happens, and `.bak` then reflects the state right
  after the account row was removed but before that album's own stale
  reference was cleaned: the API key is already gone, but the removed
  person's name is still there (measured: one affected, unlocked album, two
  saves total). With more than one such album, `.bak` reflects the state
  right before the very LAST of these cleanup saves — an EARLIER-cleaned
  album's own stale person name can already be gone from `.bak` by then,
  while a LATER one's is still there (measured: two affected, unlocked
  albums, three saves total — `.bak` still carried the removed account's
  person name from the second album's not-yet-cleaned reference).
- **A referenced album's lock is held** by another operation at that moment —
  this call skips it entirely (see the paragraph above), and if that is the
  only affected album, the account-row removal remains the SOLE save: `.bak`
  then reflects the full pre-deletion state, exactly like the no-albums case
  above — **both** the API key **and** the stale person name are present
  (measured). Once that album's own holder finishes and performs its own
  end-of-run cleanup, `.bak` is exchanged again for the state right before
  THAT save: the API key is gone by then (it was removed earlier), the stale
  person name is still there (measured).

An album whose lock stays held **beyond** the `DELETE` request's own
lifetime keeps its stale reference in memory across many further, unrelated
saves — see the case above and the account-removal paragraph earlier — until
that lock's holder finishes or the application restarts; `.bak` at any later
point in time simply reflects whichever on-disk state preceded whatever save
most recently ran, by the same rule as everywhere else in this section.
`accounts.json.bak` is written with the same restrictive
permissions as the primary file, but it is a second file on disk carrying the
same secrets. **Its lifetime is bounded by the _next save_, not by elapsed
time — calling it "short" would be wrong.** A dormant instance (auto-sync
disabled, nobody acting on it) may go a long time between saves, during which
`.bak` — and anything it captured, such as a just-removed account's API key —
stays exactly as it was. Read-only access (browsing accounts, matches, the
log) does not write to `accounts.json` and therefore does not touch `.bak`
either — but **starting the application can**, and this is not hypothetical:
`ConfigStore._migrate()` calls `_save()` on load whenever it changes
anything — and it does that for **two** independent reasons, not only one.
The one this paragraph used to name is backfilling a field it finds missing
(`backend/services/config_store.py`, `_migrate`, the `if changed: ...
self._save()` near the end of the method). The other, added afterwards
(#117/#121/#103) and just as capable of triggering this save on its own, is
clearing out dead account references from every managed album — the same
healing that closes the observability gap described above for an aborted,
already-woken waiter. A dead reference removed this way carries the same
kind of data an ordinary removal does, including the person's name: it stops
being live data at that point, but it does **not** stop being readable —
`.bak` still holds the pre-healing on-disk state (which had the reference)
until the _next_ save, exactly like every other `.bak` snapshot in this
document (measured: a fresh load that heals one dead reference does exactly
one save, and the healed-away person's name is in `.bak` right after that
load, gone again only once something saves a second time). Separately,
`main.py`'s startup schedules `_backfill_user_ids()` in the background,
which calls `update_account()` — and therefore `_save()` — for every account
still missing a `user_id`. Any of these three paths exchanges `.bak` for the
pre-start snapshot exactly like any other save; only a run with nothing left
to backfill, no dead reference to clear, and no account missing a `user_id`
leaves `.bak` untouched. This is easy to mistake for "already gone" precisely
because it looks stale, not because it is.

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

**A crashed save can leave a third kind of file behind, and the app removes
it on the next start.** `ConfigStore._save` writes the new state to a
temporary file first, then atomically replaces `accounts.json` with it. If
the process is killed hard (SIGKILL, power loss, OOM) between those two
steps, the temporary file — with the full new state, including any API keys
it was about to write — stays on disk under a name of the form
`.accounts.json.<8 random characters>`, unbounded, until someone finds it by
hand. Since this slice, the application removes any such file — and only a
file matching exactly that pattern, nothing that merely looks similar — the
next time it starts (`backend/services/config_store.py`, measured: a
leftover of this exact shape is gone after the next `ConfigStore` load; a
hand-placed file with a similar but not identical name is left alone).

**Since this slice, the application also warns — once, on every start — if a
sibling of `accounts.json` (or its directory) is readable by group or world**
on a filesystem where that distinction is measurable at all
(`backend/services/config_store.py`; on Windows and similar filesystems the
check is skipped and says so in the log, because the underlying permission
bits are not reliable there — see `docs/BACKUP_RESTORE.md`). It only warns
and names the offending path and mode; it does not change permissions or
refuse to start. This does not replace the operator's own responsibility for
file permissions (see `docs/BACKUP_RESTORE.md`) — a warning that is never
read is not a control.

## Operator responsibility

The operator determines the lawful purpose, access permissions, backup policy,
and whether household-use exemptions apply. Face embeddings used to identify a
person may be biometric data. This document is technical information, not legal
advice.
