# Backup and Restore

## Backup

1. Snapshot the ZFS dataset containing `/app/data`.
2. Replicate snapshots to a protected second target.
3. Ensure both `accounts.json` and `accounts.json.bak` remain readable only by
   UID/GID 3006 (`0600`; directory `0700`).
4. Treat every backup as a secret because it contains Immich API keys.

## Restore

1. Stop the container.
2. Restore a known-good ZFS snapshot or copy `accounts.json.bak` to
   `accounts.json`.
3. Reapply ownership `3006:3006`, directory mode `0700`, and file mode `0600`.
4. Start the container and verify `/api/health`.
5. Log in and test account status before running synchronization.

Test restoration after setup and periodically thereafter. An untested backup is
only a hopeful collection of bytes.
