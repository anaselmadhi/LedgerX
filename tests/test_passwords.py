import pytest
from pydantic import ValidationError

from app.core.security import hash_password, issue_token, token_digest, verify_password
from app.schemas.auth import Credentials


def test_password_hash_is_salted_and_verifies():
    password = "correct horse battery staple"
    first, second = hash_password(password), hash_password(password)
    assert first != second
    assert password not in first
    assert verify_password(password, first)
    assert not verify_password("wrong password", first)
    assert not verify_password(password, "scrypt$999999999$8$3$00$00")
    assert not verify_password(password, "disabled")


def test_tokens_are_random_and_only_digest_is_persisted():
    first, digest = issue_token()
    second, _ = issue_token()
    assert len(first) == 43
    assert first != second
    assert token_digest(first) == digest
    assert first != digest


@pytest.mark.parametrize("password", ["short", "x" * 129])
def test_password_length(password):
    with pytest.raises(ValidationError):
        Credentials(username="customer", password=password)


def test_credentials_hide_password_and_normalize_username():
    credentials = Credentials(username="Alice", password="secret-password-123")
    assert credentials.username == "alice"
    assert "secret-password-123" not in repr(credentials)
