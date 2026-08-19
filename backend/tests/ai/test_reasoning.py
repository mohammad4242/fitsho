from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.athlete_state.schemas import (
    AthleteState,
    AthleteStateAdherence,
    AthleteStateBodyProgress,
    AthleteStateDifficultyTrend,
    AthleteStateProvenance,
    AthleteStateRecoveryTrend,
    AthleteStateScheduleContext,
)
from app.profile.enums import WorkoutGenerationMethod
from app.workouts.program_engine.adaptation_policy import decide_cycle_adaptation


def _input(*, method: WorkoutGenerationMethod = WorkoutGenerationMethod.AI):
    state = AthleteState(
        user_id=uuid4(),
        adherence=AthleteStateAdherence(
            sessions_completed=4,
            planned_sessions=4,
            percent=100,
        ),
        recovery_trend=AthleteStateRecoveryTrend(),
        difficulty_trend=AthleteStateDifficultyTrend(),
        schedule=AthleteStateScheduleContext(),
        body_progress=AthleteStateBodyProgress(),
        provenance=AthleteStateProvenance(),
    )
    candidate_id = "safe-candidate-a"
    return {
        "generation_method": method,
        "athlete_state": state,
        "adaptation_decision": decide_cycle_adaptation(state),
        "safe_candidates": (
            {
                "candidate_id": candidate_id,
                "exercise_ids": (uuid4(),),
            },
        ),
        "deterministic_selected_candidate_id": candidate_id,
    }


class _Provider:
    async def reason(self, request: object) -> object:
        return {
            "summary": "The supplied safe candidate matches the structured context.",
            "reason_codes": ["SAFE_CANDIDATE_SET"],
            "selected_candidate_id": "safe-candidate-a",
            "rankings": [
                {
                    "candidate_id": "safe-candidate-a",
                    "rank": 1,
                    "rationale": "It is already eligible and safe.",
                }
            ],
        }


def test_reasoning_service_accepts_valid_structured_provider_output() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningOutput, AIReasoningService

    reasoning_input = AIReasoningInput.model_validate(_input())
    output = asyncio.run(AIReasoningService().reason(reasoning_input, _Provider()))

    assert isinstance(output, AIReasoningOutput)
    assert output.selected_candidate_id == "safe-candidate-a"
    assert output.source == "provider"


def test_reasoning_rejects_candidate_outside_safe_set() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningOutputError, AIReasoningService

    reasoning_input = AIReasoningInput.model_validate(_input())

    class InvalidProvider:
        async def reason(self, request: object) -> object:
            return {
                "summary": "invalid",
                "reason_codes": ["SAFE_CANDIDATE_SET"],
                "selected_candidate_id": "not-safe",
                "rankings": [],
            }

    with pytest.raises(AIReasoningOutputError):
        asyncio.run(AIReasoningService().reason(reasoning_input, InvalidProvider()))


def test_reasoning_rejects_malformed_output() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningOutputError, AIReasoningService

    reasoning_input = AIReasoningInput.model_validate(_input())

    class MalformedProvider:
        async def reason(self, request: object) -> object:
            return {"summary": "missing required fields", "sets": 10}

    with pytest.raises(AIReasoningOutputError):
        asyncio.run(AIReasoningService().reason(reasoning_input, MalformedProvider()))


def test_safety_constraint_rejects_blocked_candidate_before_provider_call() -> None:
    from app.ai.reasoning import AIReasoningInput

    raw = _input()
    blocked_id = raw["safe_candidates"][0]["exercise_ids"][0]
    decision = raw["adaptation_decision"]
    raw["adaptation_decision"] = decision.model_copy(
        update={
            "safety_constraints": decision.safety_constraints.model_copy(
                update={"blocked_exercises": (blocked_id,)}
            )
        }
    )

    with pytest.raises(ValueError):
        AIReasoningInput.model_validate(raw)


def test_internal_generation_mode_cannot_invoke_reasoning_provider() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningNotAllowedError, AIReasoningService

    reasoning_input = AIReasoningInput.model_validate(
        _input(method=WorkoutGenerationMethod.FITSHO_COACH)
    )

    with pytest.raises(AIReasoningNotAllowedError):
        asyncio.run(AIReasoningService().reason(reasoning_input, _Provider()))


def test_deterministic_fallback_remains_available_without_provider() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningService

    reasoning_input = AIReasoningInput.model_validate(_input())
    output = AIReasoningService().deterministic_fallback(reasoning_input)

    assert output.source == "deterministic_fallback"
    assert output.selected_candidate_id == "safe-candidate-a"


def test_provider_failure_can_use_explicit_deterministic_fallback() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningService

    class FailingProvider:
        async def reason(self, request: object) -> object:
            raise RuntimeError("provider unavailable")

    reasoning_input = AIReasoningInput.model_validate(_input())
    output = asyncio.run(
        AIReasoningService().reason(
            reasoning_input,
            FailingProvider(),
            fallback_on_provider_failure=True,
        )
    )

    assert output.source == "deterministic_fallback"
    assert output.selected_candidate_id == "safe-candidate-a"
