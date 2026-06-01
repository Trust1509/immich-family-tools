"""
Persistent config storage: accounts + dismissed match IDs + sync log + managed albums.
Backed by a JSON file on the Docker volume.
"""
import hashlib
import json
import logging
from itertools import combinations
from pathlib import Path
from typing import Optional

from models.account import Account, AccountCreate
from models.match import ManagedAlbum, SyncLogEntry

logger = logging.getLogger(__name__)


class ConfigStore:
    def __init__(self, path: str):
        self._path = Path(path)
        self._data: dict = {
            "accounts": {},
            "dismissed_match_ids": [],
            "sync_log": [],
            "managed_albums": [],
        }
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def pair_match_id(id_a: str, id_b: str) -> str:
        """Same algorithm as face_matcher._match_id — keep in sync."""
        key = "_".join(sorted([id_a, id_b]))
        return hashlib.md5(key.encode()).hexdigest()

    @staticmethod
    def compute_linked_match_ids(person_refs: list[dict]) -> list[str]:
        """All pairwise MD5 match IDs for the persons in an album."""
        ids = [r["person_id"] for r in person_refs if r.get("person_id")]
        return [
            ConfigStore.pair_match_id(a, b)
            for a, b in combinations(ids, 2)
        ]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
                self._data.setdefault("managed_albums", [])
                logger.info("Config loaded from %s", self._path)
                self._migrate()
            except Exception as exc:
                logger.error("Failed to load config: %s – starting fresh", exc)

    def _migrate(self) -> None:
        """One-time repair of managed_albums: fill missing fields from live account data."""
        accounts = self._data.get("accounts", {})
        albums = self._data.get("managed_albums", [])
        changed = False

        for album in albums:
            album_name = album.get("album_name", "")

            for ref in album.get("person_refs", []):
                acc = accounts.get(ref.get("account_id", ""), {})
                # Fill account_color from live accounts dict
                if acc and not ref.get("account_color"):
                    ref["account_color"] = acc.get("color", "#6366f1")
                    changed = True
                # Fill account_name from live accounts dict
                if acc and not ref.get("account_name"):
                    ref["account_name"] = acc.get("name", "")
                    changed = True
                # Fill person_name with album_name as canonical fallback
                if not ref.get("person_name"):
                    ref["person_name"] = album_name
                    changed = True

            # Recompute linked_match_ids — always authoritative
            computed = self.compute_linked_match_ids(album.get("person_refs", []))
            if set(album.get("linked_match_ids", [])) != set(computed):
                album["linked_match_ids"] = computed
                changed = True

        if changed:
            logger.info("Config migration applied; saving.")
            self._save()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    def list_accounts(self) -> list[Account]:
        return [Account(**v) for v in self._data["accounts"].values()]

    def get_account(self, account_id: str) -> Optional[Account]:
        raw = self._data["accounts"].get(account_id)
        return Account(**raw) if raw else None

    def add_account(self, data: AccountCreate, user_id: Optional[str] = None) -> Account:
        account = Account.from_create(data)
        account.user_id = user_id
        self._data["accounts"][account.id] = account.model_dump()
        self._save()
        return account

    def update_account(self, account_id: str, updates: dict) -> Optional[Account]:
        raw = self._data["accounts"].get(account_id)
        if not raw:
            return None
        raw.update({k: v for k, v in updates.items() if v is not None})
        self._save()
        return Account(**raw)

    def delete_account(self, account_id: str) -> bool:
        if account_id not in self._data["accounts"]:
            return False
        del self._data["accounts"][account_id]
        self._save()
        return True

    # ------------------------------------------------------------------
    # Dismissed matches
    # ------------------------------------------------------------------

    def get_dismissed_ids(self) -> set[str]:
        return set(self._data.get("dismissed_match_ids", []))

    def dismiss_match(self, match_id: str) -> None:
        ids = self._data.setdefault("dismissed_match_ids", [])
        if match_id not in ids:
            ids.append(match_id)
            self._save()

    def undismiss_match(self, match_id: str) -> None:
        ids = self._data.get("dismissed_match_ids", [])
        if match_id in ids:
            ids.remove(match_id)
            self._save()

    # ------------------------------------------------------------------
    # Explicitly synced name matches
    # ------------------------------------------------------------------

    def get_synced_name_ids(self) -> set[str]:
        return set(self._data.get("synced_name_match_ids", []))

    def mark_all_pairs_synced(self, person_ids: list[str]) -> None:
        """Mark every pairwise combination of person_ids as names-synced."""
        for a, b in combinations(person_ids, 2):
            self.mark_names_synced(self.pair_match_id(a, b))

    def mark_names_synced(self, match_id: str) -> None:
        ids = self._data.setdefault("synced_name_match_ids", [])
        if match_id not in ids:
            ids.append(match_id)
            self._save()

    # ------------------------------------------------------------------
    # Sync log
    # ------------------------------------------------------------------

    def append_log(self, entries: list[SyncLogEntry]) -> None:
        log = self._data.setdefault("sync_log", [])
        log.extend(e.model_dump() for e in entries)
        self._data["sync_log"] = log[-500:]
        self._save()

    def get_log(self) -> list[SyncLogEntry]:
        return [SyncLogEntry(**e) for e in self._data.get("sync_log", [])]

    # ------------------------------------------------------------------
    # Managed albums
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Auto-sync config
    # ------------------------------------------------------------------

    def get_auto_sync_config(self) -> dict:
        """Returns {"enabled": bool, "time": "HH:MM"}."""
        return dict(self._data.setdefault("auto_sync", {"enabled": False, "time": "01:00"}))

    def set_auto_sync_config(self, enabled: bool, time: str) -> None:
        self._data["auto_sync"] = {"enabled": enabled, "time": time}
        self._save()

    # ------------------------------------------------------------------
    # Managed albums
    # ------------------------------------------------------------------

    def get_managed_albums(self) -> list[ManagedAlbum]:
        return [ManagedAlbum(**a) for a in self._data.get("managed_albums", [])]

    def add_managed_album(self, album: ManagedAlbum) -> None:
        # Always compute linked_match_ids before saving
        album.linked_match_ids = self.compute_linked_match_ids(album.person_refs)
        albums = self._data.setdefault("managed_albums", [])
        albums.append(album.model_dump())
        self._save()

    def update_managed_album(self, album: ManagedAlbum) -> None:
        # Always recompute linked_match_ids before saving
        album.linked_match_ids = self.compute_linked_match_ids(album.person_refs)
        albums = self._data.get("managed_albums", [])
        for i, a in enumerate(albums):
            if a["id"] == album.id:
                albums[i] = album.model_dump()
                self._save()
                return

    def delete_managed_album(self, album_id: str) -> bool:
        albums = self._data.get("managed_albums", [])
        new_albums = [a for a in albums if a["id"] != album_id]
        if len(new_albums) == len(albums):
            return False
        self._data["managed_albums"] = new_albums
        self._save()
        return True
