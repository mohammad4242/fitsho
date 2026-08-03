from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.body_analysis.schemas import NormalizedBodyAnalysis


class MedicalClaimError(ValueError):
    """Raised when provider prose crosses the non-diagnostic product boundary."""


_MEDICAL_CLAIM_PATTERN = re.compile(
    r"\b(?:arthritis|diagnos(?:e|ed|is|tic)|disease|deformit(?:y|ies)|hernia|"
    r"injur(?:y|ed|ies)|scoliosis|tendinitis|tendonitis)\b",
    flags=re.IGNORECASE,
)


def normalize_body_analysis(payload: Mapping[str, Any]) -> NormalizedBodyAnalysis:
    """Validate and normalize a provider payload without retaining provider envelopes."""

    normalized = NormalizedBodyAnalysis.model_validate(payload)
    for finding in normalized.findings:
        if _MEDICAL_CLAIM_PATTERN.search(finding.explanation):
            raise MedicalClaimError("body analysis cannot contain medical diagnostic claims")
    return normalized
