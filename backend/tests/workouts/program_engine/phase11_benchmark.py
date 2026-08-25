"""Reproducible Phase 11 benchmark for the deterministic resistance engine.

The CLI path loads the real exercise and template catalog from a read-only database
snapshot, maps deterministic profile fixtures through the production request mapper,
and calls the production ``generate_program`` entrypoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Register the cross-module review mapper before SQLAlchemy configures workout models.
import app.workout_reviews.models  # noqa: F401
from app.exercises.enums import Equipment, ExerciseCautionTag, MovementPattern, MuscleGroup
from app.profile.enums import (
    ExperienceLevel,
    FitnessGoal,
    HomeTrainingSetup,
    Sex,
    TrainingCaution,
    TrainingLocation,
)
from app.profile.service import ProfileSnapshot
from app.training_templates.engine_reference import load_template_references
from app.training_templates.seed_data import TRAINING_PROGRAM_TEMPLATE_SEEDS
from app.training_templates.service import seed_training_program_templates
from app.workouts.program_engine.duration_policy import (
    OFFICIAL_SESSION_DURATIONS,
    get_session_duration_policy,
)
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import (
    BalanceAbility,
    Goal,
    ImpactLimit,
    LoadLimit,
    PhysicalJobDemand,
    RecoveryRating,
)
from app.workouts.program_engine.recovery import recovery_spacing_is_valid
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    BodyAnalysisInfluence,
    BodyAnalysisPriority,
    ExerciseCandidate,
    ProgramGenerationRequest,
    ProgramGenerationResult,
    RecentTrainingHistory,
    TemplateReference,
)
from app.workouts.program_engine.supplemental_policy import main_exercise_count
from app.workouts.schemas import ProgramGenerationOverrides
from app.workouts.service import WorkoutGenerationService, WorkoutGenerationSettings

SUPPORTED_MATRIX: tuple[tuple[str, int], ...] = (
    (ExperienceLevel.FIRST_MONTH.value, 2),
    (ExperienceLevel.FIRST_MONTH.value, 3),
    (ExperienceLevel.FIRST_MONTH.value, 4),
    (ExperienceLevel.BEGINNER.value, 2),
    (ExperienceLevel.BEGINNER.value, 3),
    (ExperienceLevel.BEGINNER.value, 4),
    (ExperienceLevel.INTERMEDIATE.value, 2),
    (ExperienceLevel.INTERMEDIATE.value, 3),
    (ExperienceLevel.INTERMEDIATE.value, 4),
    (ExperienceLevel.INTERMEDIATE.value, 5),
    (ExperienceLevel.INTERMEDIATE.value, 6),
    (ExperienceLevel.ADVANCED.value, 3),
    (ExperienceLevel.ADVANCED.value, 4),
    (ExperienceLevel.ADVANCED.value, 5),
    (ExperienceLevel.ADVANCED.value, 6),
)
PROFILE_VARIANTS_PER_CELL = 25
EXPECTED_PROFILE_COUNT = len(SUPPORTED_MATRIX) * PROFILE_VARIANTS_PER_CELL
EXPECTED_TEMPLATE_SLUGS = tuple(
    sorted(seed.slug for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS if seed.is_active)
)
EXPECTED_TEMPLATE_COUNT = len(EXPECTED_TEMPLATE_SLUGS)
EXPECTED_TEMPLATE_SEED_HASH = hashlib.sha256(
    json.dumps(
        [asdict(seed) for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS],
        default=str,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
).hexdigest()

MAJOR_MUSCLES = frozenset(
    {
        MuscleGroup.CHEST,
        MuscleGroup.BACK,
        MuscleGroup.SHOULDERS,
        MuscleGroup.GLUTES,
        MuscleGroup.QUADRICEPS,
        MuscleGroup.HAMSTRINGS,
    }
)

_PRIORITY_MUSCLES_BY_VARIANT: dict[int, tuple[MuscleGroup, ...]] = {
    1: (MuscleGroup.CHEST,),
    3: (MuscleGroup.BACK,),
    5: (MuscleGroup.SHOULDERS,),
    7: (MuscleGroup.QUADRICEPS,),
    9: (MuscleGroup.HAMSTRINGS,),
    11: (MuscleGroup.GLUTES,),
}

UNSAT_CAUSES = frozenset(
    {
        "legitimate catalog limitation",
        "legitimate constraint limitation",
        "quality failure",
        "engine bug",
    }
)
LEGITIMATE_UNSAT_CAUSES = frozenset(
    {"legitimate catalog limitation", "legitimate constraint limitation"}
)


@dataclass(frozen=True)
class BenchmarkProfile:
    profile_id: str
    variant: int
    experience_level: ExperienceLevel
    resistance_days: int
    goal: Goal
    priority_muscles: tuple[MuscleGroup, ...]
    body_analysis_priorities: tuple[tuple[MuscleGroup, str], ...]
    sex: Sex | None
    duration_minutes: int
    equipment_label: str
    training_location: TrainingLocation
    home_setup: HomeTrainingSetup | None
    available_equipment_override: frozenset[Equipment] | None = None
    training_cautions: tuple[TrainingCaution, ...] = ()
    blocked_movement_patterns: tuple[MovementPattern, ...] = ()
    blocked_caution_tags: tuple[ExerciseCautionTag, ...] = ()
    impact_limit: ImpactLimit | None = None
    axial_load_limit: LoadLimit | None = None
    overhead_limit: LoadLimit | None = None
    balance_requirement: BalanceAbility | None = None
    sleep_quality: RecoveryRating = RecoveryRating.AVERAGE
    stress_level: RecoveryRating = RecoveryRating.AVERAGE
    physical_job_demand: PhysicalJobDemand = PhysicalJobDemand.LOW
    recent_recovery_problems: bool = False
    previous_volume_sets: int | None = None
    blocked_exercise_tokens: tuple[str, ...] = ()
    physical_limitation_note: str | None = None
    training_age_months: int | None = None
    allowed_range_of_motion: frozenset[str] = frozenset()


def _profile_id(experience: ExperienceLevel, days: int, variant: int) -> str:
    return str(
        uuid5(NAMESPACE_URL, f"https://fitsho.test/phase11/{experience.value}/{days}/{variant}")
    )


def _variant_profile(experience: ExperienceLevel, days: int, variant: int) -> BenchmarkProfile:
    goals = (
        Goal.STRENGTH,
        Goal.HYPERTROPHY,
        Goal.BODY_RECOMPOSITION,
        Goal.FAT_LOSS,
        Goal.GENERAL_FITNESS,
    )
    goal = goals[variant % len(goals)]
    if experience is ExperienceLevel.FIRST_MONTH:
        goal = Goal.GENERAL_FITNESS

    locations = (TrainingLocation.GYM, TrainingLocation.HOME)
    location = locations[variant % 2]

    home_setups = (
        ("home_bw", HomeTrainingSetup.BODYWEIGHT_ONLY, frozenset({Equipment.BODYWEIGHT})),
        (
            "home_db",
            HomeTrainingSetup.DUMBBELLS_AVAILABLE,
            frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL}),
        ),
        (
            "home_band",
            HomeTrainingSetup.BODYWEIGHT_ONLY,
            frozenset({Equipment.BODYWEIGHT, Equipment.RESISTANCE_BAND}),
        ),
        (
            "home_db_bench",
            HomeTrainingSetup.DUMBBELLS_AVAILABLE,
            frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.BENCH}),
        ),
        (
            "home_db_pullup",
            HomeTrainingSetup.DUMBBELLS_AVAILABLE,
            frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.PULL_UP_BAR}),
        ),
        (
            "home_band_pullup",
            HomeTrainingSetup.BODYWEIGHT_ONLY,
            frozenset({Equipment.BODYWEIGHT, Equipment.RESISTANCE_BAND, Equipment.PULL_UP_BAR}),
        ),
        (
            "home_all",
            HomeTrainingSetup.DUMBBELLS_AVAILABLE,
            frozenset(
                {
                    Equipment.BODYWEIGHT,
                    Equipment.DUMBBELL,
                    Equipment.RESISTANCE_BAND,
                    Equipment.BENCH,
                    Equipment.PULL_UP_BAR,
                }
            ),
        ),
    )
    gym_setups = (
        ("full_gym", None, None),
        (
            "limited_gym",
            None,
            frozenset(
                {
                    Equipment.BODYWEIGHT,
                    Equipment.DUMBBELL,
                    Equipment.BENCH,
                    Equipment.BARBELL,
                    Equipment.CABLE,
                }
            ),
        ),
    )

    eq_override: frozenset[Equipment] | None
    if location == TrainingLocation.HOME:
        label, home_setup, eq_override = home_setups[variant % len(home_setups)]
    else:
        label, _, eq_override_raw = gym_setups[variant % len(gym_setups)]
        home_setup = None
        eq_override = eq_override_raw

    training_ages = {
        ExperienceLevel.FIRST_MONTH: (0, 1),
        ExperienceLevel.BEGINNER: (2, 6, 12),
        ExperienceLevel.INTERMEDIATE: (18, 24, 36, 48),
        ExperienceLevel.ADVANCED: (60, 84, 120),
    }
    age_options = training_ages[experience]
    training_age = age_options[variant % len(age_options)]

    duration = OFFICIAL_SESSION_DURATIONS[variant % len(OFFICIAL_SESSION_DURATIONS)]
    sexes = (Sex.MALE, Sex.FEMALE, None)
    sex = sexes[variant % len(sexes)]

    impact_limit = ImpactLimit.LOW if variant == 16 else None
    axial_load_limit = LoadLimit.LOW if variant == 17 else None
    overhead_limit = LoadLimit.LOW if variant == 18 else None
    balance_requirement = BalanceAbility.LIMITED if variant == 19 else None
    training_cautions: tuple[TrainingCaution, ...] = ()
    if variant == 20:
        training_cautions = (TrainingCaution.LOWER_BACK,)
    elif variant == 21:
        training_cautions = (TrainingCaution.SHOULDER,)
    elif variant == 22:
        training_cautions = (TrainingCaution.KNEE,)
    elif variant == 24:
        training_cautions = (TrainingCaution.WRIST,)

    if variant == 23:
        allowed_rom = frozenset({"spinal_flexion"})
    elif variant == 24:
        allowed_rom = frozenset({"deep_knee_flexion"})
    else:
        allowed_rom = frozenset()

    return BenchmarkProfile(
        profile_id=_profile_id(experience, days, variant),
        variant=variant,
        experience_level=experience,
        resistance_days=days,
        goal=goal,
        priority_muscles=_PRIORITY_MUSCLES_BY_VARIANT.get(variant, ()),
        body_analysis_priorities=(),
        sex=sex,
        duration_minutes=duration,
        equipment_label=label,
        training_location=location,
        home_setup=home_setup,
        available_equipment_override=eq_override,
        training_age_months=training_age,
        allowed_range_of_motion=allowed_rom,
        impact_limit=impact_limit,
        axial_load_limit=axial_load_limit,
        overhead_limit=overhead_limit,
        balance_requirement=balance_requirement,
        training_cautions=training_cautions,
    )


def benchmark_profiles() -> tuple[BenchmarkProfile, ...]:
    return tuple(
        _variant_profile(ExperienceLevel(experience), days, variant)
        for experience, days in SUPPORTED_MATRIX
        for variant in range(PROFILE_VARIANTS_PER_CELL)
    )


NEGATIVE_PROFILES: tuple[BenchmarkProfile, ...] = (
    _variant_profile(ExperienceLevel.FIRST_MONTH, 5, 0),
    _variant_profile(ExperienceLevel.BEGINNER, 5, 1),
    _variant_profile(ExperienceLevel.INTERMEDIATE, 7, 2),
    _variant_profile(ExperienceLevel.ADVANCED, 2, 3),
)


_PROFILE_GOALS: dict[Goal, FitnessGoal] = {
    Goal.STRENGTH: FitnessGoal.STRENGTH,
    Goal.HYPERTROPHY: FitnessGoal.BUILD_MUSCLE,
    Goal.MUSCLE_GAIN: FitnessGoal.BUILD_MUSCLE,
    Goal.BODY_RECOMPOSITION: FitnessGoal.BODY_RECOMPOSITION,
    Goal.FAT_LOSS: FitnessGoal.FAT_LOSS,
    Goal.GENERAL_FITNESS: FitnessGoal.IMPROVE_FITNESS,
}


def _body_analysis(profile: BenchmarkProfile) -> BodyAnalysisInfluence | None:
    if not profile.body_analysis_priorities:
        return None
    return BodyAnalysisInfluence(
        analysis_id=uuid5(
            NAMESPACE_URL, f"https://fitsho.test/phase11/{profile.profile_id}/analysis"
        ),
        result_version_id=uuid5(
            NAMESPACE_URL, f"https://fitsho.test/phase11/{profile.profile_id}/result"
        ),
        analysis_revision=1,
        schema_version="1.0",
        source="fully_reviewed",
        overall_confidence=0.92,
        priorities=tuple(
            BodyAnalysisPriority(
                muscle=muscle,
                classification=classification,
                confidence=0.92 if classification == "clear_lag" else 0.82,
                severity=0.85 if classification == "clear_lag" else 0.45,
                emphasis=(muscle.value,),
            )
            for muscle, classification in profile.body_analysis_priorities
        ),
    )


def profile_to_request(
    profile: BenchmarkProfile,
    *,
    enforce_matrix: bool = True,
) -> ProgramGenerationRequest:
    """Map a fixture through the production service's profile request mapper."""

    profile_stub = SimpleNamespace(
        user_id=UUID(profile.profile_id),
        birth_date=date(1992, 4, 15),
        sex=profile.sex or Sex.OTHER,
        height_cm=175,
        fitness_goal=_PROFILE_GOALS[profile.goal],
        experience_level=profile.experience_level,
        training_age_months=profile.training_age_months
        if profile.training_age_months is not None
        else {
            ExperienceLevel.FIRST_MONTH: 0,
            ExperienceLevel.BEGINNER: 6,
            ExperienceLevel.INTERMEDIATE: 24,
            ExperienceLevel.ADVANCED: 60,
        }[profile.experience_level],
        preferred_weekdays=None,
        priority_muscles=[muscle.value for muscle in profile.priority_muscles],
        training_days_per_week=(
            profile.resistance_days
            if enforce_matrix
            else (2 if profile.experience_level is not ExperienceLevel.ADVANCED else 3)
        ),
        training_location=profile.training_location,
        home_training_setup=profile.home_setup,
        session_duration_minutes=45 if profile.duration_minutes == 40 else profile.duration_minutes,
        physical_limitations=profile.physical_limitation_note,
        plan_duration_weeks=4,
        training_caution_items=[
            SimpleNamespace(caution=item) for item in profile.training_cautions
        ],
    )
    measurement_stub = SimpleNamespace(weight_kg=75.0)
    source = ProfileSnapshot(
        profile=cast(Any, profile_stub),
        measurement=cast(Any, measurement_stub),
    )
    override_values: dict[str, object] = {}
    if profile.available_equipment_override is not None:
        override_values["available_equipment"] = profile.available_equipment_override
    if profile.allowed_range_of_motion:
        override_values["allowed_range_of_motion"] = profile.allowed_range_of_motion
    if profile.blocked_movement_patterns:
        override_values["blocked_movement_patterns"] = frozenset(profile.blocked_movement_patterns)
    if profile.blocked_caution_tags:
        override_values["blocked_caution_tags"] = frozenset(profile.blocked_caution_tags)
    for name in ("impact_limit", "axial_load_limit", "overhead_limit", "balance_requirement"):
        value = getattr(profile, name)
        if value is not None:
            override_values[name] = value
    if profile.sleep_quality is not RecoveryRating.AVERAGE:
        override_values["sleep_quality"] = profile.sleep_quality
    if profile.stress_level is not RecoveryRating.AVERAGE:
        override_values["stress_level"] = profile.stress_level
    if profile.physical_job_demand is not PhysicalJobDemand.LOW:
        override_values["physical_job_demand"] = profile.physical_job_demand
    if profile.recent_recovery_problems or profile.previous_volume_sets is not None:
        override_values["recent_training_history"] = RecentTrainingHistory(
            consistent_weeks=24,
            completed_session_ratio=0.9,
            previous_weekly_direct_sets_by_muscle=(
                {MuscleGroup.CHEST: float(profile.previous_volume_sets)}
                if profile.previous_volume_sets is not None
                else {}
            ),
            previous_volume_source="prescribed_plan" if profile.previous_volume_sets else "none",
            recovery_problems=profile.recent_recovery_problems,
        )
    overrides = (
        ProgramGenerationOverrides.model_construct(**cast(Any, override_values))
        if override_values
        else None
    )
    mapper = object.__new__(WorkoutGenerationService)
    request = WorkoutGenerationService._to_program_request(
        mapper,
        source,
        overrides,
        _body_analysis(profile),
    )
    updates: dict[str, object] = {}
    if profile.sex is None:
        updates["biological_sex_optional"] = None
    if not enforce_matrix:
        updates["available_training_days"] = profile.resistance_days
    if profile.duration_minutes == 40:
        # TEST-ONLY bypass for legacy Phase 11.6 40-minute cases
        updates["session_duration_minutes"] = 40

    if updates:
        request = request.model_copy(update=updates)
    return request


def apply_catalog_constraints(
    request: ProgramGenerationRequest,
    profile: BenchmarkProfile,
    catalog: Sequence[ExerciseCandidate],
) -> ProgramGenerationRequest:
    blocked = frozenset(
        item.id
        for item in catalog
        if any(token in item.name.lower() for token in profile.blocked_exercise_tokens)
    )
    return request.model_copy(update={"blocked_exercises": blocked}) if blocked else request


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return _jsonable(value.model_dump(mode="json"))
    if is_dataclass(value):
        return _jsonable(asdict(cast(Any, value)))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_jsonable(item) for item in value]
    return value


def canonical_fingerprint(result: ProgramGenerationResult) -> str:
    payload = json.dumps(_jsonable(result), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _prepare_template_library(db: Session) -> tuple[TemplateReference, ...]:
    """Reseed and fail if active templates differ from the production seed intent."""
    seed_training_program_templates(db)
    references = load_template_references(db)
    actual_slugs = tuple(sorted(item.slug for item in references))
    if actual_slugs != EXPECTED_TEMPLATE_SLUGS:
        missing = sorted(set(EXPECTED_TEMPLATE_SLUGS) - set(actual_slugs))
        unexpected = sorted(set(actual_slugs) - set(EXPECTED_TEMPLATE_SLUGS))
        raise RuntimeError(
            "active template library differs from production seed intent: "
            f"expected={EXPECTED_TEMPLATE_COUNT} actual={len(references)} "
            f"missing={missing} unexpected={unexpected}"
        )
    return references


def _trace_entry(result: ProgramGenerationResult, stage: str) -> dict[str, object] | None:
    if result.program is not None:
        entries = result.program.decision_trace
    else:
        entries = result.decision_trace
    return next((entry for entry in entries if entry.get("stage") == stage), None)


def _mapping_sequence(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, (tuple, list)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _number(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _template_stats(result: ProgramGenerationResult) -> dict[str, object]:
    selection = _trace_entry(result, "template_selection") or {}
    selected = selection.get("selected")
    entries = result.program.decision_trace if result.program is not None else result.decision_trace
    attempts = tuple(entry for entry in entries if entry.get("stage") == "template_attempt")
    reference = (
        result.program.aggregate_metrics.get("reference_template")
        if result.program is not None
        else None
    )
    attempted = bool(attempts) or isinstance(selected, str)
    succeeded = isinstance(reference, str)
    reasons: list[str] = []
    rejection_categories: list[str] = []
    attempt_reasons: list[str] = []
    attempt_rejection_categories: list[str] = []
    if attempts:
        for entry in attempts:
            if entry.get("status") != "rejected":
                continue
            attempt_reasons.extend(_string_values(entry.get("reason_codes")))
            category = entry.get("rejection_category")
            if isinstance(category, str):
                attempt_rejection_categories.append(category)
        if attempted and not succeeded:
            first_rejection = next(
                (entry for entry in attempts if entry.get("status") == "rejected"),
                None,
            )
            if first_rejection is not None:
                reasons.extend(_string_values(first_rejection.get("reason_codes")))
                category = first_rejection.get("rejection_category")
                if isinstance(category, str):
                    rejection_categories.append(category)
    elif attempted and not succeeded:
        for entry in entries:
            if entry.get("stage") == "template_reference":
                reasons.extend(_string_values(entry.get("reason_codes")))
                category = entry.get("rejection_category")
                if isinstance(category, str):
                    rejection_categories.append(category)
        if not reasons:
            rejection_categories.append("ADAPTATION_EXHAUSTED")
    if not attempted:
        reasons.extend(
            code
            for item in _mapping_sequence(selection.get("hard_rejections", ()))
            for code in _string_values(item.get("reason_codes"))
        )
        category = selection.get("rejection_category")
        rejection_categories.append(
            category if isinstance(category, str) else "NO_DAYS_LEVEL_CANDIDATE"
        )
    dynamic = result.program is not None and reference is None
    candidates = _mapping_sequence(selection.get("candidates", ()))
    selected_score = next(
        (item.get("score") for item in candidates if item.get("slug") == selected),
        None,
    )
    successful_score = next(
        (item.get("score") for item in candidates if item.get("slug") == reference),
        None,
    )
    successful_attempt = next(
        (item for item in attempts if item.get("status") == "succeeded"),
        None,
    )
    successful_rank = successful_attempt.get("rank") if successful_attempt is not None else None
    successful_attempt_depth = successful_rank if isinstance(successful_rank, int) else None
    alternatives_exhausted = any(
        entry.get("stage") == "template_recovery" and entry.get("status") == "exhausted"
        for entry in entries
    )
    return {
        "attempted": attempted,
        "succeeded": succeeded,
        "fallback_activated": dynamic,
        "fallback_succeeded": dynamic and result.is_success,
        "selected_template": selected,
        "successful_template": reference,
        "template_path": reference,
        "attempted_templates": attempts,
        "attempt_depth": len(attempts) if attempts else int(attempted),
        "successful_attempt_depth": successful_attempt_depth,
        "recovered_with_alternative": bool(
            succeeded and successful_attempt_depth is not None and successful_attempt_depth > 1
        ),
        "alternatives_exhausted": alternatives_exhausted,
        "reason_codes": tuple(dict.fromkeys(reasons)),
        "rejection_categories": tuple(dict.fromkeys(rejection_categories)),
        "attempt_reason_codes": tuple(dict.fromkeys(attempt_reasons)),
        "attempt_rejection_categories": tuple(dict.fromkeys(attempt_rejection_categories)),
        "selected_score_breakdown": selected_score,
        "successful_score_breakdown": successful_score,
        "score_breakdown": candidates,
    }


def _string_values(value: object) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list, set, frozenset)):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _duration_policy_failure(
    *,
    requested_minutes: int,
    estimated_total_minutes: int,
    main_exercises: int,
    minimum_exercises: int,
    reason_codes: Sequence[str],
) -> str | None:
    policy = get_session_duration_policy(requested_minutes)
    workout_minutes = policy.workout_minutes(
        estimated_total_minutes, RULESET.general_warmup_minutes
    )
    reasons = set(reason_codes)
    if workout_minutes > policy.maximum_minutes:
        core_extension = (
            "SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE" in reasons
            and workout_minutes <= policy.core_preservation_maximum_minutes
        )
        return None if core_extension else "above_maximum"
    if workout_minutes >= policy.minimum_minutes or main_exercises >= minimum_exercises:
        return None
    if reasons.intersection(
        {
            "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS",
            "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD",
        }
    ):
        return None
    return "below_minimum_incomplete"


def _classify_final_unsat(result: ProgramGenerationResult) -> dict[str, object]:
    error_code = result.error_code.value if result.error_code is not None else "UNKNOWN"
    errors = tuple(dict.fromkeys((error_code, *result.errors)))
    error_set = set(errors)
    if error_code == "NO_AVAILABLE_EQUIPMENT_MATCH" or "NO_ELIGIBLE_EXERCISES" in error_set:
        cause = "legitimate catalog limitation"
    elif error_set.intersection(
        {
            "VALIDATION_FAILURE",
            "DAY_COUNT_INVARIANT_FAILED",
            "REQUESTED_TRAINING_DAYS_MISMATCH",
        }
    ):
        cause = "engine bug"
    elif error_set.intersection(
        {
            "REQUIRED_SLOT_HARD_IMPOSSIBILITY",
            "EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED",
            "DURATION_RECOVERY_HARD_IMPOSSIBILITY",
            "RECOVERY_SPACING_INVALID",
            "SESSION_DURATION_EXCEEDED",
        }
    ):
        cause = "legitimate constraint limitation"
    elif "WEEKLY_VOLUME_OUTSIDE_ACCEPTABLE_RANGE" in error_set:
        cause = "quality failure"
    elif error_code in {"NO_SAFE_EXERCISE_FOR_PATTERN", "NO_EXERCISES_FOR_REQUIRED_MUSCLE"}:
        cause = "legitimate catalog limitation"
    else:
        cause = "quality failure"
    return {"cause": cause, "evidence": errors}


def _semantic_substitution_audit(
    result: ProgramGenerationResult,
    template: Mapping[str, object],
) -> dict[str, int]:
    if result.program is None:
        return {
            "successful_valid_substitutions": 0,
            "recovered_intermediate_attempts": 0,
            "legitimate_no_valid_replacements": 0,
            "final_semantic_degradations": 0,
            "explained_final_semantic_degradations": 0,
            "unexplained_final_semantic_failures": 0,
        }
    program = result.program
    metrics = program.aggregate_metrics
    trace = next(
        (
            entry
            for entry in program.decision_trace
            if entry.get("stage") == "substitution_observability"
        ),
        {},
    )
    decisions = _mapping_sequence(trace.get("decisions"))
    no_valid_display = sum(
        not _object_sequence(item.get("alternative_exercise_ids"))
        and item.get("cause") == "display_alternative"
        for item in decisions
    )
    no_valid_repair = sum(
        not _object_sequence(item.get("alternative_exercise_ids"))
        and item.get("cause") != "display_alternative"
        for item in decisions
    )
    recovered_templates = 0
    if bool(template.get("recovered_with_alternative")):
        recovered_templates = sum(
            item.get("status") == "rejected"
            for item in _mapping_sequence(template.get("attempted_templates"))
        )

    semantic_warning = "SEMANTIC_SLOT_MISMATCH_SELECTED" in program.validation_report.warnings
    relaxed_slots = _object_sequence(metrics.get("relaxed_required_slots"))
    hard_incompatible = sum(
        any("HARD_INCOMPATIBLE" in code for code in item.reason_codes)
        for day in program.weekly_schedule
        for item in day.exercises
    )
    final_degradations = int(semantic_warning) + hard_incompatible
    explained_degradations = int(semantic_warning and bool(relaxed_slots))
    unexplained = final_degradations - explained_degradations
    return {
        "successful_valid_substitutions": int(_number(metrics.get("substitution_successes"))),
        "recovered_intermediate_attempts": recovered_templates + no_valid_repair,
        "legitimate_no_valid_replacements": no_valid_display,
        "final_semantic_degradations": final_degradations,
        "explained_final_semantic_degradations": explained_degradations,
        "unexplained_final_semantic_failures": unexplained,
    }


def _audit_program(
    profile: BenchmarkProfile,
    request: ProgramGenerationRequest,
    result: ProgramGenerationResult,
    catalog: Sequence[ExerciseCandidate],
) -> tuple[dict[str, object], ...]:
    if result.program is None:
        return ()
    program = result.program
    issues: list[dict[str, object]] = []

    def issue(
        code: str,
        severity: str,
        message: str,
        *,
        classification: str | None = None,
        explanation: str | None = None,
    ) -> None:
        final_classification = classification or ("B" if severity == "constraint" else "A")
        issues.append(
            {
                "code": code,
                "severity": severity,
                "message": message,
                "classification": final_classification,
                "classification_reason": explanation
                or (
                    "legitimate documented constraint or tradeoff"
                    if final_classification == "B"
                    else "proven final-program defect"
                ),
            }
        )

    catalog_by_id = {item.id: item for item in catalog}
    for day in program.weekly_schedule:
        for item in day.exercises:
            candidate = catalog_by_id.get(item.exercise_id)
            if candidate is None:
                issue("EXERCISE_NOT_IN_CATALOG", "engine_bug", item.exercise_name)
                continue
            if not candidate.equipment.issubset(request.available_equipment):
                issue("UNAVAILABLE_EQUIPMENT", "engine_bug", item.exercise_name)
            if candidate.movement_pattern in request.blocked_movement_patterns:
                issue("LIMITATION_VIOLATION_PATTERN", "engine_bug", item.exercise_name)
            if candidate.caution_tags.intersection(request.blocked_caution_tags):
                issue("LIMITATION_VIOLATION_CAUTION", "engine_bug", item.exercise_name)
            if item.prescription_mode.value == "reps" and request.primary_goal is Goal.STRENGTH:
                if (
                    item.exercise_type.value not in {"isolation", "core"}
                    and (item.rep_max or 0) > 15
                ):
                    issue("INAPPROPRIATE_STRENGTH_REPS", "quality", item.exercise_name)
            if item.sets > RULESET.max_working_sets_per_exercise_absolute:
                issue("EXCESSIVE_EXERCISE_SETS", "engine_bug", item.exercise_name)
            if "STRENGTH_PRIMARY_COMPOUND" in item.reason_codes and item.rest_seconds < 60:
                issue("INSUFFICIENT_PRIMARY_STRENGTH_REST", "quality", item.exercise_name)

    if len(program.weekly_schedule) != profile.resistance_days:
        issue("DAY_COUNT_MISMATCH", "engine_bug", str(len(program.weekly_schedule)))
    metrics = program.aggregate_metrics
    ranges = metrics.get("volume_ranges_by_muscle", {})
    range_mapping = ranges if isinstance(ranges, Mapping) else {}
    missing_major_coverage = _missing_major_muscle_coverage(range_mapping)
    if missing_major_coverage:
        constrained_coverage = all(
            isinstance(values := range_mapping.get(muscle), Mapping)
            and bool(_string_values(values.get("constraint_reason_codes")))
            for muscle in missing_major_coverage
        )
        issue(
            "MISSING_MAJOR_MUSCLE_COVERAGE",
            "quality",
            ",".join(missing_major_coverage),
            classification="B" if constrained_coverage else "A",
            explanation=(
                "hard volume, session-feasibility, or catalog constraints "
                "prevented minimum coverage"
                if constrained_coverage
                else "minimum major-muscle coverage is missing without a recorded constraint"
            ),
        )
    if not recovery_spacing_is_valid(program.weekly_schedule, RULESET):
        issue("RECOVERY_SPACING_INVALID", "quality", "direct/exposure overlap")

    duration_trace = _trace_entry(result, "session_duration") or {}
    duration_reasons = _string_values(duration_trace.get("reason_codes"))
    for day in program.weekly_schedule:
        duration_failure = _duration_policy_failure(
            requested_minutes=request.session_duration_minutes,
            estimated_total_minutes=day.estimated_duration_minutes,
            main_exercises=main_exercise_count(day.exercises),
            minimum_exercises=(
                3
                if request.session_duration_minutes <= RULESET.short_session_minutes
                else RULESET.minimum_exercises_per_session
            ),
            reason_codes=duration_reasons,
        )
        if duration_failure is not None:
            issue(
                "DURATION_OUTSIDE_POLICY",
                "quality",
                f"day={day.day_index}:{duration_failure}",
                explanation="final resistance duration violates the canonical duration policy",
            )

    priority_metrics = metrics.get("priority_metrics", {})
    if isinstance(priority_metrics, Mapping):
        for muscle in profile.priority_muscles:
            metric = priority_metrics.get(muscle.value, {})
            if isinstance(metric, Mapping) and metric.get("status") != "satisfied":
                volume_range = ranges.get(muscle.value, {}) if isinstance(ranges, Mapping) else {}
                severity = (
                    "constraint"
                    if isinstance(volume_range, Mapping)
                    and _hard_priority_minimum_is_met(volume_range)
                    else "quality"
                )
                issue("EXPLICIT_PRIORITY_PARTIAL", severity, muscle.value)
        for muscle, _classification in profile.body_analysis_priorities:
            metric = priority_metrics.get(muscle.value, {})
            if isinstance(metric, Mapping) and metric.get("status") != "satisfied":
                reason_codes = set(_string_values(metric.get("reason_codes")))
                severity = (
                    "constraint"
                    if profile.priority_muscles or "PRIORITY_TARGET_CONSTRAINED" in reason_codes
                    else "quality"
                )
                issue("BODY_ANALYSIS_PRIORITY_PARTIAL", severity, muscle.value)
    if isinstance(ranges, Mapping):
        for muscle, values in ranges.items():
            if isinstance(values, Mapping) and values.get("status") == "outside_acceptable_range":
                constrained = bool(_string_values(values.get("constraint_reason_codes")))
                issue(
                    "VOLUME_OUTSIDE_ACCEPTABLE_RANGE",
                    "quality",
                    str(muscle),
                    classification="B" if constrained else "A",
                    explanation=(
                        "recorded hard/session constraint prevented acceptable-range volume"
                        if constrained
                        else "volume is outside the acceptable range without a recorded constraint"
                    ),
                )

    if _has_redundant_near_identical_movements(program.weekly_schedule):
        issue("REDUNDANT_NEAR_IDENTICAL_MOVEMENTS", "quality", "same-session duplication")
    if any(
        sum(item.exercise_id == candidate_id for item in day.exercises) > 2
        for day in program.weekly_schedule
        for candidate_id in {item.exercise_id for item in day.exercises}
    ):
        issue("EXCESSIVE_REPEATED_EXERCISE", "quality", "same session")

    for day in program.weekly_schedule:
        if day.cardio is not None and day.cardio.intensity.value == "vigorous":
            issue("CARDIO_INTENSITY_TOO_HIGH", "quality", day.cardio.modality_name)
    return tuple(issues)


def _hard_priority_minimum_is_met(volume_range: Mapping[str, object]) -> bool:
    effective_met = _number(volume_range.get("actual_effective_volume")) >= _number(
        volume_range.get("minimum_effective_sets")
    )
    if not bool(volume_range.get("direct_minimum_required")):
        return effective_met
    return effective_met and _number(volume_range.get("actual_direct_volume")) >= _number(
        volume_range.get("minimum_direct_sets")
    )


def _missing_major_muscle_coverage(
    volume_ranges: Mapping[str, object],
) -> tuple[str, ...]:
    missing: list[str] = []
    for muscle in sorted(MAJOR_MUSCLES, key=lambda item: item.value):
        values = volume_ranges.get(muscle.value)
        if not isinstance(values, Mapping) or not bool(values.get("minimum_coverage_required")):
            continue
        if _number(values.get("actual_effective_volume")) < _number(
            values.get("minimum_effective_sets")
        ):
            missing.append(muscle.value)
    return tuple(missing)


def _has_redundant_near_identical_movements(days: Sequence[object]) -> bool:
    for day in days:
        exercises = tuple(getattr(day, "exercises", ()))
        exercise_ids = [getattr(item, "exercise_id", None) for item in exercises]
        if len(exercise_ids) != len(set(exercise_ids)):
            return True
        signatures = Counter(
            (
                getattr(item, "primary_muscle", None),
                getattr(item, "movement_pattern", None),
                getattr(item, "exercise_type", None),
                frozenset(getattr(item, "equipment", ())),
            )
            for item in exercises
        )
        if any(count >= 3 for count in signatures.values()):
            return True
    return False


def _audit_quality_metrics(
    request: ProgramGenerationRequest,
    result: ProgramGenerationResult,
) -> dict[str, object]:
    if result.program is None:
        return {}
    program = result.program
    quality = cast(Mapping[str, object], program.aggregate_metrics.get("coach_quality", {}))
    ranges = cast(
        Mapping[str, object], program.aggregate_metrics.get("volume_ranges_by_muscle", {})
    )
    volume_fit = _strict_volume_fit(ranges)
    policy = get_session_duration_policy(request.session_duration_minutes)
    duration_trace = _trace_entry(result, "session_duration") or {}
    duration_reasons = set(_string_values(duration_trace.get("reason_codes")))
    durations_fit = all(
        policy.contains_total(day.estimated_duration_minutes, RULESET.general_warmup_minutes)
        for day in program.weekly_schedule
    )
    core_extended = "SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE" in duration_reasons
    if not durations_fit and core_extended:
        durations_fit = all(
            day.estimated_duration_minutes
            <= policy.core_preservation_maximum_total_minutes(RULESET.general_warmup_minutes)
            for day in program.weekly_schedule
        )
    duration_fit = (
        "fit"
        if durations_fit
        else "constrained"
        if duration_reasons.intersection(
            {
                "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS",
                "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD",
            }
        )
        else "failed"
    )
    return {
        "template_preservation": quality.get("template_preservation"),
        "priority_target_satisfaction": quality.get("priority_target_satisfaction"),
        "body_analysis_target_satisfaction": quality.get("body_analysis_target_satisfaction"),
        "volume_fit": volume_fit,
        "muscle_level_volume_fit": _muscle_level_volume_fit(ranges),
        "duration_fit": duration_fit,
        "recovery_fit": quality.get("recovery_fit"),
    }


def _strict_volume_fit(volume_ranges: Mapping[str, object]) -> str:
    """Preserve the Phase 11 whole-program, all-or-nothing volume metric."""

    statuses = {
        str(values.get("status"))
        for values in volume_ranges.values()
        if isinstance(values, Mapping)
    }
    return (
        "fit"
        if statuses and statuses.issubset({"exact_target", "within_flexible_range"})
        else "constrained"
        if "constrained" in statuses
        else "failed"
    )


def _muscle_level_volume_fit(volume_ranges: Mapping[str, object]) -> dict[str, object]:
    tracked = 0
    within = 0
    constrained = 0
    outside = 0
    for values in volume_ranges.values():
        if not isinstance(values, Mapping):
            continue
        tracked += 1
        status = values.get("status")
        if status in {"exact_target", "within_flexible_range"}:
            within += 1
        elif status == "constrained":
            constrained += 1
        else:
            outside += 1
    return {
        "tracked_muscles": tracked,
        "within_target_or_flexible_range": within,
        "constrained": constrained,
        "outside_target": outside,
        "constrained_or_outside_target": constrained + outside,
        "percentage": round(within / tracked * 100, 2) if tracked else None,
    }


def _category(
    result: ProgramGenerationResult,
    template: Mapping[str, object],
    issues: Sequence[Mapping[str, object]],
) -> str:
    if result.program is None:
        return "UNSATISFIED"
    if any(item.get("severity") == "engine_bug" for item in issues):
        return "ENGINE_BUG"
    if any(item.get("severity") == "quality" for item in issues):
        return "QUALITY_ISSUE"
    warnings = result.program.validation_report.warnings
    constrained = warnings or any(item.get("severity") == "constraint" for item in issues)
    return "PASS_WITH_CONSTRAINTS" if constrained else "PASS"


def _construction_path(
    result: ProgramGenerationResult,
    template: Mapping[str, object],
) -> str:
    if result.program is None:
        return "NONE"
    return "TEMPLATE" if bool(template.get("succeeded")) else "FALLBACK"


def _case_record(
    profile: BenchmarkProfile,
    request: ProgramGenerationRequest,
    result: ProgramGenerationResult,
    catalog: Sequence[ExerciseCandidate],
    determinism_fingerprints: tuple[str, ...] = (),
) -> dict[str, object]:
    template = _template_stats(result)
    issues = _audit_program(profile, request, result, catalog)
    program = result.program
    quality = (
        cast(Mapping[str, object], program.aggregate_metrics.get("coach_quality", {}))
        if program
        else {}
    )
    quality_trace = _trace_entry(result, "coach_quality")
    audit_quality = _audit_quality_metrics(request, result)
    final_program = None
    if program is not None:
        final_program = {
            "sessions": len(program.weekly_schedule),
            "days": [
                {
                    "day_index": day.day_index,
                    "weekday": day.weekday,
                    "focus": day.focus,
                    "exercise_count": len(day.exercises),
                    "estimated_duration_minutes": day.estimated_duration_minutes,
                    "exercises": [
                        {
                            "id": str(item.exercise_id),
                            "name": item.exercise_name,
                            "primary_muscle": (
                                item.primary_muscle.value
                                if item.primary_muscle is not None
                                else None
                            ),
                            "secondary_muscles": tuple(
                                muscle.value for muscle in item.secondary_muscles
                            ),
                            "movement_pattern": item.movement_pattern.value,
                            "equipment": tuple(
                                sorted(equipment.value for equipment in item.equipment)
                            ),
                            "caution_tags": tuple(sorted(tag.value for tag in item.caution_tags)),
                            "exercise_type": item.exercise_type.value,
                            "prescription_mode": item.prescription_mode.value,
                            "sets": item.sets,
                            "reps": [item.rep_min, item.rep_max],
                            "rir": item.target_rir,
                            "rest_seconds": item.rest_seconds,
                            "reason_codes": item.reason_codes,
                            "substitutions": [
                                str(item_id) for item_id in item.substitution_exercise_ids
                            ],
                        }
                        for item in day.exercises
                    ],
                    "cardio": _jsonable(day.cardio),
                }
                for day in program.weekly_schedule
            ],
            "direct_volume": program.aggregate_metrics.get("weekly_direct_sets_by_muscle", {}),
            "effective_volume": program.aggregate_metrics.get(
                "weekly_effective_sets_by_muscle", {}
            ),
            "priority_metrics": program.aggregate_metrics.get("priority_metrics", {}),
            "volume_ranges": program.aggregate_metrics.get("volume_ranges_by_muscle", {}),
            "relaxed_required_pattern_groups": program.aggregate_metrics.get(
                "relaxed_required_pattern_groups", ()
            ),
            "relaxed_required_slots": program.aggregate_metrics.get("relaxed_required_slots", ()),
            "substitution_metrics": {
                "substitution_requests": program.aggregate_metrics.get("substitution_requests", 0),  # noqa: E501
                "substitution_successes": program.aggregate_metrics.get(
                    "substitution_successes", 0
                ),
                "substitution_exact_group": program.aggregate_metrics.get(
                    "substitution_exact_group", 0
                ),
                "substitution_exact_semantic_role": program.aggregate_metrics.get(
                    "substitution_exact_semantic_role", 0
                ),
                "substitution_movement_family_fallback": program.aggregate_metrics.get(
                    "substitution_movement_family_fallback", 0
                ),
                "substitution_no_valid_replacement": program.aggregate_metrics.get(
                    "substitution_no_valid_replacement", 0
                ),
            },
            "constraint_count": quality.get("constraint_count", 0),
            "recovery_spacing_valid": recovery_spacing_is_valid(program.weekly_schedule, RULESET),
            "validation": {
                "status": program.validation_report.status.value,
                "errors": program.validation_report.errors,
                "warnings": program.validation_report.warnings,
            },
            "trace": program.decision_trace,
        }
    category = _category(result, template, issues)
    semantic_substitution = _semantic_substitution_audit(result, template)
    return {
        "input": _jsonable(asdict(profile)),
        "request": _jsonable(request),
        "template": _jsonable(template),
        "result": {
            "success": result.is_success,
            "error_code": result.error_code.value if result.error_code else None,
            "errors": result.errors,
            "safety_status": result.safety_status.value if result.safety_status else None,
        },
        "final_program": _jsonable(final_program),
        "quality": _jsonable(quality),
        "quality_trace": _jsonable(quality_trace.get("metrics", {}) if quality_trace else {}),
        "quality_audit": _jsonable(audit_quality),
        "audit_findings": _jsonable(issues),
        "semantic_substitution": semantic_substitution,
        "unsat_classification": (
            _classify_final_unsat(result) if category == "UNSATISFIED" else None
        ),
        "quality_outcome": category,
        "construction_path": _construction_path(result, template),
        "category": category,
        "determinism": {
            "fingerprints": determinism_fingerprints,
            "identical": len(set(determinism_fingerprints)) <= 1,
        },
    }


def _failure_dimensions(record: Mapping[str, object]) -> dict[str, str]:
    input_data = cast(Mapping[str, object], record["input"])
    return {
        "experience_level": str(input_data["experience_level"]),
        "days": str(input_data["resistance_days"]),
        "goal": str(input_data["goal"]),
        "duration": str(input_data["duration_minutes"]),
        "equipment": str(input_data["equipment_label"]),
        "limitations": ",".join(cast(Sequence[str], input_data["training_cautions"])),
    }


def _quality_satisfied(value: object, accepted: frozenset[str]) -> bool:
    if isinstance(value, str):
        return value in accepted
    if isinstance(value, Mapping):
        percentage = value.get("percentage")
        return isinstance(percentage, (int, float)) and float(percentage) >= 100.0
    return False


def _quality_rate(
    records: Sequence[Mapping[str, object]],
    key: str,
    accepted: frozenset[str],
    *,
    source: str = "quality",
) -> dict[str, object]:
    applicable = 0
    satisfied = 0
    outcomes: Counter[str] = Counter()
    for record in records:
        quality = cast(Mapping[str, object], record[source])
        value = quality.get(key)
        if value in (None, "not_applicable"):
            continue
        applicable += 1
        satisfied += _quality_satisfied(value, accepted)
        outcomes[str(value)] += 1
    return {
        "satisfied": satisfied,
        "applicable": applicable,
        "rate": round(satisfied / applicable, 4) if applicable else 0.0,
        "outcomes": dict(sorted(outcomes.items())),
    }


def _template_attempt_metrics(
    template_stats: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    attempt_depths = Counter(
        str(int(_number(item.get("attempt_depth")))) for item in template_stats
    )
    successful_depths = Counter(
        str(int(depth))
        for item in template_stats
        for depth in (_number(item.get("successful_attempt_depth")),)
        if depth > 0
    )
    return {
        "total_template_attempts": sum(
            int(_number(item.get("attempt_depth"))) for item in template_stats
        ),
        "attempt_depth_distribution": dict(sorted(attempt_depths.items())),
        "successful_attempt_depth_distribution": dict(sorted(successful_depths.items())),
        "recovered_with_alternative": sum(
            bool(item.get("recovered_with_alternative")) for item in template_stats
        ),
        "alternatives_exhausted": sum(
            bool(item.get("alternatives_exhausted")) for item in template_stats
        ),
    }


def _aggregate_muscle_level_volume_fit(
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    programs = 0
    tracked = 0
    within = 0
    constrained = 0
    outside = 0
    for record in records:
        quality = cast(Mapping[str, object], record.get("quality_audit", {}))
        metric = quality.get("muscle_level_volume_fit")
        if not isinstance(metric, Mapping):
            continue
        program_tracked = int(_number(metric.get("tracked_muscles")))
        if program_tracked <= 0:
            continue
        programs += 1
        tracked += program_tracked
        within += int(_number(metric.get("within_target_or_flexible_range")))
        constrained += int(_number(metric.get("constrained")))
        outside += int(_number(metric.get("outside_target")))
    return {
        "programs": programs,
        "tracked_muscles": tracked,
        "within_target_or_flexible_range": within,
        "constrained": constrained,
        "outside_target": outside,
        "constrained_or_outside_target": constrained + outside,
        "percentage": round(within / tracked * 100, 2) if tracked else None,
    }


def _aggregate(records: Sequence[Mapping[str, object]], negative_count: int) -> dict[str, object]:
    categories = Counter(str(item["category"]) for item in records)
    for cat in ("PASS", "PASS_WITH_CONSTRAINTS", "QUALITY_ISSUE", "UNSATISFIED", "ENGINE_BUG"):
        categories[cat] += 0
    template = [cast(Mapping[str, object], item["template"]) for item in records]
    template_attempts_metrics = _template_attempt_metrics(template)
    total = len(records)
    template_attempts = sum(bool(item["attempted"]) for item in template)
    template_successes = sum(bool(item["succeeded"]) for item in template)
    fallback_activations = sum(bool(item["fallback_activated"]) for item in template)
    fallback_successes = sum(bool(item["fallback_succeeded"]) for item in template)
    unsatisfied = sum(str(item["category"]) == "UNSATISFIED" for item in records)
    unsat_classifications: Counter[str] = Counter()
    for item in records:
        if str(item["category"]) == "UNSATISFIED":
            classification = _object_mapping(item.get("unsat_classification"))
            unsat_classifications[str(classification.get("cause", "unclassified"))] += 1
    reason_codes = Counter(
        code
        for item in template
        if item["fallback_activated"]
        for code in cast(Sequence[str], item["reason_codes"])
    )
    rejection_categories = Counter(
        category
        for item in template
        if item["fallback_activated"]
        for category in cast(Sequence[str], item["rejection_categories"])
    )
    attempt_reason_codes = Counter(
        code for item in template for code in cast(Sequence[str], item["attempt_reason_codes"])
    )
    attempt_rejection_categories = Counter(
        category
        for item in template
        for category in cast(Sequence[str], item["attempt_rejection_categories"])
    )
    findings = Counter(
        str(finding["code"])
        for item in records
        for finding in cast(Sequence[Mapping[str, object]], item["audit_findings"])
    )
    finding_classifications: dict[str, Counter[str]] = defaultdict(Counter)
    finding_reasons: dict[str, set[str]] = defaultdict(set)
    for item in records:
        for finding in cast(Sequence[Mapping[str, object]], item["audit_findings"]):
            code = str(finding.get("code"))
            finding_classifications[code][str(finding.get("classification"))] += 1
            finding_reasons[code].add(str(finding.get("classification_reason")))
    quality_code_audit = {
        code: {
            "count": count,
            "classifications": dict(sorted(finding_classifications[code].items())),
            "explanations": tuple(sorted(finding_reasons[code])),
        }
        for code, count in sorted(findings.items())
    }
    semantic_keys = (
        "successful_valid_substitutions",
        "recovered_intermediate_attempts",
        "legitimate_no_valid_replacements",
        "final_semantic_degradations",
        "explained_final_semantic_degradations",
        "unexplained_final_semantic_failures",
    )
    semantic_substitution = {
        key: sum(
            int(_number(_object_mapping(item.get("semantic_substitution")).get(key)))
            for item in records
        )
        for key in semantic_keys
    }
    feasible = total - unsatisfied
    quality_passes = categories["PASS"] + categories["PASS_WITH_CONSTRAINTS"]
    determinism = sum(
        1 for r in records if cast(Mapping[str, object], r.get("determinism", {})).get("identical")
    )
    determinism_runs = sum(1 for r in records if r.get("determinism"))
    substitutions_total = sum(
        int(
            _number(
                cast(
                    Mapping[str, object],
                    cast(Mapping[str, object], r.get("final_program", {})).get(
                        "substitution_metrics", {}
                    ),
                ).get("substitution_successes", 0)  # noqa: E501
            )
        )
        if r.get("final_program")
        else 0
        for r in records
    )
    substitutions_requests = sum(
        int(
            _number(
                cast(
                    Mapping[str, object],
                    cast(Mapping[str, object], r.get("final_program", {})).get(
                        "substitution_metrics", {}
                    ),
                ).get("substitution_requests", 0)  # noqa: E501
            )
        )
        if r.get("final_program")
        else 0
        for r in records
    )
    substitutions_exact_group = sum(
        int(
            _number(
                cast(
                    Mapping[str, object],
                    cast(Mapping[str, object], r.get("final_program", {})).get(
                        "substitution_metrics", {}
                    ),
                ).get("substitution_exact_group", 0)  # noqa: E501
            )
        )
        if r.get("final_program")
        else 0
        for r in records
    )
    substitutions_exact_role = sum(
        int(
            _number(
                cast(
                    Mapping[str, object],
                    cast(Mapping[str, object], r.get("final_program", {})).get(
                        "substitution_metrics", {}
                    ),
                ).get("substitution_exact_semantic_role", 0)  # noqa: E501
            )
        )
        if r.get("final_program")
        else 0
        for r in records
    )
    no_valid_replacements = sum(
        int(
            _number(
                cast(
                    Mapping[str, object],
                    cast(Mapping[str, object], r.get("final_program", {})).get(
                        "substitution_metrics", {}
                    ),
                ).get("substitution_no_valid_replacement", 0)  # noqa: E501
            )
        )
        if r.get("final_program")
        else 0
        for r in records
    )
    movement_family_fallbacks = sum(
        int(
            _number(
                cast(
                    Mapping[str, object],
                    cast(Mapping[str, object], r.get("final_program", {})).get(
                        "substitution_metrics", {}
                    ),
                ).get("substitution_movement_family_fallback", 0)  # noqa: E501
            )
        )
        if r.get("final_program")
        else 0
        for r in records
    )
    equipment_violations = sum(
        1
        for r in records
        for f in cast(Sequence[Mapping[str, object]], r.get("audit_findings", []))
        if "equipment" in str(f.get("code")).lower()
    )
    safety_violations = sum(
        1
        for r in records
        for f in cast(Sequence[Mapping[str, object]], r.get("audit_findings", []))
        if "safety" in str(f.get("code")).lower()
        or "caution" in str(f.get("code")).lower()
        or "constraint" in str(f.get("code")).lower()
        or "limit" in str(f.get("code")).lower()
    )
    redundancy_violations = sum(
        1
        for r in records
        for f in cast(Sequence[Mapping[str, object]], r.get("audit_findings", []))
        if "redundant" in str(f.get("code")).lower() or "redundancy" in str(f.get("code")).lower()
    )

    breakdowns: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
    for dimension in ("experience_level", "days", "goal", "duration", "equipment", "limitations"):
        grouped: dict[str, Counter[str]] = defaultdict(Counter)
        for item in records:
            grouped[_failure_dimensions(item)[dimension]][str(item["category"])] += 1
        breakdowns[dimension] = {
            key: dict(sorted(counter.items())) for key, counter in sorted(grouped.items())
        }
    validation_success = sum(
        bool(item["final_program"])
        and cast(
            Mapping[str, object], cast(Mapping[str, object], item["final_program"])["validation"]
        )["status"]
        != "INVALID"
        for item in records
    )
    quality_rates = {
        "template_preservation": _quality_rate(
            records, "template_preservation", frozenset({"preserved"})
        ),
        "priority_target_satisfaction": _quality_rate(
            records, "priority_target_satisfaction", frozenset({"satisfied"})
        ),
        "body_analysis_target_satisfaction": _quality_rate(
            records, "body_analysis_target_satisfaction", frozenset({"satisfied"})
        ),
        "volume_fit": _quality_rate(
            records, "volume_fit", frozenset({"fit"}), source="quality_audit"
        ),
        "muscle_level_volume_fit": _aggregate_muscle_level_volume_fit(records),
        "duration_fit": _quality_rate(
            records, "duration_fit", frozenset({"fit"}), source="quality_audit"
        ),
        "recovery_fit": _quality_rate(
            records, "recovery_fit", frozenset({"fit"}), source="quality_audit"
        ),
    }
    return {
        "profiles_tested": total,
        "negative_profiles": negative_count,
        "category_counts": dict(sorted(categories.items())),
        "category_percentages": {
            key: round(value / total * 100, 2) for key, value in sorted(categories.items())
        },
        "quality_pass_rate": round(quality_passes / feasible, 4) if feasible else 0.0,
        "feasible_profiles": feasible,
        "engine_bugs": categories["ENGINE_BUG"],
        "safety_violations": sum(
            findings[code]
            for code in ("LIMITATION_VIOLATION_PATTERN", "LIMITATION_VIOLATION_CAUTION")
        ),
        "equipment_violations": findings["UNAVAILABLE_EQUIPMENT"],
        "redundancy_findings": findings["REDUNDANT_NEAR_IDENTICAL_MOVEMENTS"],
        "fallback": {
            "template_path_attempts": template_attempts,
            "template_path_successes": template_successes,
            "fallback_activations": fallback_activations,
            "fallback_successes": fallback_successes,
            "unsatisfied_generations": unsatisfied,
            "template_success_rate": round(template_successes / template_attempts, 4)
            if template_attempts
            else 0.0,
            "fallback_activation_rate": round(fallback_activations / total, 4) if total else 0.0,
            "fallback_success_rate": round(fallback_successes / fallback_activations, 4)
            if fallback_activations
            else 0.0,
            "overall_generation_success_rate": round((total - unsatisfied) / total, 4)
            if total
            else 0.0,
            "reason_codes": dict(sorted(reason_codes.items())),
            "rejection_categories": dict(sorted(rejection_categories.items())),
            "unsat_classifications": dict(sorted(unsat_classifications.items())),
            "template_attempt_reason_codes": dict(sorted(attempt_reason_codes.items())),
            "template_attempt_rejection_categories": dict(
                sorted(attempt_rejection_categories.items())
            ),
            **template_attempts_metrics,
        },
        "quality": {
            "validation_success_rate": round(validation_success / total, 4) if total else 0.0,
            "metrics": quality_rates,
            "top_findings": findings.most_common(),
            "determinism_identical": determinism,
            "determinism_runs": determinism_runs,
            "substitutions_total": substitutions_total,
            "substitutions_requests": substitutions_requests,
            "substitutions_exact_group": substitutions_exact_group,
            "substitutions_exact_role": substitutions_exact_role,
            "no_valid_replacements": no_valid_replacements,
            "movement_family_fallbacks": movement_family_fallbacks,
            "equipment_violations_custom": equipment_violations,
            "safety_violations_custom": safety_violations,
            "redundancy_violations_custom": redundancy_violations,
            "quality_code_audit": quality_code_audit,
            "semantic_substitution": semantic_substitution,
        },
        "failure_breakdowns": {key: dict(value) for key, value in breakdowns.items()},
    }


def _service_for_benchmark(db: Session) -> WorkoutGenerationService:
    return WorkoutGenerationService(
        db,
        settings=WorkoutGenerationSettings(
            provider_name="phase11-benchmark",
            model_id="deterministic",
            prompt_version="phase11",
            generation_policy_version="phase11",
            catalog_programming_version="database",
            max_repair_attempts=0,
            cooldown_seconds=0,
            max_candidates=1000,
            max_request_bytes=1_000_000,
            warmup_minutes=RULESET.general_warmup_minutes,
        ),
    )


def _object_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _object_sequence(value: object) -> Sequence[object]:
    return value if isinstance(value, (tuple, list)) else ()


def verify_closeout(payload: Mapping[str, object]) -> tuple[str, ...]:
    """Return every Prompt 5 acceptance blocker; an empty tuple is READY."""
    blockers: list[str] = []
    catalog = _object_mapping(payload.get("catalog"))
    aggregate = _object_mapping(payload.get("aggregate"))
    fallback = _object_mapping(aggregate.get("fallback"))
    quality = _object_mapping(aggregate.get("quality"))
    determinism = _object_mapping(payload.get("determinism"))
    records = tuple(_object_mapping(item) for item in _object_sequence(payload.get("profiles")))
    total = int(_number(aggregate.get("profiles_tested")))

    if total != EXPECTED_PROFILE_COUNT or len(records) != EXPECTED_PROFILE_COUNT:
        blockers.append(
            "Canonical profile count mismatch: "
            f"aggregate={total} records={len(records)} expected={EXPECTED_PROFILE_COUNT}"
        )
    if not 300 <= total <= 500:
        blockers.append(f"Profile count {total} is outside the required 300-500 range")

    matrix = tuple(
        tuple(_object_sequence(item)) for item in _object_sequence(payload.get("supported_matrix"))
    )
    if matrix != SUPPORTED_MATRIX:
        blockers.append("Supported Experience x Days matrix differs from the canonical 15 cells")

    inputs = tuple(_object_mapping(record.get("input")) for record in records)
    cells = Counter(
        (str(item.get("experience_level")), int(_number(item.get("resistance_days"))))
        for item in inputs
    )
    expected_cells = Counter({cell: PROFILE_VARIANTS_PER_CELL for cell in SUPPORTED_MATRIX})
    if cells != expected_cells:
        blockers.append("Profile population does not cover every supported cell exactly")

    durations = {int(_number(item.get("duration_minutes"))) for item in inputs}
    if durations != set(OFFICIAL_SESSION_DURATIONS):
        blockers.append("Profile population does not cover every official duration")
    goals = {str(item.get("goal")) for item in inputs}
    expected_goals = {
        Goal.STRENGTH.value,
        Goal.HYPERTROPHY.value,
        Goal.BODY_RECOMPOSITION.value,
        Goal.FAT_LOSS.value,
        Goal.GENERAL_FITNESS.value,
    }
    if goals != expected_goals:
        blockers.append("Profile population does not cover every benchmark goal")
    equipment = {str(item.get("equipment_label")) for item in inputs}
    locations = {str(item.get("training_location")) for item in inputs}
    if "gym" not in locations or "home" not in locations or len(equipment) < 4:
        blockers.append("Profile population lacks gym and diverse home equipment coverage")
    training_ages = {int(_number(item.get("training_age_months"))) for item in inputs}
    if len(training_ages) < 8:
        blockers.append("Profile population lacks training-age variation")

    coverage_fields = {
        "ROM": any(_object_sequence(item.get("allowed_range_of_motion")) for item in inputs),
        "impact": any(item.get("impact_limit") is not None for item in inputs),
        "axial-load": any(item.get("axial_load_limit") is not None for item in inputs),
        "overhead": any(item.get("overhead_limit") is not None for item in inputs),
        "balance": any(item.get("balance_requirement") is not None for item in inputs),
    }
    cautions = {
        str(caution)
        for item in inputs
        for caution in _object_sequence(item.get("training_cautions"))
    }
    for caution in ("lower_back", "shoulder", "knee", "wrist"):
        coverage_fields[caution] = caution in cautions
    missing_coverage = sorted(name for name, covered in coverage_fields.items() if not covered)
    if missing_coverage:
        blockers.append(f"Profile limitation coverage missing: {missing_coverage}")
    priorities = {
        str(muscle) for item in inputs for muscle in _object_sequence(item.get("priority_muscles"))
    }
    expected_priorities = {muscle.value for muscle in MAJOR_MUSCLES}
    if not expected_priorities.issubset(priorities):
        blockers.append("Profile population lacks multiple major priority-muscle coverage")

    template_slugs = tuple(
        sorted(str(slug) for slug in _object_sequence(catalog.get("template_slugs")))
    )
    if int(_number(catalog.get("template_count"))) != EXPECTED_TEMPLATE_COUNT:
        blockers.append("Active template count differs from production seed intent")
    if template_slugs != EXPECTED_TEMPLATE_SLUGS:
        blockers.append("Active template slugs differ from production seed intent")
    if catalog.get("template_seed_hash") != EXPECTED_TEMPLATE_SEED_HASH:
        blockers.append("Template seed hash differs from production seed intent")
    for key in ("catalog_hash", "template_hash"):
        value = catalog.get(key)
        if not isinstance(value, str) or len(value) != 64:
            blockers.append(f"Catalog snapshot is missing a valid {key}")

    categories = Counter(str(record.get("category")) for record in records)
    category_names = (
        "PASS",
        "PASS_WITH_CONSTRAINTS",
        "QUALITY_ISSUE",
        "UNSATISFIED",
        "ENGINE_BUG",
    )
    category_counts = _object_mapping(aggregate.get("category_counts"))
    reported_categories = {key: int(_number(category_counts.get(key))) for key in category_names}
    actual_categories = {key: categories[key] for key in category_names}
    if sum(reported_categories.values()) != total or reported_categories != actual_categories:
        blockers.append("Category totals do not reconcile with profile records")
    if reported_categories["ENGINE_BUG"]:
        blockers.append(f"ENGINE_BUG = {reported_categories['ENGINE_BUG']}")

    hard_metrics = {
        "equipment violations": max(
            int(_number(aggregate.get("equipment_violations"))),
            int(_number(quality.get("equipment_violations_custom"))),
        ),
        "safety/constraint hard violations": max(
            int(_number(aggregate.get("safety_violations"))),
            int(_number(quality.get("safety_violations_custom"))),
        ),
        "redundancy violations": max(
            int(_number(aggregate.get("redundancy_findings"))),
            int(_number(quality.get("redundancy_violations_custom"))),
        ),
    }
    blockers.extend(f"{name} = {count}" for name, count in hard_metrics.items() if count)

    determinism_cases = int(_number(determinism.get("cases")))
    determinism_runs = int(_number(quality.get("determinism_runs")))
    determinism_identical = int(_number(quality.get("determinism_identical")))
    if determinism_cases != total or determinism_runs != total:
        blockers.append(
            "Determinism denominator does not equal total profiles: "
            f"cases={determinism_cases} runs={determinism_runs} total={total}"
        )
    if (
        float(_number(determinism.get("rate"))) != 1.0
        or determinism_identical != total
        or _object_sequence(determinism.get("mismatches"))
    ):
        blockers.append("Determinism is below 100%")

    negative_cases = tuple(
        _object_mapping(item) for item in _object_sequence(payload.get("negative_cases"))
    )
    if len(negative_cases) != len(NEGATIVE_PROFILES) or not all(
        item.get("rejected_correctly") is True for item in negative_cases
    ):
        blockers.append("Unsupported negative profiles were not all rejected correctly")

    unsat_records = tuple(record for record in records if record.get("category") == "UNSATISFIED")
    unsat_causes: Counter[str] = Counter()
    for record in unsat_records:
        unsat_classification = _object_mapping(record.get("unsat_classification"))
        cause = str(unsat_classification.get("cause", ""))
        evidence = _object_sequence(unsat_classification.get("evidence"))
        if cause not in UNSAT_CAUSES or not evidence:
            blockers.append("Every UNSAT record must have one final cause and evidence")
            continue
        unsat_causes[cause] += 1
        if cause not in LEGITIMATE_UNSAT_CAUSES:
            blockers.append(f"UNSAT profile has non-legitimate final cause: {cause}")
    reported_unsat = {
        str(key): int(_number(value))
        for key, value in _object_mapping(fallback.get("unsat_classifications")).items()
    }
    if (
        sum(reported_unsat.values()) != len(unsat_records)
        or reported_unsat != dict(sorted(unsat_causes.items()))
        or int(_number(fallback.get("unsatisfied_generations"))) != len(unsat_records)
    ):
        blockers.append("UNSAT classifications do not reconcile exactly with UNSAT records")

    finding_counts: Counter[str] = Counter()
    finding_classifications: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        for raw_finding in _object_sequence(record.get("audit_findings")):
            finding = _object_mapping(raw_finding)
            code = str(finding.get("code", ""))
            finding_classification = str(finding.get("classification", ""))
            if not code or finding_classification not in {"A", "B", "C"}:
                blockers.append("Every quality finding must have an A/B/C classification")
                continue
            finding_counts[code] += 1
            finding_classifications[code][finding_classification] += 1
            if finding_classification == "A":
                blockers.append(f"Proven engine defect remains in quality findings: {code}")
            if finding_classification == "C":
                blockers.append(f"Benchmark false positive remains in final findings: {code}")
    reported_quality_audit = _object_mapping(quality.get("quality_code_audit"))
    expected_quality_audit = {
        code: {
            "count": count,
            "classifications": dict(sorted(finding_classifications[code].items())),
        }
        for code, count in sorted(finding_counts.items())
    }
    normalized_quality_audit = {
        str(code): {
            "count": int(_number(_object_mapping(values).get("count"))),
            "classifications": {
                str(key): int(_number(value))
                for key, value in _object_mapping(
                    _object_mapping(values).get("classifications")
                ).items()
            },
        }
        for code, values in reported_quality_audit.items()
    }
    if normalized_quality_audit != expected_quality_audit:
        blockers.append("Final quality-code audit does not reconcile with profile findings")

    semantic = _object_mapping(quality.get("semantic_substitution"))
    unexplained = int(_number(semantic.get("unexplained_final_semantic_failures")))
    record_unexplained = sum(
        int(
            _number(
                _object_mapping(record.get("semantic_substitution")).get(
                    "unexplained_final_semantic_failures"
                )
            )
        )
        for record in records
    )
    if unexplained != record_unexplained:
        blockers.append("Semantic substitution totals do not reconcile with profile records")
    if unexplained:
        blockers.append(f"Unexplained final semantic substitution failures = {unexplained}")

    return tuple(dict.fromkeys(blockers))


def _summary_markdown(payload: Mapping[str, object]) -> str:
    aggregate = cast(Mapping[str, object], payload["aggregate"])
    fallback = cast(Mapping[str, object], aggregate["fallback"])
    categories = cast(Mapping[str, int], aggregate["category_counts"])
    lines = [
        "# Phase 11 deterministic benchmark",
        "",
        f"Profiles tested: {aggregate['profiles_tested']}",
        f"Supported cells: {len(SUPPORTED_MATRIX)}/15",
        "",
        "## Outcomes",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in sorted(categories.items()))
    lines.extend(
        [
            "",
            "## Fallback",
            "",
            "- Template attempts/successes: "
            f"{fallback['template_path_attempts']}/{fallback['template_path_successes']}",
            f"- Total ranked template attempts: {fallback['total_template_attempts']}",
            f"- Attempt-depth distribution: {fallback['attempt_depth_distribution']}",
            "- Successful attempt-depth distribution: "
            f"{fallback['successful_attempt_depth_distribution']}",
            f"- Recovered with alternative: {fallback['recovered_with_alternative']}",
            f"- Alternatives exhausted: {fallback['alternatives_exhausted']}",
            "- Activations/successes: "
            f"{fallback['fallback_activations']}/{fallback['fallback_successes']}",
            f"- Overall generation success rate: {fallback['overall_generation_success_rate']}",
            f"- Reasons: {fallback['reason_codes']}",
            "- All attempt rejection categories: "
            f"{fallback['template_attempt_rejection_categories']}",
            "",
            "## Quality metrics",
            "",
        ]
    )
    quality = cast(Mapping[str, object], aggregate["quality"])
    lines.append(f"- Validation success rate: {quality['validation_success_rate']}")
    for name, metric in cast(Mapping[str, Mapping[str, object]], quality["metrics"]).items():
        if name == "muscle_level_volume_fit":
            lines.append(
                "- muscle_level_volume_fit: "
                f"{metric['within_target_or_flexible_range']}/{metric['tracked_muscles']} "
                f"({metric['percentage']}%)"
            )
            lines.append(
                "- muscle_level_volume_constrained_or_outside: "
                f"{metric['constrained_or_outside_target']}"
            )
        else:
            lines.append(
                f"- {name}: {metric['satisfied']}/{metric['applicable']} ({metric['rate']})"
            )
    lines.extend(
        [
            "",
            "## Custom Audits",
            "",
            f"- Determinism (identical across repeats): "
            f"{quality.get('determinism_identical', 0)}/{quality.get('determinism_runs', 0)}",
            f"- Substitution Requests: {quality.get('substitutions_requests', 0)}",
            f"- Substitution Successes: {quality.get('substitutions_total', 0)}",
            f"- Substitution Exact Group: {quality.get('substitutions_exact_group', 0)}",
            f"- Substitution Exact Role: {quality.get('substitutions_exact_role', 0)}",
            f"- Substitution Movement Family Fallback: {quality.get('movement_family_fallbacks', 0)}",  # noqa: E501
            f"- Substitution No Valid Replacement: {quality.get('no_valid_replacements', 0)}",
            f"- Equipment Violations: {quality.get('equipment_violations_custom', 0)}",
            f"- Safety/Constraint Violations: {quality.get('safety_violations_custom', 0)}",
            f"- Redundancy Violations: {quality.get('redundancy_violations_custom', 0)}",
            "",
            "## Top audit findings",
            "",
        ]
    )
    for finding, count in cast(Sequence[Sequence[object]], quality["top_findings"])[:10]:
        lines.append(f"- {finding}: {count}")
    lines.extend(["", "## Failure breakdowns", ""])
    breakdowns = cast(
        Mapping[str, Mapping[str, Mapping[str, int]]], aggregate["failure_breakdowns"]
    )
    for dimension, values in breakdowns.items():
        lines.append(f"- {dimension}: {dict(values)}")
    lines.extend(["", "## Catalog snapshot", "", f"{payload['catalog']}", ""])
    return "\n".join(lines)


def run_benchmark(
    db: Session,
    output_dir: Path,
    *,
    determinism_repeats: int = 3,
) -> dict[str, object]:
    service = _service_for_benchmark(db)
    references = _prepare_template_library(db)
    catalog_by_sex = {sex: service._load_catalog(sex) for sex in (None, Sex.MALE, Sex.FEMALE)}
    catalog = catalog_by_sex[None]
    if len(catalog) < 100 or len(references) < 15:
        raise RuntimeError(
            "real catalog snapshot is too small: "
            f"exercises={len(catalog)} templates={len(references)}"
        )
    catalog_hash = service._catalog_hash(catalog)
    reference_hash = service._template_reference_hash(references)
    records: list[dict[str, object]] = []
    profiles = benchmark_profiles()
    for profile in profiles:
        request = profile_to_request(profile)
        case_catalog = catalog_by_sex[profile.sex]
        request = apply_catalog_constraints(request, profile, case_catalog)
        result = generate_program(request, case_catalog, RULESET, reference_templates=references)
        repeated = [
            generate_program(request, case_catalog, RULESET, reference_templates=references)
            for _ in range(max(1, determinism_repeats))
        ]
        fingerprints = tuple(canonical_fingerprint(item) for item in [result] + repeated)
        records.append(_case_record(profile, request, result, case_catalog, fingerprints))

    negative_cases: list[dict[str, object]] = []
    for profile in NEGATIVE_PROFILES:
        request = profile_to_request(profile, enforce_matrix=False)
        case_catalog = catalog_by_sex[profile.sex]
        result = generate_program(request, case_catalog, RULESET, reference_templates=references)
        negative_cases.append(
            {
                "input": _jsonable(asdict(profile)),
                "request_days": request.available_training_days,
                "error_code": result.error_code.value if result.error_code else None,
                "errors": result.errors,
                "rejected_correctly": result.error_code is not None
                and result.error_code.value == "UNSUPPORTED_RESISTANCE_TRAINING_DAYS",
            }
        )

    payload: dict[str, object] = {
        "phase": 11,
        "ruleset": RULESET.version,
        "engine_version": RULESET.engine_version,
        "catalog": {
            "exercise_count": len(catalog),
            "template_count": len(references),
            "template_slugs": tuple(sorted(item.slug for item in references)),
            "catalog_hash": catalog_hash,
            "template_hash": reference_hash,
            "template_seed_hash": EXPECTED_TEMPLATE_SEED_HASH,
        },
        "supported_matrix": SUPPORTED_MATRIX,
        "aggregate": _aggregate(records, len(NEGATIVE_PROFILES)),
        "determinism": {
            "cases": len(records),
            "rate": round(
                sum(
                    bool(cast(Mapping[str, object], record["determinism"])["identical"])
                    for record in records
                )
                / len(records),
                4,
            )
            if records
            else 0.0,
            "mismatches": [
                record["input"]
                for record in records
                if not cast(Mapping[str, object], record["determinism"])["identical"]
            ],
        },
        "negative_cases": negative_cases,
        "profiles": records,
    }
    blockers = verify_closeout(payload)
    payload["closeout"] = {
        "verdict": "READY FOR PROMPT 6" if not blockers else "NOT READY FOR PROMPT 6",
        "blockers": blockers,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "phase11-benchmark.json").write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True), encoding="utf-8"
    )
    (output_dir / "phase11-summary.md").write_text(_summary_markdown(payload), encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Phase 11 deterministic benchmark")
    parser.add_argument(
        "--database-url",
        default=os.environ.get(
            "BENCHMARK_DATABASE_URL",
            "postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho",
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("var/benchmarks/phase11"))
    parser.add_argument("--determinism-repeats", type=int, default=3)
    args = parser.parse_args(argv)
    engine = create_engine(args.database_url)
    try:
        with Session(engine) as db:
            payload = run_benchmark(
                db,
                args.output_dir,
                determinism_repeats=max(1, args.determinism_repeats),
            )
        aggregate = cast(Mapping[str, object], payload["aggregate"])
        print(json.dumps(aggregate, indent=2, sort_keys=True))
        closeout = cast(Mapping[str, object], payload["closeout"])
        print(closeout["verdict"])
        for blocker in cast(Sequence[str], closeout["blockers"]):
            print(f"- {blocker}")
    finally:
        engine.dispose()
    return 0 if not cast(Mapping[str, object], payload["closeout"])["blockers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
