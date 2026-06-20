import time

from services.auth_service import create_session, verify_session


def test_signed_session_roundtrip():
    token = create_session("a-long-secret", 60)
    assert verify_session(token, "a-long-secret")
    assert not verify_session(token, "wrong-secret")


def test_expired_or_malformed_session_is_rejected():
    assert not verify_session(create_session("secret", -1), "secret")
    assert not verify_session("not-a-session", "secret")
    assert not verify_session(None, "secret")
