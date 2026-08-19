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


class _CountingProvider:
    def __init__(self, output: object) -> None:
        self.calls = 0
        self.output = output

    async def reason(self, request: object) -> object:
        self.calls += 1
        return self.output


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


def test_ai_coach_interprets_feedback_into_validated_proposal() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningService

    source_id = uuid4()
    raw = _input()
    raw["feedback_context"] = {
        "text": "این حرکت باعث درد شد",
        "source_id": source_id,
        "source_field": "note_optional",
    }

    class FeedbackProvider:
        async def reason(self, request: object) -> object:
            return {
                "summary": "A possible safety concern was found.",
                "reason_codes": ["FEEDBACK_INTERPRETATION"],
                "feedback_proposals": [
                    {
                        "signal": "pain_or_safety_concern",
                        "confidence": 0.94,
                        "source_id": source_id,
                        "source_field": "note_optional",
                    }
                ],
            }

    reasoning_input = AIReasoningInput.model_validate(raw)
    output = asyncio.run(AIReasoningService().reason(reasoning_input, FeedbackProvider()))
    approved = AIReasoningService().validate_feedback_proposals(reasoning_input, output)

    assert len(approved) == 1
    assert approved[0].signal == "pain_or_safety_concern"
    assert approved[0].confidence == 0.94
    assert approved[0].source_id == source_id


def test_low_confidence_feedback_proposal_is_rejected_without_state_change() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningService

    source_id = uuid4()
    raw = _input()
    raw["feedback_context"] = {
        "text": "این حرکت را دوست ندارم",
        "source_id": source_id,
        "source_field": "note_optional",
    }
    reasoning_input = AIReasoningInput.model_validate(raw)
    original_state = reasoning_input.athlete_state

    class LowConfidenceProvider:
        async def reason(self, request: object) -> object:
            return {
                "summary": "The text is ambiguous.",
                "reason_codes": ["FEEDBACK_INTERPRETATION"],
                "feedback_proposals": [
                    {
                        "signal": "dislike",
                        "confidence": 0.49,
                        "source_id": source_id,
                        "source_field": "note_optional",
                    }
                ],
            }

    output = asyncio.run(AIReasoningService().reason(reasoning_input, LowConfidenceProvider()))
    approved = AIReasoningService().validate_feedback_proposals(reasoning_input, output)

    assert output.feedback_proposals == ()
    assert approved == ()
    assert reasoning_input.athlete_state == original_state


def test_feedback_provenance_must_match_supplied_text() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningOutputError, AIReasoningService

    source_id = uuid4()
    raw = _input()
    raw["feedback_context"] = {
        "text": "درد دارم",
        "source_id": source_id,
        "source_field": "pain_or_limitation_feedback",
    }
    reasoning_input = AIReasoningInput.model_validate(raw)

    class WrongProvenanceProvider:
        async def reason(self, request: object) -> object:
            return {
                "summary": "Possible pain.",
                "reason_codes": ["FEEDBACK_INTERPRETATION"],
                "feedback_proposals": [
                    {
                        "signal": "pain_or_safety_concern",
                        "confidence": 0.98,
                        "source_id": uuid4(),
                        "source_field": "pain_or_limitation_feedback",
                    }
                ],
            }

    with pytest.raises(AIReasoningOutputError):
        asyncio.run(AIReasoningService().reason(reasoning_input, WrongProvenanceProvider()))


def test_pain_proposal_is_not_a_dislike_proposal() -> None:
    from app.ai.reasoning import AIReasoningFeedbackSignal

    assert AIReasoningFeedbackSignal.PAIN_OR_SAFETY_CONCERN != AIReasoningFeedbackSignal.DISLIKE


def test_ai_output_cannot_create_persistent_or_safety_state_directly() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningOutputError, AIReasoningService

    reasoning_input = AIReasoningInput.model_validate(_input())

    class StateMutatingProvider:
        async def reason(self, request: object) -> object:
            return {
                "summary": "invalid state mutation",
                "reason_codes": ["FEEDBACK_INTERPRETATION"],
                "blocked_exercises": [str(uuid4())],
                "persistent_preferences": [str(uuid4())],
            }

    with pytest.raises(AIReasoningOutputError):
        asyncio.run(AIReasoningService().reason(reasoning_input, StateMutatingProvider()))


def test_deterministic_mode_makes_zero_ai_calls() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningNotAllowedError, AIReasoningService

    provider = _CountingProvider({})
    reasoning_input = AIReasoningInput.model_validate(
        _input(method=WorkoutGenerationMethod.FITSHO_COACH)
    )

    with pytest.raises(AIReasoningNotAllowedError):
        asyncio.run(AIReasoningService().reason(reasoning_input, provider))

    assert provider.calls == 0


def test_deterministic_mode_makes_zero_ai_calls_for_coach_summary() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningNotAllowedError, AIReasoningService

    provider = _CountingProvider({})
    reasoning_input = AIReasoningInput.model_validate(
        _input(method=WorkoutGenerationMethod.FITSHO_COACH)
    )

    with pytest.raises(AIReasoningNotAllowedError):
        asyncio.run(AIReasoningService().summarize_for_coach(reasoning_input, provider))

    assert provider.calls == 0


def test_ai_coach_ranks_multiple_safe_candidates_with_structured_reasons() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningService

    raw = _input()
    raw["safe_candidates"] = (
        raw["safe_candidates"][0],
        {
            "candidate_id": "safe-candidate-b",
            "exercise_ids": (uuid4(),),
        },
    )

    class RankingProvider:
        async def reason(self, request: object) -> object:
            return {
                "summary": "Candidate B better matches the supplied context.",
                "reason_codes": ["SAFE_CANDIDATE_SET", "STRUCTURED_CONTEXT"],
                "selected_candidate_id": "safe-candidate-b",
                "rankings": [
                    {
                        "candidate_id": "safe-candidate-b",
                        "rank": 1,
                        "rationale": "It best matches the supplied safe context.",
                    },
                    {
                        "candidate_id": "safe-candidate-a",
                        "rank": 2,
                        "rationale": "It remains eligible but is a weaker fit.",
                    },
                ],
            }

    reasoning_input = AIReasoningInput.model_validate(raw)
    output = asyncio.run(
        AIReasoningService().rank_safe_candidates(reasoning_input, RankingProvider())
    )

    assert output.selected_candidate_id == "safe-candidate-b"
    assert [item.candidate_id for item in output.rankings] == [
        "safe-candidate-b",
        "safe-candidate-a",
    ]
    assert output.reason_codes == ("SAFE_CANDIDATE_SET", "STRUCTURED_CONTEXT")


def test_ai_coach_produces_validated_persian_coach_summary() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningService

    source_id = uuid4()
    raw = _input()
    state = raw["athlete_state"]
    raw["athlete_state"] = state.model_copy(
        update={"provenance": state.provenance.model_copy(update={"cycle_ids": (source_id,)})}
    )
    decision = raw["adaptation_decision"]
    raw["adaptation_decision"] = decision.model_copy(
        update={"provenance": decision.provenance.model_copy(update={"cycle_ids": (source_id,)})}
    )
    reasoning_input = AIReasoningInput.model_validate(raw)
    reason_code = reasoning_input.adaptation_decision.reason_codes[0].value

    class SummaryProvider:
        async def reason(self, request: object) -> object:
            return {
                "summary": "Structured coach summary.",
                "reason_codes": ["STRUCTURED_CONTEXT"],
                "coach_summary": {
                    "summary_fa": "دوره قبلی با شواهد موجود بررسی شد و نیاز به توجه مربی دارد.",
                    "attention_points_fa": ["روند ریکاوری و محدودیت‌های ایمنی بررسی شود."],
                    "covered_sections": [
                        "previous_cycle",
                        "adherence_recovery_difficulty",
                        "program_changes",
                        "coach_attention",
                    ],
                    "source_reason_codes": [reason_code],
                    "source_ids": [source_id],
                },
            }

    output = asyncio.run(
        AIReasoningService().summarize_for_coach(reasoning_input, SummaryProvider())
    )

    assert output.coach_summary is not None
    assert output.coach_summary.summary_fa.startswith("دوره قبلی")
    assert output.coach_summary.source_reason_codes == (reason_code,)
    assert output.coach_summary.source_ids == (source_id,)


def test_coach_summary_rejects_unsupported_claim_evidence() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningOutputError, AIReasoningService

    reasoning_input = AIReasoningInput.model_validate(_input())

    class InventingProvider:
        async def reason(self, request: object) -> object:
            return {
                "summary": "Invented summary.",
                "reason_codes": ["STRUCTURED_CONTEXT"],
                "coach_summary": {
                    "summary_fa": "برنامه قطعاً باعث افزایش قدرت می‌شود.",
                    "attention_points_fa": [],
                    "covered_sections": ["progress"],
                    "source_reason_codes": ["INVENTED_REASON"],
                    "source_ids": [uuid4()],
                },
            }

    with pytest.raises(AIReasoningOutputError):
        asyncio.run(AIReasoningService().summarize_for_coach(reasoning_input, InventingProvider()))


def test_coach_summary_provider_failure_keeps_deterministic_context_available() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningService

    reasoning_input = AIReasoningInput.model_validate(_input())

    class FailingProvider:
        async def reason(self, request: object) -> object:
            raise RuntimeError("provider unavailable")

    output = asyncio.run(
        AIReasoningService().summarize_for_coach(
            reasoning_input,
            FailingProvider(),
            fallback_on_provider_failure=True,
        )
    )

    assert output.coach_summary is None
    assert output.source == "deterministic_fallback"
    assert output.summary.startswith("Deterministic coaching remains authoritative")


def test_summary_does_not_mutate_athlete_state_or_program_inputs() -> None:
    from app.ai.reasoning import AIReasoningInput, AIReasoningOutputError, AIReasoningService

    reasoning_input = AIReasoningInput.model_validate(_input())
    original_state = reasoning_input.athlete_state
    original_decision = reasoning_input.adaptation_decision

    class SummaryProvider:
        async def reason(self, request: object) -> object:
            return {
                "summary": "invalid mutation",
                "reason_codes": ["STRUCTURED_CONTEXT"],
                "coach_summary": {
                    "summary_fa": "تغییر state",
                    "attention_points_fa": [],
                    "covered_sections": ["coach_attention"],
                    "source_reason_codes": [],
                    "source_ids": [],
                },
                "sets": 10,
            }

    with pytest.raises(AIReasoningOutputError):
        asyncio.run(AIReasoningService().summarize_for_coach(reasoning_input, SummaryProvider()))

    assert reasoning_input.athlete_state == original_state
    assert reasoning_input.adaptation_decision == original_decision
