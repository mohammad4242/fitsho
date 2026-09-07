from __future__ import annotations

import json

import httpx

from app.notifications.fcm import FcmProvider, FcmSendOutcome


class FakeCredentials:
    token = "access-token"
    expired = False

    def refresh(self, _request) -> None:
        self.token = "refreshed-access-token"


def test_fcm_provider_sends_a_v1_message_with_string_data() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"name": "projects/fitician/messages/123"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = FcmProvider(
        project_id="fitician-project",
        credentials=FakeCredentials(),
        client=client,
        base_url="https://fcm.googleapis.com",
    )

    outcome = provider.send(
        token_value="native-token",
        event_type="plan_approved",
        payload={
            "title": "Plan ready",
            "body": "Your plan is ready.",
            "channel_id": "fitician-activity",
            "deep_link": "/workouts",
            "revision": 3,
        },
    )

    assert outcome == FcmSendOutcome.sent("projects/fitician/messages/123")
    assert len(requests) == 1
    request = requests[0]
    assert request.url.path == "/v1/projects/fitician-project/messages:send"
    assert request.headers["authorization"] == "Bearer access-token"
    body = json.loads(request.content)
    assert body["message"]["token"] == "native-token"
    assert body["message"]["notification"] == {
        "title": "Plan ready",
        "body": "Your plan is ready.",
    }
    assert body["message"]["data"] == {
        "event_type": "plan_approved",
        "deep_link": "/workouts",
        "revision": "3",
    }
    assert body["message"]["android"] == {
        "notification": {"channel_id": "fitician-activity"},
    }
    client.close()


def test_fcm_provider_classifies_invalid_token_and_transient_failures() -> None:
    responses = [
        httpx.Response(
            400,
            json={
                "error": {
                    "status": "INVALID_ARGUMENT",
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError",
                            "errorCode": "UNREGISTERED",
                        }
                    ],
                }
            },
        ),
        httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}}),
    ]
    client = httpx.Client(transport=httpx.MockTransport(lambda _request: responses.pop(0)))
    provider = FcmProvider(
        project_id="fitician-project",
        credentials=FakeCredentials(),
        client=client,
        base_url="https://fcm.googleapis.com",
    )

    invalid = provider.send(token_value="bad-token", event_type="event", payload={})
    retryable = provider.send(token_value="temporary-token", event_type="event", payload={})

    assert invalid == FcmSendOutcome.invalid_token("UNREGISTERED")
    assert retryable == FcmSendOutcome.retryable("UNAVAILABLE")
    client.close()
