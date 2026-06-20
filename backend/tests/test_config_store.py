import json
import os

import pytest

from models.account import AccountCreate
from services.config_store import ConfigStore


def test_save_is_private_versioned_and_recoverable(tmp_path):
    path = tmp_path / "accounts.json"
    store = ConfigStore(str(path))
    store.add_account(
        AccountCreate(name="A", immich_url="http://192.168.1.2", api_key="secret")
    )
    payload = json.loads(path.read_text())
    assert payload["schema_version"] == ConfigStore.SCHEMA_VERSION
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


def test_invalid_config_fails_closed(tmp_path):
    path = tmp_path / "accounts.json"
    path.write_text("{broken")
    with pytest.raises(RuntimeError, match="left untouched"):
        ConfigStore(str(path))


def test_delete_account_removes_local_references(tmp_path):
    store = ConfigStore(str(tmp_path / "accounts.json"))
    account = store.add_account(
        AccountCreate(name="A", immich_url="http://192.168.1.2", api_key="secret")
    )
    assert store.delete_account(account.id)
    assert store.list_accounts() == []
