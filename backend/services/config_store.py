"""
Persistent config storage: accounts + dismissed match IDs + sync log + managed albums.
Backed by a JSON file on the Docker volume.
"""
import hashlib
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path
from typing import Optional

from models.account import Account, AccountCreate
from models.match import ManagedAlbum, SyncLogEntry

logger = logging.getLogger(__name__)


class ConfigStore:
    SCHEMA_VERSION = 2

    def __init__(self, path: str, log_retention_days: int = 90):
        self._path = Path(path)
        self._log_retention_days = log_retention_days
        self._data: dict = {
            "schema_version": self.SCHEMA_VERSION,
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
                if not isinstance(self._data, dict) or not isinstance(self._data.get("accounts", {}), dict):
                    raise ValueError("invalid configuration schema")
                self._data.setdefault("managed_albums", [])
                logger.info("Config loaded from %s", self._path)
                self._migrate()
            except Exception as exc:
                raise RuntimeError(
                    f"Configuration {self._path} is invalid and was left untouched. "
                    f"Restore {self._path}.bak or a ZFS snapshot."
                ) from exc

    def _migrate(self) -> None:
        """One-time repair of managed_albums: fill missing fields from live account data."""
        accounts = self._data.get("accounts", {})
        albums = self._data.get("managed_albums", [])
        changed = False
        if self._data.get("schema_version") != self.SCHEMA_VERSION:
            self._data["schema_version"] = self.SCHEMA_VERSION
            changed = True
        self._data.setdefault("accounts", {})
        self._data.setdefault("dismissed_match_ids", [])
        self._data.setdefault("synced_name_match_ids", [])
        self._data.setdefault("sync_log", [])
        self._data.setdefault("auto_sync", {"enabled": False, "time": "01:00"})

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
        try:
            os.chmod(self._path.parent, 0o700)
        except OSError:
            logger.warning("Could not enforce 0700 on %s", self._path.parent)
        payload = json.dumps(self._data, indent=2, ensure_ascii=False)
        fd, temp_name = tempfile.mkstemp(prefix=f".{self._path.name}.", dir=self._path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_name, 0o600)
            if self._path.exists():
                shutil.copy2(self._path, f"{self._path}.bak")
                os.chmod(f"{self._path}.bak", 0o600)
            os.replace(temp_name, self._path)
            os.chmod(self._path, 0o600)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

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
        account_name = self._data["accounts"][account_id].get("name", "")
        del self._data["accounts"][account_id]
        cleaned_albums = []
        for album in self._data.get("managed_albums", []):
            album["person_refs"] = [
                ref for ref in album.get("person_refs", [])
                if ref.get("account_id") != account_id
            ]
            if len(album["person_refs"]) >= 2:
                album["linked_match_ids"] = self.compute_linked_match_ids(album["person_refs"])
                cleaned_albums.append(album)
        self._data["managed_albums"] = cleaned_albums
        self._data["dismissed_match_ids"] = []
        self._data["synced_name_match_ids"] = []
        self._data["sync_log"] = [
            entry for entry in self._data.get("sync_log", [])
            if (entry.get("undo_data") or {}).get("account_id") != account_id
            and (not account_name or account_name not in entry.get("details", ""))
        ]
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

    def _apply_log_retention(self, entries: list[dict]) -> list[dict]:
        """Apply the configured retention window (`log_retention_days`) and the
        500-entry cap to a list of raw sync-log dicts. Used by both the write
        path (`append_log`) and the read path (`get_log`) so the rule holds
        regardless of whether a write ever happens.

        An entry with a missing or unparseable timestamp is kept rather than
        dropped — a broken timestamp is not evidence the entry is old, and
        silently discarding a log entry because we can't read its clock is
        exactly the kind of quiet data loss this store avoids elsewhere.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._log_retention_days)
        retained = []
        for entry in entries:
            try:
                timestamp = datetime.fromisoformat(entry["timestamp"])
            except (KeyError, TypeError, ValueError):
                retained.append(entry)
                continue
            if timestamp >= cutoff:
                retained.append(entry)
        return retained[-500:]

    def append_log(self, entries: list[SyncLogEntry]) -> None:
        log = self._data.setdefault("sync_log", [])
        log.extend(e.model_dump() for e in entries)
        self._data["sync_log"] = self._apply_log_retention(log)
        self._save()

    def get_log(self) -> list[SyncLogEntry]:
        # Retention is enforced on read too, not just as a side effect of
        # append_log — otherwise entries only age out when something is
        # written, which is not what "retained for 90 days" promises. This
        # does NOT persist the filtered result: get_log() backs GET
        # /api/sync/log, which the frontend polls every 30s, and rewriting
        # the project's one JSON file on every poll would be a bad trade for
        # pruning a handful of already-invisible, already-capped rows.
        filtered = self._apply_log_retention(self._data.get("sync_log", []))
        return [SyncLogEntry(**e) for e in filtered]

    def clear_log(self) -> None:
        self._data["sync_log"] = []
        self._save()

    def mark_log_undone(self, entry_id: str, undone_at: str) -> None:
        for entry in self._data.get("sync_log", []):
            if entry.get("id") == entry_id:
                entry["undone_at"] = undone_at
                self._save()
                return

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
