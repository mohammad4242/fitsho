from dataclasses import fields

import pytest
from pydantic import ValidationError

from app import schemas
from app.runners.base import RunnerRequest, RunnerResult
from app.schemas import (
    AgentGenerationInput,
    AgentGenerationOutput,
    AgentName,
    ErrorEnvelope,
    RunnerCapabilities,
    RunnerModelCapabilities,
)


def test_agent_names_are_cli_implementations() -> None:
    assert {agent.value for agent in AgentName} == {"antigravity", "codex", "claude"}


def test_generation_contract_matches_the_backend_boundary() -> None:
    request_fields = set(AgentGenerationInput.model_fields)
    assert request_fields == {
        "agent",
        "model_id",
        "profile_id",
        "system_prompt",
        "input_payload",
        "response_schema",
        "schema_name",
        "temperature",
        "max_output_tokens",
        "timeout_seconds",
    }
    assert set(AgentGenerationOutput.model_fields) == {
        "payload",
        "agent",
        "model_id",
        "profile_id",
        "request_id",
        "input_tokens",
        "output_tokens",
        "duration_seconds",
    }
    with pytest.raises(ValidationError):
        AgentGenerationInput.model_validate(
            {
                "agent": "codex",
                "model_id": "model",
                "system_prompt": "prompt",
                "input_payload": {},
                "response_schema": {},
                "schema_name": "schema",
                "timeout_seconds": 10,
            }
        )


def test_runner_contract_matches_the_frozen_protocol() -> None:
    assert [field.name for field in fields(RunnerRequest)] == [
        "model_id",
        "system_prompt",
        "input_payload",
        "response_schema",
        "schema_name",
        "temperature",
        "max_output_tokens",
        "timeout_seconds",
        "image_paths",
        "effort",
    ]
    assert [field.name for field in fields(RunnerResult)] == [
        "payload",
        "model_id",
        "input_tokens",
        "output_tokens",
        "duration_seconds",
    ]


def test_capability_and_test_contracts_use_agent_names() -> None:
    assert set(RunnerModelCapabilities.model_fields) >= {
        "model_id",
        "supports_text_input",
        "supports_image_input",
        "supports_structured_output",
    }
    assert "agent" in RunnerCapabilities.model_fields
    assert "agent" in schemas.TestRequest.model_fields


def test_error_request_id_is_inside_error_object() -> None:
    payload = ErrorEnvelope.model_validate(
        {
            "error": {
                "code": "timeout",
                "message": "request timed out",
                "request_id": "request-1",
            }
        }
    )
    assert payload.model_dump() == {
        "error": {
            "code": "timeout",
            "message": "request timed out",
            "request_id": "request-1",
        }
    }
