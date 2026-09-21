# Backup and Restore

> Betriebs-Bausatz (terminierte Rückspiel-Probe, Totmann-Schalter,
> Erreichbarkeits-Wächter) siehe `docs/betrieb/` — vorbereitet, noch nicht
> installiert (Issue #54).

## Backup

1. Snapshot the ZFS dataset containing `/app/data`.
2. Replicate snapshots to a protected second target.
3. Ensure `accounts.json`, `accounts.json.bak` **and any
   `accounts.json.vor-schema-*.bak`** remain readable only by UID/GID 3006
   (`0600`; directory `0700`).
4. Treat every backup as a secret because it contains Immich API keys. This
   applies to the `vor-schema-*` files too — and to them for longer, because
   nothing overwrites or removes them (see _Schema migrations_ below).

## Schema migrations

The app writes a rollback copy before anything it cannot undo. There are two,
and they behave differently on purpose:

- **`accounts.json.vor-schema-<N>.bak`** — written **once** before a schema
  migration and never overwritten while it is usable. `<N>` is the schema
  version it is migrating **to**; the file holds the state from _before_ that
  migration.
- **`accounts.json.vor-kennungsvergabe.bak`** — written before the app assigns
  album group identifiers **without** a schema change. That happens when an
  older version created an album without one. **One generation only:** it is
  replaced on each such run, so it always holds the state from before the
  _most recent_ one. That is the state you would want back; a months-old copy
  would throw away everything since.

**This is the file you want after a migration, not `accounts.json.bak`.** The
ordinary `.bak` is rewritten on every save — including by the account backfill
that runs at startup, seconds after the migration. It stops being the
pre-migration state almost immediately.

Two things follow for you as the operator:

- **After you have confirmed an upgrade is good**, delete the rollback copies
  you no longer need. Nothing rotates the `vor-schema-*` files, and both kinds
  keep Immich API keys — including keys of accounts you have since deleted
  from the app, and log entries past the 90-day retention window. `PRIVACY.md`
  points here for that reason.
- If the file is missing after an upgrade, the migration still ran. Check the
  container log for `Sicherung vor Schemasprung nicht moeglich`; a failed
  backup does not stop the app, by design.

## Restore

1. Stop the container.
2. Restore a known-good ZFS snapshot. **To undo a migration, that is not
   enough on its own** — see _Undoing a migration_ below.
3. Reapply ownership `3006:3006`, directory mode `0700`, and file mode `0600`.
4. Start the container and verify `/api/health`.
5. Log in and test account status before running synchronization.

## Undoing a migration

**Roll the image back first.** Restoring the pre-migration file alone does not
work: the same container migrates again the moment it starts — and assigns
_new, different_ group identifiers while doing so. Measured. The naive
sequence is not merely useless; it moves the identifiers a second time.

The order that works:

1. Stop the container.
2. Deploy the **previous image tag**, the one from before the upgrade.
3. Copy the matching rollback copy over `accounts.json`:
   `accounts.json.vor-schema-<N>.bak` for a schema migration,
   `accounts.json.vor-kennungsvergabe.bak` for an identifier assignment. Only
   if neither exists, fall back to `accounts.json.bak` — it may already carry
   the migrated state.
4. Reapply ownership `3006:3006`, directory `0700`, file `0600`.
5. Start the old image and verify `/api/health` reports the old version.

Only then decide whether to upgrade again.

Test restoration after setup and periodically thereafter. An untested backup is
only a hopeful collection of bytes.
