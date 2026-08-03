from __future__ import annotations

from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.body_analysis.enums import (
    AnalysisLimitation,
    BodyAnalysisClassification,
    BodyArea,
    TrainingEmphasis,
)
from app.body_photos.enums import BodyPhotoView

PhotoValidationReason = Literal[
    "exactly_one_person_required",
    "full_body_not_visible",
    "wrong_view",
    "low_lighting",
    "low_sharpness",
    "clothing_obscures_body",
    "unsuitable_background",
    "photo_uncertain",
]


class BodyPhotoValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    view: BodyPhotoView
    reasons: tuple[PhotoValidationReason, ...] = Field(min_length=1, max_length=4)


class BodyPhotoPreflight(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    confidence: float = Field(ge=0, le=1)
    issues: tuple[BodyPhotoValidationIssue, ...] = Field(default=(), max_length=3)

    @model_validator(mode="after")
    def validate_decision(self) -> BodyPhotoPreflight:
        if not self.accepted and not self.issues:
            raise ValueError("rejected photos require validation issues")
        if len({issue.view for issue in self.issues}) != len(self.issues):
            raise ValueError("validation issues must contain each view at most once")
        return self


class BodyAnalysisFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    body_area: BodyArea
    classification: BodyAnalysisClassification
    severity: float | None = Field(default=None, ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    supporting_views: tuple[BodyPhotoView, ...] = Field(min_length=1, max_length=3)
    explanation: str = Field(min_length=1, max_length=800)
    limitations: tuple[AnalysisLimitation, ...] = Field(default=(), max_length=10)
    suggested_training_emphasis: tuple[TrainingEmphasis, ...] = Field(default=(), max_length=8)
    medical_review_recommended: bool = False

    @model_validator(mode="after")
    def validate_classification_fields(self) -> BodyAnalysisFinding:
        if (
            self.classification
            in {
                BodyAnalysisClassification.MILD_LAG,
                BodyAnalysisClassification.CLEAR_LAG,
            }
            and self.severity is None
        ):
            raise ValueError("lag findings require severity")
        if self.classification is BodyAnalysisClassification.UNCERTAIN:
            if self.severity is not None:
                raise ValueError("uncertain findings cannot have severity")
            if self.suggested_training_emphasis:
                raise ValueError("uncertain findings cannot affect training emphasis")
        if len(set(self.supporting_views)) != len(self.supporting_views):
            raise ValueError("supporting views must be unique")
        if len(set(self.limitations)) != len(self.limitations):
            raise ValueError("limitations must be unique")
        if len(set(self.suggested_training_emphasis)) != len(self.suggested_training_emphasis):
            raise ValueError("training emphasis values must be unique")
        return self


class BodyAnalysisSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    visible_strengths: tuple[BodyArea, ...] = ()
    priority_areas: tuple[BodyArea, ...] = ()
    moderate_attention_areas: tuple[BodyArea, ...] = ()
    uncertain_areas: tuple[BodyArea, ...] = ()

    @model_validator(mode="after")
    def validate_unique_categories(self) -> BodyAnalysisSummary:
        groups = (
            self.visible_strengths,
            self.priority_areas,
            self.moderate_attention_areas,
            self.uncertain_areas,
        )
        flattened = [area for group in groups for area in group]
        if len(flattened) != len(set(flattened)):
            raise ValueError("a body area cannot appear in multiple summary categories")
        return self


class NormalizedBodyAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(pattern=r"^[0-9]+\.[0-9]+$", max_length=16)
    overall_confidence: float = Field(ge=0, le=1)
    findings: tuple[BodyAnalysisFinding, ...] = Field(min_length=1, max_length=20)
    summary: BodyAnalysisSummary
    requires_coach_review: Literal[True]
    requires_doctor_review: Literal[True]

    @model_validator(mode="after")
    def validate_summary_against_findings(self) -> NormalizedBodyAnalysis:
        findings_by_area = {finding.body_area: finding for finding in self.findings}
        if len(findings_by_area) != len(self.findings):
            raise ValueError("findings must contain each body area at most once")

        expected = (
            (self.summary.visible_strengths, BodyAnalysisClassification.STRENGTH),
            (self.summary.priority_areas, BodyAnalysisClassification.CLEAR_LAG),
            (self.summary.moderate_attention_areas, BodyAnalysisClassification.MILD_LAG),
            (self.summary.uncertain_areas, BodyAnalysisClassification.UNCERTAIN),
        )
        for areas, classification in expected:
            for area in areas:
                finding = findings_by_area.get(area)
                if finding is None or finding.classification is not classification:
                    raise ValueError("summary categories must match finding classifications")

        summarized = {area for areas, _ in expected for area in areas}
        must_be_summarized = {
            finding.body_area
            for finding in self.findings
            if finding.classification is not BodyAnalysisClassification.NEUTRAL
        }
        if summarized != must_be_summarized:
            raise ValueError("summary must include every non-neutral finding")
        return self


VisualAssessmentStatus = Literal["complete", "partial"]
VisualDevelopmentPattern = Literal[
    "upper_body_dominant",
    "lower_body_dominant",
    "visually_balanced",
    "mixed",
    "uncertain",
]
VisualTaper = Literal["pronounced", "moderate", "limited", "uncertain"]
VisualUpperLowerBalance = Literal[
    "upper_body_dominant",
    "lower_body_dominant",
    "balanced",
    "uncertain",
]
VisualFindingClassification = Literal[
    "strength",
    "neutral",
    "mild_lag",
    "clear_lag",
    "uncertain",
    "not_assessable",
]
VisualTrainingEmphasis = Literal[
    "overall_shoulders",
    "lateral_delts",
    "rear_delts",
    "overall_chest",
    "upper_chest",
    "upper_back",
    "mid_back",
    "lat_width",
    "overall_arms",
    "biceps",
    "triceps",
    "forearms",
    "trunk_musculature",
    "glutes",
    "quads",
    "hamstrings",
    "calves",
    "left_right_balance",
]
VisualChecklistRating = Literal[
    "excellent",
    "good",
    "average",
    "needs_attention",
    "focus_priority",
    "not_assessable",
]
VisualSuggestedGoal = Literal["lose_weight", "maintain_weight", "build_muscle", "gain_weight"]


class VisualViewQuality(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    usable: bool
    issues_fa: tuple[str, ...] = Field(default=(), max_length=4)


class VisualPhotoQuality(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    front: VisualViewQuality
    side: VisualViewQuality
    back: VisualViewQuality
    global_limitations_fa: tuple[str, ...] = Field(default=(), max_length=6)

    @property
    def usable_views(self) -> tuple[BodyPhotoView, ...]:
        views = (
            (BodyPhotoView.FRONT, self.front),
            (BodyPhotoView.SIDE, self.side),
            (BodyPhotoView.BACK, self.back),
        )
        return tuple(view for view, quality in views if quality.usable)


class VisualOverallAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    development_pattern: VisualDevelopmentPattern
    shoulder_to_waist_taper: VisualTaper
    upper_lower_balance: VisualUpperLowerBalance
    summary_fa: str = Field(min_length=1, max_length=800)


class VisualPhysiqueFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    area: BodyArea
    classification: VisualFindingClassification
    severity: float | None = Field(default=None, ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    views_used: tuple[BodyPhotoView, ...] = Field(min_length=1, max_length=3)
    evidence_fa: str = Field(min_length=1, max_length=800)
    suggested_training_emphasis: tuple[VisualTrainingEmphasis, ...] = Field(
        default=(), max_length=8
    )

    @model_validator(mode="after")
    def validate_classification_fields(self) -> VisualPhysiqueFinding:
        is_lag = self.classification in {"mild_lag", "clear_lag"}
        if is_lag and self.severity is None:
            raise ValueError("lag findings require severity")
        if not is_lag and self.severity is not None:
            raise ValueError("only lag findings can include severity")
        if not is_lag and self.suggested_training_emphasis:
            raise ValueError("only lag findings can include training emphasis")
        if len(set(self.views_used)) != len(self.views_used):
            raise ValueError("views_used must be unique")
        if len(set(self.suggested_training_emphasis)) != len(self.suggested_training_emphasis):
            raise ValueError("training emphasis values must be unique")
        return self


class VisualPhysiqueAssessmentPayload(BaseModel):
    """Provider-owned v2 visual assessment response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assessment_status: VisualAssessmentStatus
    photo_quality: VisualPhotoQuality
    overall_assessment: VisualOverallAssessment
    findings: tuple[VisualPhysiqueFinding, ...] = Field(min_length=13, max_length=13)

    @model_validator(mode="after")
    def validate_assessment(self) -> VisualPhysiqueAssessmentPayload:
        expected_areas = set(BodyArea)
        areas = {finding.area for finding in self.findings}
        if areas != expected_areas or len(areas) != len(self.findings):
            raise ValueError("findings must contain each supported body area exactly once")
        usable_count = len(self.photo_quality.usable_views)
        if self.assessment_status == "complete" and usable_count != 3:
            raise ValueError("complete assessments require three usable views")
        if self.assessment_status == "partial" and usable_count != 2:
            raise ValueError("partial assessments require exactly two usable views")
        usable_views = set(self.photo_quality.usable_views)
        for finding in self.findings:
            if not set(finding.views_used).issubset(usable_views):
                raise ValueError("findings can use only usable photo views")
        return self


class VisualPhysiqueAssessment(VisualPhysiqueAssessmentPayload):
    """Validated v2 result enriched with backend-owned product policy."""

    medical_review_recommended: Literal[False] = False
    human_coach_review_required: Literal[True] = True
    human_doctor_review_required: Literal[True] = True
    provisional_notice_fa: Literal[
        "این ارزیابی صرفاً یک بررسی بصری اولیه است و پیش از استفاده در طراحی برنامه باید توسط "
        "مربی واجد صلاحیت بازبینی شود."
    ] = (
        "این ارزیابی صرفاً یک بررسی بصری اولیه است و پیش از استفاده در طراحی برنامه باید توسط "
        "مربی واجد صلاحیت بازبینی شود."
    )


class VisualChecklistView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rating: VisualChecklistRating
    evidence_fa: str = Field(min_length=1, max_length=500)


class VisualChecklistFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    area: BodyArea
    front: VisualChecklistView
    side: VisualChecklistView
    back: VisualChecklistView
    overall_rating: VisualChecklistRating
    overall_summary_fa: str = Field(min_length=1, max_length=800)
    confidence: float = Field(ge=0, le=1)
    suggested_training_emphasis: tuple[VisualTrainingEmphasis, ...] = Field(
        default=(), max_length=8
    )

    @model_validator(mode="after")
    def validate_training_emphasis(self) -> VisualChecklistFinding:
        if self.overall_rating not in {"needs_attention", "focus_priority"}:
            if self.suggested_training_emphasis:
                raise ValueError("only attention ratings can include training emphasis")
        if len(set(self.suggested_training_emphasis)) != len(self.suggested_training_emphasis):
            raise ValueError("training emphasis values must be unique")
        return self


class VisualGoalSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    suggested_goal: VisualSuggestedGoal
    reasoning_fa: str = Field(min_length=1, max_length=800)
    inputs_unavailable_fa: tuple[str, ...] = Field(default=(), max_length=6)


class VisualPhysiqueAssessmentV3Payload(BaseModel):
    """Provider-owned v3 checklist response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assessment_status: VisualAssessmentStatus
    photo_quality: VisualPhotoQuality
    overall_assessment: VisualOverallAssessment
    goal_suggestion: VisualGoalSuggestion
    findings: tuple[VisualChecklistFinding, ...] = Field(min_length=13, max_length=13)

    @model_validator(mode="after")
    def validate_assessment(self) -> VisualPhysiqueAssessmentV3Payload:
        expected_areas = set(BodyArea)
        areas = {finding.area for finding in self.findings}
        if areas != expected_areas or len(areas) != len(self.findings):
            raise ValueError("findings must contain each supported body area exactly once")
        usable_count = len(self.photo_quality.usable_views)
        if self.assessment_status == "complete" and usable_count != 3:
            raise ValueError("complete assessments require three usable views")
        if self.assessment_status == "partial" and usable_count != 2:
            raise ValueError("partial assessments require exactly two usable views")
        qualities = {
            BodyPhotoView.FRONT: self.photo_quality.front,
            BodyPhotoView.SIDE: self.photo_quality.side,
            BodyPhotoView.BACK: self.photo_quality.back,
        }
        for finding in self.findings:
            for view, checklist in (
                (BodyPhotoView.FRONT, finding.front),
                (BodyPhotoView.SIDE, finding.side),
                (BodyPhotoView.BACK, finding.back),
            ):
                if not qualities[view].usable and checklist.rating != "not_assessable":
                    raise ValueError("unusable views must be not_assessable")
        return self


class VisualPhysiqueAssessmentV3(VisualPhysiqueAssessmentV3Payload):
    """Validated v3 result enriched with backend-owned product policy."""

    medical_review_recommended: Literal[False] = False
    human_coach_review_required: Literal[True] = True
    human_doctor_review_required: Literal[True] = True
    provisional_notice_fa: Literal[
        "این ارزیابی صرفاً یک بررسی بصری اولیه است و پیش از استفاده در طراحی برنامه باید توسط "
        "مربی واجد صلاحیت بازبینی شود."
    ] = (
        "این ارزیابی صرفاً یک بررسی بصری اولیه است و پیش از استفاده در طراحی برنامه باید توسط "
        "مربی واجد صلاحیت بازبینی شود."
    )


def visual_physique_provider_schema() -> dict[str, Any]:
    """Return a transport schema supported by constrained-output vision providers.

    Pydantic validates the full product contract after generation. The provider receives
    the same object shape without state-exploding string, number, and array bounds.
    """

    return cast(
        dict[str, Any],
        _relax_provider_schema(VisualPhysiqueAssessmentPayload.model_json_schema()),
    )


def visual_physique_v3_provider_schema() -> dict[str, Any]:
    """Return the relaxed transport schema for the v3 checklist."""

    return cast(
        dict[str, Any],
        _relax_provider_schema(VisualPhysiqueAssessmentV3Payload.model_json_schema()),
    )


def _relax_provider_schema(value: Any) -> Any:
    if isinstance(value, dict):
        unsupported_constraints = {
            "format",
            "maxItems",
            "maxLength",
            "maximum",
            "minItems",
            "minLength",
            "minimum",
            "pattern",
            "uniqueItems",
        }
        return {
            key: _relax_provider_schema(item)
            for key, item in value.items()
            if key not in unsupported_constraints
        }
    if isinstance(value, list):
        return [_relax_provider_schema(item) for item in value]
    return value
