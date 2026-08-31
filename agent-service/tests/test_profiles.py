from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app
from app.profiles import (
    AgentTaskKind,
    ProfileCatalog,
    ReasoningEffort,
    antigravity_profiles_from_output,
    profile_id_for,
)
from app.runners.base import AgentRunner, RunnerRequest, RunnerResult
from app.runners.registry import RunnerRegistry
from app.schemas import AgentName, AuthState, RunnerCapabilities, RunnerModelCapabilities


def test_antigravity_catalog_parses_bounded_model_rows() -> None:
    output = """
    gemini-3.7-flash-high  Gemini 3.7 Flash (High)
    gemini-3.7-flash-low   Gemini 3.7 Flash (Low)
    unknown value with spaces
    """

    profiles = antigravity_profiles_from_output(output, version="agy 1.1.22")

    assert [profile.model_id for profile in profiles] == [
        "gemini-3.7-flash-high",
        "gemini-3.7-flash-low",
    ]
    assert profiles[0].display_name == "Gemini 3.7 Flash (High)"
    assert AgentTaskKind.BODY_PHOTO_ANALYSIS in profiles[0].task_kinds


def test_profile_id_is_stable_and_combines_model_and_effort() -> None:
    assert profile_id_for(AgentName.CODEX, "gpt-5.6-luna", ReasoningEffort.HIGH) == (
        "codex-gpt-5.6-luna-high"
    )


def test_catalog_rejects_unknown_profile_before_runner_execution() -> None:
    catalog = ProfileCatalog(
        profiles=antigravity_profiles_from_output(
            "gemini-3.7-flash-high Gemini 3.7 Flash (High)", version="agy 1.1.22"
        )
    )

    with pytest.raises(KeyError):
        catalog.resolve(AgentName.ANTIGRAVITY, "antigravity-not-allow-listed")


def test_catalog_fingerprint_changes_with_runner_version() -> None:
    first = antigravity_profiles_from_output(
        "gemini-3.7-flash-high Gemini 3.7 Flash (High)", version="agy 1.1.22"
    )[0]
    second = antigravity_profiles_from_output(
        "gemini-3.7-flash-high Gemini 3.7 Flash (High)", version="agy 1.1.23"
    )[0]

    assert first.fingerprint != second.fingerprint


def test_capability_contract_includes_profiles_without_dropping_legacy_models() -> None:
    profile = antigravity_profiles_from_output(
        "gemini-3.7-flash-high Gemini 3.7 Flash (High)", version="agy 1.1.22"
    )[0]
    capabilities = RunnerCapabilities(
        agent=AgentName.ANTIGRAVITY,
        installed=True,
        auth_state=AuthState.AUTHENTICATED,
        models=[
            RunnerModelCapabilities(
                model_id=profile.model_id,
                supports_text_input=True,
                supports_image_input=False,
                supports_structured_output=True,
            )
        ],
        profiles=[profile],
    )

    assert capabilities.profiles == [profile]


def test_profile_id_can_be_sent_to_test_endpoint(tmp_path: Path) -> None:
    profile = antigravity_profiles_from_output(
        "gemini-3.7-flash-high Gemini 3.7 Flash (High)", version="agy 1.1.22"
    )[0]

    class FakeRunner(AgentRunner):
        name = AgentName.ANTIGRAVITY

        async def capabilities(self) -> RunnerCapabilities:
            return RunnerCapabilities(
                agent=self.name,
                installed=True,
                models=[
                    RunnerModelCapabilities(
                        model_id=profile.model_id,
                        supports_text_input=True,
                        supports_image_input=False,
                        supports_structured_output=True,
                    )
                ],
                profiles=[profile],
            )

        async def run(self, request: RunnerRequest) -> RunnerResult:
            assert request.model_id == profile.model_id
            assert request.effort == profile.effort.value
            return RunnerResult(
                payload={"ok": True},
                model_id=request.model_id,
                input_tokens=None,
                output_tokens=None,
                duration_seconds=0.01,
            )

    token = SecretStr("a" * 32)
    app = create_app(
        Settings(agent_service_token=token, agent_workspace_root=tmp_path),
        registry=RunnerRegistry([FakeRunner()]),
    )
    response = TestClient(app).post(
        "/v1/test",
        headers={"Authorization": f"Bearer {token.get_secret_value()}"},
        json={"agent": "antigravity", "profile_id": profile.profile_id},
    )

    assert response.status_code == 200
    assert response.json()["profile_id"] == profile.profile_id
