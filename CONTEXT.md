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

### Album Groups

_Decisions of the owner recorded here are dated and link their issue. They are requirements, not acceptance criteria — a build still has to think them through against the existing data (question 10 in `docs/agents/bau-brief.md`)._

**Album Group**:
A set of Managed Albums — usually one per Account — that count as one family album. An Album Group is identified by its own **group id** (since 1.7.0). Membership hangs on the group id, never on a name; renaming an album, in the tool or in Immich, cannot move it to another group.
_Avoid_: Album set, album cluster, name group

**Group Name**:
The label shown for an Album Group. It is a label, not an identity: **two different Album Groups may carry the same name** (owner decision 2026-09-28, #98). The tool never refuses a rename or a creation because another group already uses the name.
_Avoid_: Group key, group identifier

**Group Suggestion**:
When the user types a name for a new album, the tool suggests the Album Group that name belongs to — compared the way a person reads names (case, surrounding blanks and Unicode encoding do not count, #83). If a name belongs to more than one group, **no group is suggested**; the user chooses explicitly, including "new group" (#81). A suggestion is a proposal the user sees and can overrule, never a silent assignment. Creating is blocked until the preview has answered for the **current** input (#110). **If the preview fails, creating stays blocked too** — a "retry" control re-asks, no fail-open — because the preview runs against the same server as creating itself, and a stale or wrong grouping slipping through unseen is worse than a moment's wait (owner decision 2026-09-28, #110, Nacharbeit 1).
_Avoid_: Auto-grouping, group match

**Album Name Source**:
**The name in Immich wins.** When the tool refreshes a Managed Album, it adopts the album's current name from Immich; a rename done directly in Immich shows up in the tool (owner decision 2026-09-28, #97). Because every Account holds its own album, the albums of one Album Group may carry different names afterwards — that is allowed, the group stays one group.
_Avoid_: Master name, canonical album name

**Orphaned Managed Album**:
A Managed Album whose owner Account has been removed from the tool. The album still exists in Immich, but the tool no longer holds the key that may change it. It stays visible, marked as orphaned; renaming and syncing are refused with a message that says why; removing it from the tool is allowed (owner decision 2026-09-28, #99). Nothing about it disappears silently.
_Avoid_: Dangling album, ownerless album

**Manual Match Identity**:
A Manual Match is identified by its name and its owner Account. Two Manual Matches with the same name and owner but different Persons are **refused** with a message that says so — whoever wants two such groups gives one of them another name (owner decision 2026-09-28, #96). This is the one place where a name still has to be unique, and only within one owner and only for Manual Matches.
_Avoid_: Manual group key
