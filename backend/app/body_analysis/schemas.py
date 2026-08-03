from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.body_analysis.enums import (
    AnalysisLimitation,
    BodyAnalysisClassification,
    BodyArea,
    TrainingEmphasis,
)
from app.body_photos.enums import BodyPhotoView


class BodyAnalysisFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    body_area: BodyArea
    classification: BodyAnalysisClassification
    severity: float | None = Field(default=None, ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    supporting_views: tuple[BodyPhotoView, ...] = Field(min_length=1, max_length=3)
    explanation: str = Field(min_length=1, max_length=800)
    limitations: tuple[AnalysisLimitation, ...] = Field(default=(), max_length=10)
    suggested_training_emphasis: tuple[TrainingEmphasis, ...] = Field(
        default=(), max_length=8
    )
    medical_review_recommended: bool = False

    @model_validator(mode="after")
    def validate_classification_fields(self) -> BodyAnalysisFinding:
        if self.classification is BodyAnalysisClassification.UNCERTAIN:
            if self.severity is not None:
                raise ValueError("uncertain findings cannot have severity")
            if self.suggested_training_emphasis:
                raise ValueError("uncertain findings cannot affect training emphasis")
        if len(set(self.supporting_views)) != len(self.supporting_views):
            raise ValueError("supporting views must be unique")
        if len(set(self.limitations)) != len(self.limitations):
            raise ValueError("limitations must be unique")
        if len(set(self.suggested_training_emphasis)) != len(
            self.suggested_training_emphasis
        ):
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
