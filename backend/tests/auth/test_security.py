import re

import pytest

from app.auth import security
from app.auth.security import (
    hash_password,
    hash_session_token,
    make_session_token,
    verify_password,
)


def test_password_is_hashed_and_verifiable() -> None:
    password = "correct horse battery staple"

    encoded = hash_password(password)

    assert encoded != password
    assert verify_password(password, encoded)
    assert not verify_password("wrong password", encoded)


def test_session_tokens_are_random_and_only_digest_is_stable() -> None:
    raw_one, digest_one = make_session_token()
    raw_two, digest_two = make_session_token()

    assert raw_one != raw_two
    assert digest_one != digest_two
    assert digest_one == hash_session_token(raw_one)
    assert raw_one not in digest_one
    assert len(digest_one) == 64


@pytest.mark.parametrize(
    "raw_phone",
    ["09123456789", "+989123456789", "00989123456789"],
)
def test_iranian_phone_normalization_accepts_supported_forms(raw_phone: str) -> None:
    assert security.normalize_iranian_phone(raw_phone) == "+989123456789"


@pytest.mark.parametrize("raw_phone", ["", "9123456789", "+981212345678", "0912345678a"])
def test_iranian_phone_normalization_rejects_invalid_numbers(raw_phone: str) -> None:
    with pytest.raises(ValueError, match="Iranian mobile"):
        security.normalize_iranian_phone(raw_phone)


def test_password_reset_tokens_are_random_and_only_the_digest_is_stable() -> None:
    raw_one, digest_one = security.make_password_reset_token()
    raw_two, digest_two = security.make_password_reset_token()

    assert raw_one != raw_two
    assert digest_one != digest_two
    assert security.hash_password_reset_token(raw_one) == digest_one
    assert raw_one not in digest_one
    assert len(digest_one) == 64


def test_otp_is_random_six_digits_and_hashed_with_backend_secret() -> None:
    code_one = security.make_otp_code()
    code_two = security.make_otp_code()
    digest = security.hash_otp_code("+989123456789", code_one, "test-secret")

    assert re.fullmatch(r"\d{6}", code_one)
    assert re.fullmatch(r"\d{6}", code_two)
    assert digest != code_one
    assert len(digest) == 64
    assert security.hash_otp_code("+989123456789", code_one, "test-secret") == digest
    assert security.hash_otp_code("+989123456789", code_one, "other-secret") != digest
