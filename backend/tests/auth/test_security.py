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
