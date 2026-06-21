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

Removing an account clears its local data and caches. It does not delete photos,
people, albums, or users in Immich.

## Operator responsibility

The operator determines the lawful purpose, access permissions, backup policy,
and whether household-use exemptions apply. Face embeddings used to identify a
person may be biometric data. This document is technical information, not legal
advice.
