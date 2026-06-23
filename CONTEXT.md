# Immich Family Tools

A companion app for self-hosted Immich installations with multiple user accounts. It bridges the gap where Immich builds a separate face database per account — even when all accounts belong to the same family and share the same people.

## Language

### Accounts & People

**Account**:
One Immich user account registered in this tool, identified by its URL and API key.
_Avoid_: User, instance, profile

**Person**:
A face cluster within a single Account, as recognised and managed by Immich. A Person may have a name or be unnamed.
_Avoid_: Face, contact, profile

**Unnamed Person**:
A Person Immich has recognised but not yet named. Unnamed Persons are excluded from automatic matching and can only be linked manually.
_Avoid_: Unknown person, untagged face

### Matching

**Automatic Match**:
A candidate pairing of two Persons from different Accounts, computed by the tool using face embeddings and/or name similarity. An Automatic Match has a confidence score and can be accepted or dismissed.
_Avoid_: Suggestion, detection, result

**Manual Match**:
A pairing of two or more Persons across Accounts created explicitly by the user — for cases the automatic matcher missed or where no embeddings are available.
_Avoid_: Custom match, override

**Confidence**:
A 0.0–1.0 score attached to an Automatic Match indicating how likely the two Persons are the same individual. Derived from embedding similarity (weight 0.70) and name similarity (weight 0.30). A name-only match tops out at 0.75 by design.
_Avoid_: Score, probability, certainty

**Dismissed Match**:
An Automatic Match the user has marked as incorrect. Dismissed Matches are hidden from the suggestions view and not re-suggested.
_Avoid_: Rejected match, ignored match

### Synchronisation

**Unified Name**:
The single name set on all matched Persons across their respective Accounts. Setting a Unified Name is an explicit user action, not an automatic consequence of matching.
_Avoid_: Canonical name, shared name, common name

**Name Sync**:
The action of writing a Unified Name to every Person in a Match or Managed Album via each Account's own API key.
_Avoid_: Rename, update name

**Shared Album**:
An Immich album created by this tool in one Account (the owner) and shared with all other participating Accounts. Contains all photos of the matched Person from every Account.
_Avoid_: Joint album, merged album, family album

**Managed Album**:
The tool's internal record of a Shared Album — tracking which Persons from which Accounts participate, the owner Account, sync state, and history. A Managed Album persists even if the underlying Immich album is deleted.
_Avoid_: Tracked album, linked album

**Sync Log**:
An append-only audit trail of every Name Sync and album operation performed by the tool. Entries support undo for Name Sync actions.
_Avoid_: History, activity log, changelog
