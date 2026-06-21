import pytest
from pydantic import ValidationError

from models.account import Account, AccountCreate, AccountPublic


def test_public_account_never_contains_api_key():
    account = Account(
        id="id", name="Family", immich_url="http://192.168.1.2:2283",
        api_key="super-secret", color="#000000",
    )
    public = AccountPublic.from_account(account).model_dump()
    assert "api_key" not in public
    assert public["api_key_configured"] is True


@pytest.mark.parametrize("url", [
    "ftp://192.168.1.2",
    "http://user:pass@192.168.1.2",
    "http://169.254.169.254",
])
def test_unsafe_immich_urls_are_rejected(url):
    with pytest.raises(ValidationError):
        AccountCreate(name="bad", immich_url=url, api_key="key")


def test_private_lan_http_url_is_allowed():
    model = AccountCreate(
        name="home", immich_url="http://192.168.1.2:2283/", api_key="key"
    )
    assert model.immich_url == "http://192.168.1.2:2283"
