from pydantic import BaseModel
from typing import Optional
from enum import Enum


class MatchReason(str, Enum):
    name_similarity = "name_similarity"
    embedding_similarity = "embedding_similarity"
    shared_assets = "shared_assets"
    manual = "manual"


class MatchStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    dismissed = "dismissed"


class PersonRef(BaseModel):
    person_id: str
    person_name: Optional[str]
    account_id: str
    account_name: str
    account_color: str


class Match(BaseModel):
    id: str  # deterministic: sorted(personA_id, personB_id) joined
    person_a: PersonRef
    person_b: PersonRef
    confidence: float  # 0.0 – 1.0
    reasons: list[MatchReason]
    status: MatchStatus = MatchStatus.pending
    # Enriched fields (set by router, not by face_matcher)
    has_album: bool = False
    names_synced: bool = False


class ManagedAlbum(BaseModel):
    """An album created and managed by this tool."""
    id: str                      # internal UUID
    match_id: str                # original match or manual ID
    album_id: str                # Immich album UUID (in owner account)
    album_name: str
    owner_account_id: str        # account that owns the album
    person_refs: list[dict]      # [{"account_id", "person_id", "person_name", "account_name", "account_color"}]
    linked_match_ids: list[str] = []  # MD5 IDs for every person-pair in this album
    created_at: str
    last_synced_at: Optional[str] = None
    total_assets: int = 0


class SyncNamesRequest(BaseModel):
    match_id: str
    name: str  # The canonical name to set on both persons


class MultiSyncPersonEntry(BaseModel):
    account_id: str
    person_id: str


class SyncNamesMultiRequest(BaseModel):
    persons: list[MultiSyncPersonEntry]        # one entry per account, min 2
    canonical_name: str
    album_name: Optional[str] = None           # if set, create new shared album
    existing_album_id: Optional[str] = None    # if set, link existing album instead
    owner_account_id: Optional[str] = None     # album owner; defaults to first person's account


class ExtendMatchRequest(BaseModel):
    managed_album_id: str     # which ManagedAlbum to extend
    account_id: str           # new account to add
    person_id: str            # person in that account
    person_name: Optional[str] = None     # display name of the person (for person_refs)
    canonical_name: Optional[str] = None  # if set, rename person to this


class SyncAlbumRequest(BaseModel):
    match_id: str
    owner_account_id: str
    album_name: Optional[str] = None        # for new album
    existing_album_id: Optional[str] = None # for linking existing album


class SyncLogEntry(BaseModel):
    id: str
    timestamp: str
    action: str
    details: str
    status: str  # "success" | "error"
    error_message: Optional[str] = None
    undo_data: Optional[dict] = None
