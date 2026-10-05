# Changelog

All notable changes to Immich Family Tools are documented here.

## [1.9.0] – 2026-09-30

**Risk: backup**

No data migration and no schema change. The backup line is here because the
first sync after the upgrade may **change album names in the tool**: the name
in Immich now wins (#97). If you renamed albums directly in Immich since you
created them here, the tool adopts those names on the next sync. A snapshot of
`accounts.json` before the upgrade lets you go back to 1.8.0 with the old
names. Under 1.9.0 the next sync adopts the Immich name again — to keep a name,
rename the album in Immich.

**Rollout:** build with the commit id, so `/api/health` can report it (#68):

```bash
GIT_SHA=$(git rev-parse HEAD) docker compose up -d --build
```

Without `GIT_SHA` the build still works and `/api/health` reports
`"commit":"unknown"`. On the first start, the app tightens `accounts.json` to
`0600` if it was readable by group or world (one INFO line; a WARNING instead
if the file system refuses the change). The log may also ask you to check and
delete a file next to `accounts.json` whose last part is eight characters (for
example `.accounts.json.20260930`):

- If **you** made it, keep it. To stop the warning, rename it so the last part
  is not eight characters (for example append `.bak`) or move it out of the
  data directory.
- If you did not, it is most likely left over from a crash under an older
  version and holds a full copy of your configuration, including API keys —
  delete it.

See "Tighter file permissions" below.

### Two groups may carry the same name (#98, #113, #119)

A group name is a label, not an identity. Renaming an album group no longer
refuses a name because another group already uses it — the message "already
belongs to a different group" is gone. While two groups share a name, the group
preview lists every group with that name plus the option to start a new group,
with **nothing preselected**; creating or linking an album with that name stays
disabled until you choose. If the situation changes between the preview and
your request, the server refuses (`err_group_choice_required`,
`err_group_situation_changed`) instead of guessing. A name typed with "ß" also
finds groups spelled with "ss" (and vice versa); if both spellings exist as
separate groups, each spelling finds its own. **Extend** still lets you pick
the group directly.

### The name in Immich wins (#97)

When the tool syncs a managed album, it takes over the album's current name
from Immich and logs the change ("Album … is now called … in Immich"). A rename
you did in Immich shows up here; a rename that reached Immich but failed to be
saved here heals on the next sync. An empty or blank name from Immich is
ignored.

### Creating an album waits for the group preview (#110)

The "create" and "link" buttons stay disabled until the group preview has
answered for exactly the name you typed. If the preview fails (for example the
server is briefly unreachable), the button stays disabled and you get a
**Retry** button — the tool no longer lets a failed check silently decide the
group. The preview is fetched fresh for every name you type, and creating,
linking, renaming, extending or removing an album refreshes it.

### Removing an account no longer makes things disappear (#99, #103, #112, #117, #121, #123)

- Albums stay under management even if only one person — or none — is left,
  and are **marked** ("Owner account deleted", "Only one person left",
  "No person linked anymore"). The count behind these marks includes only
  people whose account still exists.
- Renaming or syncing a group handles the albums whose owner still exists and
  **skips** the others, with a visible note; on rename, the server refuses
  only the orphaned album itself. The nightly auto-sync skips orphaned albums
  too, without an error entry every night.
- Removing an account does not wait for a sync, rename or extend running on
  one of its albums. Those operations check again under the album lock that
  the owner account still exists: a rename stops with "Owner account not
  found", a sync or extend stops with the log entry "Owner account no longer
  exists".
- References to a removed account are dropped from its albums right away; an
  album that is busy at that moment is cleaned up when its running operation
  ends, and at the latest on the next start.
- An orphaned album can be **removed on its own**; the other albums of its
  group stay under management.
- A group whose most recently synced album is orphaned can no longer be
  extended; **Extend** says why.
- **Undo** is disabled for log entries of a removed account.
- The sync log, dismissed suggestions and synced-name markers are **kept**
  when you remove an account. Previously, removing any account cleared _all_
  dismissed suggestions and synced-name markers — for every account — and
  dropped log entries that belonged to it or merely contained its name as part
  of another word.
- **Privacy:** removing an account no longer clears its local traces.
  `PRIVACY.md` describes what stays: the log still ages out and can be cleared,
  orphaned albums can be removed one by one, but dismissed-suggestion and
  synced-name markers currently have no removal path at all.

### The album card shows what happened (#102, #124)

- A sync that fails — a card's "Sync now" or the page's "Sync all", for all or
  only some albums — always shows an error line on the card, also when several
  actions overlap and an older one finishes last.
- An album removed (for example in another tab) while its group is being
  renamed is skipped with its own note instead of stopping the rename for the
  rest of the group.
- The note about albums skipped because their owner account was deleted keeps
  its count when the list reloads, and reads correctly when several albums
  with different owners are skipped.
- After a rename attempt, submitting an empty or blank name keeps the field
  open with "Please enter a name" instead of closing it and hiding the earlier
  error.

### Changes to one album no longer undo each other (#101, #123)

Syncing, renaming, extending and removing an album now wait for each other.
Before, extending an album with a person could write back an older version of
the album and silently undo a rename that had just finished. If an album is
removed while another operation is waiting for it, that operation stops
("Managed album not found") instead of changing Immich for an album you no
longer manage. Removing an album waits only for an operation already running on
that same album; the albums of a group are removed in parallel, and if one of
them cannot be removed, the card says so.

### Clearer log lines for the rollback copies (#105)

The container log now says which rollback copy was written:
`Rueckweg vor Schemasprung auf Version N: …` or
`Rueckweg vor Kennungsvergabe: …`, and the matching `… nicht moeglich: …`
warnings. Version 1.8.0 used `Sicherung vor Schemasprung` for both — if you set
up log alerts on that text, update them. `docs/BACKUP_RESTORE.md` lists both
forms. The nightly auto-sync logs the orphaned albums it skips by id, and its
album count no longer includes them. Its failure line now names the album by
id instead of by name.

### Known limitation: undoing a migration a second time (#130)

Documented, not changed in this release (it contains no schema migration).
After undoing a schema migration, working with the old version and upgrading
again, `accounts.json.vor-schema-<N>.bak` still holds the state from before the
**first** upgrade. `docs/BACKUP_RESTORE.md` ("Undoing a migration") now says so
and points to the ZFS snapshot, or to `accounts.json.vor-kennungsvergabe.bak`
where it exists, for that case. The same section now builds the old release
without starting it before the rollback copy is put back.

### Tighter file permissions and crash leftovers (#106, #68, #124)

- On start, the app warns about files next to `accounts.json` whose name starts
  with `accounts.json.` or `.accounts.json.` and that are readable by group or
  world, and about a data directory that is.
- `accounts.json` itself is tightened to `0600` after it has been read
  successfully. A symlinked `accounts.json` is left alone and reported.
- A temporary file left behind by a crash while saving (it carries the app's
  own `speichern-tmp-` marker) is removed on start once it is older than five
  minutes; a younger one is reported and removed by a second check about five
  minutes after start. Files that only look similar are reported, never
  removed — see the rollout note above for hand-made copies.
- `GET /api/health` reports `commit`, taken from the `GIT_SHA` build argument
  (`"unknown"` if it was not set). `docs/betrieb/erreichbarkeit.md` uses it to
  tell exactly whether the running build is behind.

### Stricter API at the edges (#85)

- Request validation errors (missing field, wrong type, unknown field) now use
  the same shape as every other error: a string `detail` plus
  `error_key`/`error_params` (`err_validation_failed`, 422). At most 20 field
  names are listed; the rest is given as a count (`more`).
- Request bodies of the `/api/sync/…` endpoints reject unknown fields.
- Invalid JSON (`err_invalid_json_body`), credentials in the Immich URL
  (`err_credentials_in_url`), a disallowed network address
  (`err_disallowed_network_address`) and a URL that is not `http(s)://`
  (`err_invalid_url_scheme`) each get their own translated message when they
  are the only problem in the request.
- `GET /api/sync/album-group` refuses `album_name` given twice
  (`err_duplicate_query_param`, 422).
- Any `/api/` request with a `Transfer-Encoding` header is refused with 411
  (`err_length_required`) and `Connection: close`, without reading its body. A
  request the HTTP server already rejects (for example with both
  `Transfer-Encoding` and `Content-Length`) still gets the server's plain 400.
  The app's own web interface sends its request bodies with a
  `Content-Length`.
- Client values echoed back in error responses are shortened.

### For contributors

- Log messages are now a contract: every `log_*` key the backend sends needs an
  entry in `frontend/src/logMessages.contract.json` and a template in all four
  languages; a test on each side enforces it, now also for every log entry
  built while the backend tests run (#94, #115).
- The working tree uses LF line endings on every platform (`.gitattributes`),
  guarded in CI; `npx prettier --check .` now also works on Windows checkouts
  with `core.autocrlf=true`. Existing Windows checkouts: see `CLAUDE.md` for the
  one-time refresh (#104). Exceptions to the guard are an exact path list in
  `scripts/zeilenenden-ausnahmen.txt` (#118).
- API: `GET /api/sync/albums` returns two computed flags per album,
  `owner_account_missing` and `too_few_people`; `err_album_name_in_use` is no
  longer returned. `DELETE /api/sync/albums/{id}` may wait until an operation
  already running on the same album has finished. `GET /api/sync/album-group`
  can return `{"status": "many", "candidates": [...]}` for an ambiguous name.
  `POST /api/sync/album` and `POST /api/sync/names-multi` without `group_id` or
  `force_new_group` now answer an ambiguous name with 409
  `err_group_choice_required` instead of silently starting a new group; with
  `expected_no_group: true` they answer 409 `err_group_situation_changed` if a
  group has appeared since the preview. `DELETE /api/accounts/{id}` answers 204
  instead of 404 for an already removed account that albums still refer to. See
  "Stricter API at the edges" for the new error keys and the 411.
- `backend/tests/test_umbenennen_kollision.py` is removed together with the
  collision check it tested (#98). The start-up tests for file permissions and
  crash leftovers live in `backend/tests/test_start_betrieb.py`; they were
  briefly named `backend/tests/test_s7_na1_betrieb.py` during development.
- Test and documentation follow-ups without behavior change: #111, #114, #116,
  #120.

## [1.8.0] – 2026-09-27

**Risk: backup**

No data migration in this release. The backup line is here for a different
reason: this release changes how the app decides whether an album name may be
used, and it renames albums **in Immich**. A snapshot before the upgrade costs
nothing and makes the change reversible.

### You can rename an album group (#79)

Contributed by @crisvale and reworked here. A group card now has a pencil: type
a new name, press Enter, and every real Immich album behind that card is
renamed. The group itself does not depend on the name (since 1.7.0 it carries
its own identifier), so renaming cannot split it.

What the rework added, in the order you would notice it:

- **A rename can no longer be undone behind your back.** If an automatic sync
  was running with an older snapshot of the album, it used to write the old name
  back — while Immich already carried the new one, and both log entries said
  "success". There was no error anywhere to see.
- **A partial failure is visible, and you can retry it.** If one album of the
  group fails, its log entry is shown as an error and the input stays open.
  Pressing Enter again now reaches the album that stayed behind; before, the
  retry silently did nothing.
- **A failed rename no longer hides what already worked.** If a later album
  throws an HTTP error, the entries collected so far stay on the card next to
  the error message.
- **The card shows the result of your last action.** A "Sync all" result used to
  take precedence for as long as it sat in memory, so a rename afterwards showed
  nothing at all — not even a failure.

### The app no longer blocks the way out of a name clash

Two groups can end up with the same name, and while they do, the group preview
stays silent for both: typing that name offers you no group. The one operation
that fixes this — changing one of them to a spelling that only _looks_ the same,
like "Strassenfest" against "Straßenfest" — is now allowed.

A rename is refused only when it would make things worse: when a name that is
still in use afterwards would lose its group, or would point at a _different_
group than before. In that case you get a message naming the album.

The name you rename _away from_ is not protected this way. Depending on which
other spellings exist — "Straße" against "Strasse", for example — typing that
name may afterwards suggest a different group, or none. Your albums stay in
their groups; only the suggestion for that spelling changes. The suggestion appears a moment after you stop typing — a
very quick click can currently create the album before it is shown (#110).
_(Added 2026-09-28: the first version of these notes promised more than the
release does.)_

### You choose which group an album joins (#81)

Until now the app worked out the group from the album name and told you
afterwards. When you create a shared album, it now shows you up front which
group the album would join — with the accounts and people already in it — and
lets you put it in a **new** group instead.

That is the reason the next item exists: once the app _promises_ you a group,
the rule behind the promise has to be one you can predict.

### Names are compared the way a person reads them (#83)

Two albums whose names differ only in capitalisation, in surrounding blank
space, or in how the same characters are encoded now count as the same name.
"Straßenfest" and "STRASSENFEST" are one name; so are two spellings of an
umlaut that look identical on screen but are stored differently.

This changes which albums the app would group **by name** — so before shipping
it, we measured it against the real data instead of guessing: 8 managed albums,
6 groups before, 6 groups after, no album moved. Your groups do not depend on
names any more anyway (since 1.7.0 they carry their own identifier); this only
affects what the group preview above offers you for a name you type.

### A double click no longer creates a second album (#86)

Clicking "create album" twice used to create two managed entries and two real
albums in Immich for one face pair. The second click now succeeds and tells you
the album already existed. Two people creating an album with the same name at
the same moment end up in **one** group, not two.

### After a data migration, there is a file to go back to

The app now writes a rollback copy **once** before it migrates the stored file,
and never overwrites it: `accounts.json.vor-schema-<N>.bak`. Before it assigns
group identifiers without a schema change, it writes
`accounts.json.vor-kennungsvergabe.bak`, which it renews each time.

This matters because the ordinary `accounts.json.bak` is rewritten on the next
save — seconds later — so it stops being the pre-migration state almost
immediately. The upgrade notes for 1.7.0 promised this file for releases after
1.7.0; this is that release. `docs/BACKUP_RESTORE.md` has the order that
actually works when rolling back (old image first, then the file).

### Upgrade notes

- Take a snapshot of the dataset volume before you upgrade. The app writes to
  `accounts.json` on every rename.
- Renaming writes to Immich. Your API key needs write access to albums — the
  same access the app already needs for creating and sharing them.
- Nothing in the stored file changes shape. Rolling back to 1.7.0 keeps working.

## [1.7.0] – 2026-09-21

**Risk: backup**

This release migrates `accounts.json`. Read the upgrade notes before you rebuild.

### Album groups no longer hang on the album name

The app groups managed albums so that several real Immich albums — one per account — count as _one_ family album. Until now that grouping was done **by name**: two albums were the same group if they happened to be called the same thing.

That had two consequences you could actually hit:

- **Two unrelated albums that share a name were treated as one group.** A face pair could then be counted as "already has an album" when in fact no album contained both — and the suggestion was **silently dropped**. A missing suggestion is harder to notice than a duplicate one.
- **A name you typed slightly differently made a second group.** "Familie 2024" and "Familie" never found each other.

Each group now carries an identifier of its own. The name is only a label. Renaming an album — in the app or directly in Immich — cannot split a group any more.

### Error messages from the server are translated (#74)

Every message the server sends now carries a key, and the app renders it in your language. Previously these were German no matter which language you had picked. If the app meets a message it does not know, it still shows the German sentence rather than an empty box.

### A smaller fix you may notice

When you link an **existing** Immich album and leave the name field empty, the app now fetches the album's real name instead of storing its internal id. Album lists used to show a long string of letters and digits in that case.

### Upgrade notes

- **This release migrates `accounts.json`.** On first start, every managed album is given a group identifier, derived once from the names you have today — so your existing groups stay exactly as they are.
- **The migration is reversible.** Measured: an older container reads a migrated file without complaint, and going back and forth leaves the groups and the data untouched. A ZFS snapshot beforehand is still the better safety net.

  > **Correction, 2026-09-21 — please read this before upgrading.** This entry
  > originally said "a `.bak` is written next to the file as usual", implying it
  > is a usable fallback after the migration. It is not. The ordinary `.bak` is
  > rewritten on the next save — and the account backfill at startup runs
  > seconds after the migration, so the pre-migration state survives only
  > moments. If you are upgrading **to 1.7.0**, take a ZFS snapshot first; do
  > not rely on `accounts.json.bak`.
  >
  > Releases **after** 1.7.0 write `accounts.json.vor-schema-<N>.bak` once
  > before a migration and never overwrite it. That file does not exist in
  > 1.7.0 — an image that reports version 1.7.0 and writes it is a build from
  > after the tag, not this release.
  >
  > _Why this correction is here at all:_ `docs/agents/release-ritual.md` says
  > old entries are not amended retroactively, because the changelog documents
  > what happened. This is a deliberate deviation, disclosed rather than made
  > quietly: the original sentence is quoted above verbatim and nothing was
  > removed, and the claim it made is one an operator acts on **before** an
  > upgrade they have not run yet. A correction that only appears in the next
  > release would arrive after the moment it is needed.

- **One deliberate change at migration time:** albums whose name is **empty or only spaces** each get their own group instead of sharing one. An empty name says nothing about belonging, and unlike before, the grouping is now permanent. If you have no such albums, nothing changes for you. To check beforehand:
  ```
  python -c "import json;d=json.load(open('accounts.json'));print([a['album_name'] for a in d.get('managed_albums',[]) if not str(a.get('album_name','')).strip()])"
  ```
  An empty list means this does not affect you.
- Rebuild the container so backend and frontend both report `1.7.0`.

### Still open

Creating an album still joins a group **by name**, so two albums you name the same still end up together whether you meant it or not. Choosing the group explicitly is tracked as #81.

## [1.6.0] – 2026-09-06

**Risk: safe**

### Spanish (#73)

- The app is now available in **Spanish**, contributed by [@crisvale](https://github.com/crisvale) — terminology kept consistent with Immich's own Spanish localisation. Pick it in the language switcher next to 🇩🇪 DE, 🇬🇧 EN and 🇧🇷 PT-BR.
- All 183 strings are translated, including the login screen and the sync log. Nothing falls back to German.
- A browser set to any Spanish variant — `es`, `es-MX`, `es-AR` — starts the app in Spanish on the first visit.
- Dates read `4 mar 2026, 14:30`.

### The language switcher holds more than four languages now

- The switcher used to be a single row that split the available width between the buttons. It fitted four, and it fitted them exactly: measured in the real sidebar, the longest label had about **three pixels** to spare.
- It is now a two-column grid. Every button keeps the same width no matter how many languages ship, and new ones wrap onto a new row instead of squeezing the existing ones.
- The active language now also carries `aria-current`, so screen readers announce which one is selected — before, it was only marked by colour.

### Under the hood, for anyone translating

Two guards were added after a review found that a translation could be _structurally_ wrong without anything noticing:

- A translation entry that is a string in three languages and a function in the fourth used to compile and pass every test — and render the word `undefined` on screen. That now fails to build.
- A language that takes fewer arguments than its siblings, or an empty string, now turns the test suite red.
- The list of shipped languages in the README is checked against the switcher itself, so it can no longer quietly go stale.

None of this changes what you see. It changes what can reach you.

### One German typo

- The rename hint read `Person auf „Name" umbenennen` — an opening German quote closed with a straight one. It now closes properly: `Person auf „Name“ umbenennen`. Spotted by a reviewer in passing; it had been there since the string was written.

### Upgrade notes

- **No data migration.** Rebuild the container so backend and frontend both report `1.6.0`.
- Your chosen language is remembered per browser, unchanged. If you have never chosen one, the browser's language decides.

### Please test

- Switch to Spanish and walk through accounts, people, matches and the sync log — this is the first release with a language none of the maintainers speaks.
- Look at the language switcher itself: four buttons in two rows, all the same size, nothing clipped.
- If anything reads oddly in Spanish, a comment on #73 is very welcome.

### Still German, and known

Error messages coming from the server are still German in every language — you may see `Error: Account nicht gefunden`. That is tracked in #76 and is the largest remaining gap in the translation.

## [1.5.0] – 2026-09-06

**Risk: safe**

### Portuguese (Brazil), and a login screen that speaks your language (#65, #71)

- The app is now available in **Portuguese (Brazil)**, contributed by [@fitocazo](https://github.com/fitocazo) — their first open-source contribution. Pick it in the language switcher next to 🇩🇪 DE and 🇬🇧 EN.
- The **login screen is translated**. Until now it was German for everyone, in every language — the first screen anyone sees was the one screen the language switch never reached.
- **Login errors say what actually happened**, in your language: a rejected token, too many attempts, or a general failure. Before, a failed login showed whatever the server had said — raw, untranslated, sometimes just `HTTP 429`. The technical detail now goes to the browser console instead of at you.
- On a **first visit** the app follows your browser's language instead of always starting in German.
- `<html lang>` now matches the chosen language, so screen readers and browser translation get it right.

### Dates read as dates (#71)

- Timestamps now spell the month instead of numbering it, in each language:

  |           | before              | now                        |
  | --------- | ------------------- | -------------------------- |
  | Deutsch   | `04.03.2026, 15:30` | `4. März 2026, 15:30`      |
  | English   | `04/03/2026, 15:30` | `4 Mar 2026, 15:30`        |
  | Português | `04/03/2026, 15:30` | `4 de mar. de 2026, 15:30` |

- Why it was worth changing: `04/03/2026` is 4 March to a Brazilian reader and 3 April to an American one, and nothing on screen says which. A spelled-out month cannot be read the wrong way round.
- **A broken timestamp no longer shows as `Invalid Date`.** Album lists, match extension and the sync log now show `–` for a date the server could not deliver — and they all use the same formatting routine, so no corner of the app renders dates its own way any more.

### Also in this release, if you are coming from 1.4.3

Version 1.4.4 was tagged but never rolled out here, so its changes arrive with this one:

- **Sync log retention** (90 days, at most 500 entries) now applies when the log is **read**, not only as a side effect of writing. With auto-sync off, nothing ever expired before.
- Entries with an unreadable timestamp are **kept** rather than silently dropped: a broken clock is not evidence that an entry is old.
- Entries that cannot be turned into a log record at all are skipped on read with a warning and removed on the next write.

### Upgrade notes

- **No data migration.** Rebuild the container so backend and frontend both report `1.5.0`.
- Coming from 1.4.3: sync-log entries older than 90 days disappear from the view after the update, and are removed from disk on the next write. That is the 1.4.4 change above, not a new one.
- Your chosen language is remembered in the browser, per device. Nothing to do.

### Please test

- Switch the language while logged in, and after a fresh reload — the choice should survive both.
- Open the app in a private window with a Portuguese or English browser: the login screen should already be in that language.
- Look at any timestamp in the sync log and the album list — same format, month spelled out.

## [1.4.4] – 2026-08-19

### Sync log retention (#56)

- The retention rule (90 days, at most 500 entries) now applies on **read** as well, not only as a side effect of writing. Previously entries only aged out when a sync action happened to write — with auto-sync off, nothing ever expired.
- Entries whose timestamp cannot be parsed are **kept** instead of silently discarded: a broken clock is not evidence that an entry is old.
- Naive (timezone-less) timestamps are interpreted as UTC instead of raising.
- Entries that cannot be turned into a log record at all (e.g. after a hand-restored `accounts.json`) are skipped on read **with a warning**, and removed on the next write — the store heals itself again.

### Upgrade notes

- No data migration. Sync-log entries older than 90 days disappear from the UI after the update; they are removed from disk on the next write.
- Rebuild the container so backend and frontend both report version `1.4.4`.

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
