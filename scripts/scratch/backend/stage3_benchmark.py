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
from app.workouts.program_engine.duration_policy import (
    calculate_main_training_minutes,
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
)
from app.workouts.program_engine.supplemental_policy import exercise_count_breakdown
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

from random import Random

def benchmark_profiles() -> tuple[BenchmarkProfile, ...]:
    goals = (
        Goal.STRENGTH,
        Goal.HYPERTROPHY,
        Goal.BODY_RECOMPOSITION,
        Goal.FAT_LOSS,
        Goal.GENERAL_FITNESS,
    )
    durations = (30, 45, 60, 75, 90, 120)
    locations = (TrainingLocation.GYM, TrainingLocation.HOME)
    home_setups = tuple(HomeTrainingSetup)
    cautions = tuple(TrainingCaution)
    muscles = tuple(MAJOR_MUSCLES)
    impact_limits = tuple(ImpactLimit)
    load_limits = tuple(LoadLimit)
    balance_abilities = tuple(BalanceAbility)
    
    profiles = []
    
    count_per_cell = 25
    
    for experience, days in SUPPORTED_MATRIX:
        for variant in range(count_per_cell):
            rng = Random(f"fitsho:stage3:{experience}:{days}:{variant}")
            
            goal = rng.choice(goals)
            if experience == ExperienceLevel.FIRST_MONTH.value:
                goal = Goal.GENERAL_FITNESS
                
            location = rng.choice(locations)
            home_setup = None
            equipment_label = "full_gym"
            if location == TrainingLocation.HOME:
                home_setup = rng.choice(home_setups)
                equipment_label = f"home_{home_setup.value}"
                
            training_cautions = []
            impact_limit = None
            axial_load = None
            overhead = None
            balance = None
            
            if rng.random() < 0.2:
                training_cautions = [rng.choice(cautions)]
            
            if rng.random() < 0.1:
                impact_limit = rng.choice(impact_limits)
            if rng.random() < 0.1:
                axial_load = rng.choice(load_limits)
            if rng.random() < 0.1:
                overhead = rng.choice(load_limits)
            if rng.random() < 0.1:
                balance = rng.choice(balance_abilities)
                
            priority_muscles = []
            if rng.random() < 0.3:
                priority_muscles = [rng.choice(muscles)]
                
            profiles.append(BenchmarkProfile(
                profile_id=str(uuid5(NAMESPACE_URL, f"https://fitsho.test/stage3/{experience}/{days}/{variant}")) if 'uuid5' in globals() else str(variant),
                variant=variant,
                experience_level=ExperienceLevel(experience),
                resistance_days=days,
                goal=goal,
                priority_muscles=tuple(priority_muscles),
                body_analysis_priorities=(),
                sex=rng.choice((Sex.MALE, Sex.FEMALE)),
                duration_minutes=rng.choice(durations),
                equipment_label=equipment_label,
                training_location=location,
                home_setup=home_setup,
                available_equipment_override=None,
                training_cautions=tuple(training_cautions),
                impact_limit=impact_limit,
                axial_load_limit=axial_load,
                overhead_limit=overhead,
                balance_requirement=balance,
            ))
            
    return tuple(profiles)

NEGATIVE_PROFILES: tuple[BenchmarkProfile, ...] = ()


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
        training_age_months={
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

    def issue(code: str, severity: str, message: str) -> None:
        issues.append({"code": code, "severity": severity, "message": message})

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
    missing_major_coverage = _missing_major_muscle_coverage(
        ranges if isinstance(ranges, Mapping) else {}
    )
    if missing_major_coverage:
        issue(
            "MISSING_MAJOR_MUSCLE_COVERAGE",
            "quality",
            ",".join(missing_major_coverage),
        )
    if not recovery_spacing_is_valid(program.weekly_schedule, RULESET):
        issue("RECOVERY_SPACING_INVALID", "quality", "direct/exposure overlap")

    policy = get_session_duration_policy(request.session_duration_minutes)
    for day in program.weekly_schedule:
        if not policy.contains(calculate_main_training_minutes(day)):
            issue("DURATION_OUTSIDE_POLICY", "quality", str(day.day_index))

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
                issue("VOLUME_OUTSIDE_ACCEPTABLE_RANGE", "quality", str(muscle))

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
        policy.contains(calculate_main_training_minutes(day))
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
                    "exercise_count": counts.main_count,
                    "main_exercise_count": counts.main_count,
                    "supplemental_exercise_count": counts.supplemental_count,
                    "total_exercise_count": counts.total_count,
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
                for counts in (exercise_count_breakdown(day.exercises),)
            ],
            "direct_volume": program.aggregate_metrics.get("weekly_direct_sets_by_muscle", {}),
            "effective_volume": program.aggregate_metrics.get(
                "weekly_effective_sets_by_muscle", {}
            ),
            "priority_metrics": program.aggregate_metrics.get("priority_metrics", {}),
            "volume_ranges": program.aggregate_metrics.get("volume_ranges_by_muscle", {}),
            "substitution_count": quality.get("substitution_count", 0),
            "constraint_count": quality.get("constraint_count", 0),
            "recovery_spacing_valid": recovery_spacing_is_valid(program.weekly_schedule, RULESET),
            "validation": {
                "status": program.validation_report.status.value,
                "errors": program.validation_report.errors,
                "warnings": program.validation_report.warnings,
            },
            "trace": program.decision_trace,
        }
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
        "quality_outcome": _category(result, template, issues),
        "construction_path": _construction_path(result, template),
        "category": _category(result, template, issues),
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
    template = [cast(Mapping[str, object], item["template"]) for item in records]
    template_attempts_metrics = _template_attempt_metrics(template)
    total = len(records)
    template_attempts = sum(bool(item["attempted"]) for item in template)
    template_successes = sum(bool(item["succeeded"]) for item in template)
    fallback_activations = sum(bool(item["fallback_activated"]) for item in template)
    fallback_successes = sum(bool(item["fallback_succeeded"]) for item in template)
    unsatisfied = sum(str(item["category"]) == "UNSATISFIED" for item in records)
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
    feasible = total - unsatisfied
    quality_passes = categories["PASS"] + categories["PASS_WITH_CONSTRAINTS"]
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
    lines.extend(["", "## Top audit findings", ""])
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
    references = load_template_references(db)
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
        fingerprints = tuple(canonical_fingerprint(item) for item in repeated)
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
            "catalog_hash": catalog_hash,
            "template_hash": reference_hash,
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
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
