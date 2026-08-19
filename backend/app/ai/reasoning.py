from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.ai.provider import AIReasoningProvider
from app.athlete_state.schemas import AthleteState
from app.profile.enums import WorkoutGenerationMethod
from app.workouts.program_engine.adaptation_policy import (
    CycleAdaptationDecision,
    CycleAdaptationProgramSnapshot,
)


class AIReasoningSource(StrEnum):
    PROVIDER = "provider"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"


class AIReasoningReasonCode(StrEnum):
    SAFE_CANDIDATE_SET = "SAFE_CANDIDATE_SET"
    SAFETY_CONSTRAINT_PRESERVED = "SAFETY_CONSTRAINT_PRESERVED"
    STRUCTURED_CONTEXT = "STRUCTURED_CONTEXT"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"
    FEEDBACK_INTERPRETATION = "FEEDBACK_INTERPRETATION"


class AIReasoningFeedbackSignal(StrEnum):
    DISCOMFORT = "discomfort"
    DISLIKE = "dislike"
    EQUIPMENT_UNAVAILABLE = "equipment_unavailable"
    PAIN_OR_SAFETY_CONCERN = "pain_or_safety_concern"
    RECOVERY_CONCERN = "recovery_concern"
    SCHEDULE_CONTEXT_CHANGE = "schedule_context_change"


class AIReasoningFeedbackSourceField(StrEnum):
    NOTE_OPTIONAL = "note_optional"
    PAIN_OR_LIMITATION_FEEDBACK = "pain_or_limitation_feedback"
    PERFORMANCE_CHANGES = "performance_changes"
    NEW_LIMITATION = "new_limitation"
    WEEKLY_NOTE_OPTIONAL = "weekly_note_optional"


class AIReasoningFeedbackContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = Field(min_length=1, max_length=4_000)
    source_id: UUID | None = None
    source_field: AIReasoningFeedbackSourceField


class AIReasoningSafeCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1, max_length=160)
    exercise_ids: tuple[UUID, ...] = Field(min_length=1, max_length=100)


class AIReasoningInput(BaseModel):
    """Raw-record-free, deterministic context that AI is allowed to inspect."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    generation_method: WorkoutGenerationMethod
    athlete_state: AthleteState
    adaptation_decision: CycleAdaptationDecision
    previous_program: CycleAdaptationProgramSnapshot | None = None
    proposed_program: CycleAdaptationProgramSnapshot | None = None
    feedback_context: AIReasoningFeedbackContext | None = None
    safe_candidates: tuple[AIReasoningSafeCandidate, ...] = Field(default=(), max_length=8)
    deterministic_selected_candidate_id: str | None = None

    @model_validator(mode="after")
    def validate_safe_context(self) -> AIReasoningInput:
        candidate_ids = [item.candidate_id for item in self.safe_candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("safe candidate IDs must be unique")

        blocked_ids = set(self.adaptation_decision.safety_constraints.blocked_exercises)
        unavailable_ids = set(self.adaptation_decision.preference_constraints.unavailable_exercises)
        forbidden_ids = blocked_ids | unavailable_ids
        for candidate in self.safe_candidates:
            if forbidden_ids.intersection(candidate.exercise_ids):
                raise ValueError("safe candidates cannot contain blocked or unavailable exercises")

        if (
            self.deterministic_selected_candidate_id is not None
            and self.deterministic_selected_candidate_id not in set(candidate_ids)
        ):
            raise ValueError("deterministic selection must be one of the safe candidates")
        return self


class AIReasoningCandidateRanking(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1, max_length=160)
    rank: int = Field(ge=1, le=8)
    rationale: str = Field(min_length=1, max_length=1_000)


class AIReasoningFeedbackProposal(BaseModel):
    """A proposal only; it is never a persisted preference or safety state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    signal: AIReasoningFeedbackSignal
    confidence: float = Field(ge=0, le=1)
    source_id: UUID | None = None
    source_field: AIReasoningFeedbackSourceField


class AIReasoningOutput(BaseModel):
    """Validated explanation/ranking output; it contains no prescription controls."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    source: AIReasoningSource = AIReasoningSource.PROVIDER
    summary: str = Field(min_length=1, max_length=2_000)
    reason_codes: tuple[AIReasoningReasonCode, ...] = Field(
        min_length=1,
        max_length=16,
    )
    selected_candidate_id: str | None = None
    rankings: tuple[AIReasoningCandidateRanking, ...] = Field(default=(), max_length=8)
    feedback_proposals: tuple[AIReasoningFeedbackProposal, ...] = Field(default=(), max_length=8)


class AIReasoningError(Exception):
    pass


class AIReasoningNotAllowedError(AIReasoningError):
    pass


class AIReasoningOutputError(AIReasoningError):
    pass


class AIReasoningProviderError(AIReasoningError):
    pass


class AIReasoningService:
    MIN_FEEDBACK_CONFIDENCE = 0.75

    async def reason(
        self,
        request: AIReasoningInput,
        provider: AIReasoningProvider | None,
        *,
        fallback_on_provider_failure: bool = False,
    ) -> AIReasoningOutput:
        self._require_ai_mode(request)
        if provider is None:
            return self.deterministic_fallback(request)
        try:
            raw_output = await provider.reason(request)
        except Exception as error:
            if fallback_on_provider_failure:
                return self.deterministic_fallback(request)
            raise AIReasoningProviderError(
                "AI reasoning provider failed after its configured fallback policy"
            ) from error
        output = self._validate_output(raw_output)
        approved_proposals = self.validate_feedback_proposals(request, output)
        return output.model_copy(
            update={
                "source": AIReasoningSource.PROVIDER,
                "feedback_proposals": approved_proposals,
            }
        )

    @staticmethod
    def deterministic_fallback(request: AIReasoningInput) -> AIReasoningOutput:
        rankings = tuple(
            AIReasoningCandidateRanking(
                candidate_id=candidate.candidate_id,
                rank=index,
                rationale="Retained in deterministic safe-candidate order.",
            )
            for index, candidate in enumerate(request.safe_candidates, start=1)
        )
        return AIReasoningOutput(
            source=AIReasoningSource.DETERMINISTIC_FALLBACK,
            summary=(
                "Deterministic coaching remains authoritative; AI reasoning was not required. "
                f"Adaptation action: {request.adaptation_decision.overall_action.value}."
            ),
            reason_codes=(
                AIReasoningReasonCode.DETERMINISTIC_FALLBACK,
                AIReasoningReasonCode.SAFETY_CONSTRAINT_PRESERVED,
            ),
            selected_candidate_id=request.deterministic_selected_candidate_id,
            rankings=rankings,
        )

    @classmethod
    def validate_feedback_proposals(
        cls,
        request: AIReasoningInput,
        output: AIReasoningOutput,
    ) -> tuple[AIReasoningFeedbackProposal, ...]:
        """Approve only high-confidence, correctly-provenanced proposals.

        This returns data for a later deterministic domain service to apply. It
        never writes preferences, safety signals, or other persistent state.
        """
        cls._validate_output_against_input(output, request)
        return tuple(
            proposal
            for proposal in output.feedback_proposals
            if proposal.confidence >= cls.MIN_FEEDBACK_CONFIDENCE
        )

    @staticmethod
    def _require_ai_mode(request: AIReasoningInput) -> None:
        if request.generation_method is not WorkoutGenerationMethod.AI:
            raise AIReasoningNotAllowedError(
                "AI reasoning is available only for the explicitly selected AI Coach mode"
            )

    @staticmethod
    def _validate_output(raw_output: object) -> AIReasoningOutput:
        try:
            return AIReasoningOutput.model_validate(raw_output)
        except ValidationError as error:
            raise AIReasoningOutputError(
                "AI reasoning returned invalid structured output"
            ) from error

    @staticmethod
    def _validate_output_against_input(
        output: AIReasoningOutput,
        request: AIReasoningInput,
    ) -> None:
        safe_ids = {candidate.candidate_id for candidate in request.safe_candidates}
        if (
            output.selected_candidate_id is not None
            and output.selected_candidate_id not in safe_ids
        ):
            raise AIReasoningOutputError("AI reasoning selected a candidate outside the safe set")

        ranking_ids = [item.candidate_id for item in output.rankings]
        if len(ranking_ids) != len(set(ranking_ids)):
            raise AIReasoningOutputError("AI reasoning returned duplicate candidate rankings")
        if not set(ranking_ids).issubset(safe_ids):
            raise AIReasoningOutputError("AI reasoning ranked a candidate outside the safe set")
        ranks = sorted(item.rank for item in output.rankings)
        if ranks != list(range(1, len(ranks) + 1)):
            raise AIReasoningOutputError("AI reasoning ranks must be contiguous and deterministic")

        proposals = output.feedback_proposals
        if not proposals:
            return
        feedback_context = request.feedback_context
        if feedback_context is None:
            raise AIReasoningOutputError(
                "AI reasoning returned feedback proposals without supplied feedback text"
            )
        proposal_keys = [(item.signal, item.source_id, item.source_field) for item in proposals]
        if len(proposal_keys) != len(set(proposal_keys)):
            raise AIReasoningOutputError("AI reasoning returned duplicate feedback proposals")
        for proposal in proposals:
            if (
                proposal.source_id != feedback_context.source_id
                or proposal.source_field != feedback_context.source_field
            ):
                raise AIReasoningOutputError(
                    "AI reasoning feedback provenance does not match supplied feedback text"
                )
