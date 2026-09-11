from __future__ import annotations

import base64
import json
from collections.abc import Callable

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import SecretStr

from app.config import Settings
from app.notifications.apns import (
    ApnsConfigurationError,
    ApnsProvider,
    ApnsSendOutcome,
    build_apns_provider,
)


def _private_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def _decode_jwt_part(value: str) -> dict[str, object]:
    padded = value + "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
    result = json.loads(decoded)
    assert isinstance(result, dict)
    return result


def _provider(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[ApnsProvider, httpx.Client]:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = ApnsProvider(
        team_id="TEAM123",
        key_id="KEY123",
        bundle_id="com.fitician.app",
        private_key=_private_key(),
        client=client,
        base_url="https://api.push.apple.com",
    )
    return provider, client


def test_apns_provider_sends_alert_with_signed_provider_token() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, headers={"apns-id": "apns-message-1"})

    provider, client = _provider(handler)
    outcome = provider.send(
        token_value="apns-device-token",
        event_type="plan_approved",
        payload={
            "title": "Plan ready",
            "body": "Your plan is ready.",
            "channel_id": "fitician-activity",
            "data": {"plan_id": "plan-1"},
        },
    )

    assert outcome == ApnsSendOutcome.sent("apns-message-1")
    assert len(requests) == 1
    request = requests[0]
    assert request.url.path == "/3/device/apns-device-token"
    assert request.headers["apns-topic"] == "com.fitician.app"
    assert request.headers["apns-push-type"] == "alert"
    assert request.headers["apns-priority"] == "10"
    authorization = request.headers["authorization"]
    assert authorization.startswith("Bearer ")
    header, claims, signature = authorization.removeprefix("Bearer ").split(".")
    assert _decode_jwt_part(header) == {"alg": "ES256", "kid": "KEY123", "typ": "JWT"}
    decoded_claims = _decode_jwt_part(claims)
    assert decoded_claims["iss"] == "TEAM123"
    assert isinstance(decoded_claims["iat"], int)
    assert signature

    assert json.loads(request.content) == {
        "aps": {
            "alert": {"title": "Plan ready", "body": "Your plan is ready."},
            "sound": "default",
        },
        "event_type": "plan_approved",
        "plan_id": "plan-1",
    }
    client.close()


def test_apns_provider_classifies_invalid_retryable_and_permanent_responses() -> None:
    responses = [
        httpx.Response(410, json={"reason": "Unregistered"}),
        httpx.Response(429, json={"reason": "TooManyRequests"}),
        httpx.Response(400, json={"reason": "PayloadTooLarge"}),
    ]
    provider, client = _provider(lambda _request: responses.pop(0))

    invalid = provider.send(token_value="invalid", event_type="event", payload={})
    retryable = provider.send(token_value="temporary", event_type="event", payload={})
    permanent = provider.send(token_value="valid", event_type="event", payload={})

    assert invalid == ApnsSendOutcome.invalid_token("UNREGISTERED")
    assert retryable == ApnsSendOutcome.retryable("TOOMANYREQUESTS")
    assert permanent == ApnsSendOutcome.permanent("PAYLOADTOOLARGE")
    client.close()


def test_apns_provider_rejects_network_failures_for_retry() -> None:
    provider, client = _provider(
        lambda _request: (_ for _ in ()).throw(httpx.ConnectError("offline")),
    )

    outcome = provider.send(token_value="temporary", event_type="event", payload={})

    assert outcome == ApnsSendOutcome.retryable("NETWORK_ERROR")
    client.close()


def test_apns_private_key_serialization_is_compatible_with_provider_input() -> None:
    key = _private_key()
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    loaded = serialization.load_pem_private_key(pem, password=None)

    assert isinstance(loaded, ec.EllipticCurvePrivateKey)


def test_build_apns_provider_loads_a_protected_pem_key() -> None:
    pem = _private_key().private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    settings = Settings(
        notification_apns_enabled=True,
        notification_apns_team_id="TEAM123",
        notification_apns_key_id="KEY123",
        notification_apns_private_key=SecretStr(pem.decode("utf-8")),
    )

    provider = build_apns_provider(settings)

    assert isinstance(provider, ApnsProvider)
    provider.close()


def test_build_apns_provider_fails_closed_when_enabled_configuration_is_incomplete() -> None:
    settings = Settings(notification_apns_enabled=True)

    try:
        build_apns_provider(settings)
    except ApnsConfigurationError as error:
        assert str(error) == "APNs provider configuration is missing"
    else:
        raise AssertionError("Expected incomplete APNs configuration to fail")
