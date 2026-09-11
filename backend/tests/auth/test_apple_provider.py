import base64
import json
import time
from collections.abc import Mapping

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.auth.providers import AppleIdTokenProvider
from app.config import Settings


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _jwk(public_key: rsa.RSAPublicKey, kid: str = "apple-test") -> dict[str, str]:
    numbers = public_key.public_numbers()
    return {
        "alg": "RS256",
        "e": _base64url(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
        "kid": kid,
        "kty": "RSA",
        "n": _base64url(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
        "use": "sig",
    }


def _token(
    private_key: rsa.RSAPrivateKey,
    *,
    nonce: str = "nonce-1",
    subject: str = "apple-sub-1",
    issuer: str = "https://appleid.apple.com",
    audience: str = "com.fitician.app",
    expires_at: int | None = None,
    kid: str = "apple-test",
    email: str = "member@privaterelay.appleid.com",
) -> str:
    header = {"alg": "RS256", "kid": kid, "typ": "JWT"}
    claims = {
        "aud": audience,
        "email": email,
        "email_verified": "true",
        "exp": expires_at or int(time.time()) + 300,
        "iat": int(time.time()),
        "iss": issuer,
        "nonce": nonce,
        "sub": subject,
    }
    encoded_header = _base64url(json.dumps(header, separators=(",", ":")).encode())
    encoded_claims = _base64url(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{encoded_header}.{encoded_claims}.{_base64url(signature)}"


@pytest.fixture
def apple_material() -> tuple[rsa.RSAPrivateKey, Mapping[str, Mapping[str, str]]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, {"apple-test": _jwk(private_key.public_key())}


def _provider(jwks: Mapping[str, Mapping[str, str]]) -> AppleIdTokenProvider:
    return AppleIdTokenProvider(
        Settings(app_env="test", apple_client_id="com.fitician.app"),
        jwks_fetcher=lambda: jwks,
    )


def test_verifies_signed_apple_identity_and_private_relay_email(
    apple_material: tuple[rsa.RSAPrivateKey, Mapping[str, Mapping[str, str]]],
) -> None:
    private_key, jwks = apple_material

    identity = _provider(jwks).verify(_token(private_key), nonce="nonce-1")

    assert identity.sub == "apple-sub-1"
    assert identity.email == "member@privaterelay.appleid.com"
    assert identity.email_verified is True


@pytest.mark.parametrize(
    ("claim", "value", "nonce"),
    [
        ("issuer", "https://evil.example", "nonce-1"),
        ("audience", "another-client", "nonce-1"),
        ("expires_at", int(time.time()) - 60, "nonce-1"),
        ("nonce", "different-nonce", "nonce-1"),
    ],
)
def test_rejects_invalid_apple_claims(
    apple_material: tuple[rsa.RSAPrivateKey, Mapping[str, Mapping[str, str]]],
    claim: str,
    value: str | int,
    nonce: str,
) -> None:
    private_key, jwks = apple_material
    kwargs: dict[str, str | int] = {claim: value}
    token = _token(private_key, **kwargs)

    with pytest.raises(ValueError):
        _provider(jwks).verify(token, nonce=nonce)


def test_rejects_tampered_apple_signature(
    apple_material: tuple[rsa.RSAPrivateKey, Mapping[str, Mapping[str, str]]],
) -> None:
    private_key, jwks = apple_material
    token = _token(private_key)
    header, claims, signature = token.split(".")
    tampered = f"{header}.{claims}.{signature[:-1]}A"

    with pytest.raises(ValueError):
        _provider(jwks).verify(tampered, nonce="nonce-1")


def test_refreshes_jwks_once_for_an_unknown_key_id(
    apple_material: tuple[rsa.RSAPrivateKey, Mapping[str, Mapping[str, str]]],
) -> None:
    private_key, jwks = apple_material
    calls = 0

    def fetch_jwks() -> Mapping[str, Mapping[str, str]]:
        nonlocal calls
        calls += 1
        return jwks

    provider = AppleIdTokenProvider(
        Settings(app_env="test", apple_client_id="com.fitician.app"),
        jwks_fetcher=fetch_jwks,
    )
    token = _token(private_key, kid="unknown-kid")

    with pytest.raises(ValueError):
        provider.verify(token, nonce="nonce-1")

    assert calls == 2
