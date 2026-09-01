"""Independent Phase 11.9 holdout benchmark.

This module deliberately reuses the production-equivalent Phase 11 mapping and
the current deterministic engine, but owns a new, frozen 150-profile population.
It does not change engine behavior or Phase 11 fixtures.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import tests.workouts.program_engine.phase11_benchmark as phase11
from app.exercises.enums import Equipment, ExerciseCautionTag, MovementPattern, MuscleGroup
from app.profile.enums import (
    ExperienceLevel,
    HomeTrainingSetup,
    Sex,
    TrainingCaution,
    TrainingLocation,
)
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
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET

PHASE = "11.9"
HOLDOUT_NAMESPACE = "https://fitsho.test/phase11-9-holdout"
DETERMINISM_SUBSET_SIZE = 30


def _profile_id(level: ExperienceLevel, days: int, variant: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"{HOLDOUT_NAMESPACE}/{level.value}/{days}/{variant}"))


def _persona(
    level: ExperienceLevel,
    days: int,
    variant: int,
) -> phase11.BenchmarkProfile:
    """Return one coach-like holdout persona, with level/day-specific identity."""

    common = {
        "profile_id": _profile_id(level, days, variant),
        "variant": variant,
        "experience_level": level,
        "resistance_days": days,
    }
    personas: tuple[dict[str, object], ...] = (
        {
            "goal": Goal.STRENGTH,
            "priority_muscles": (),
            "body_analysis_priorities": (),
            "sex": Sex.MALE,
            "duration_minutes": 120 if level is ExperienceLevel.ADVANCED and days == 6 else 60,
            "equipment_label": "full_gym",
            "training_location": TrainingLocation.GYM,
            "home_setup": None,
        },
        {
            "goal": Goal.HYPERTROPHY,
            "priority_muscles": (MuscleGroup.CHEST,),
            "body_analysis_priorities": (),
            "sex": Sex.FEMALE,
            "duration_minutes": 45,
            "equipment_label": "limited_gym",
            "training_location": TrainingLocation.GYM,
            "home_setup": None,
            "available_equipment_override": frozenset(
                {Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.BENCH}
            ),
            "blocked_movement_patterns": (MovementPattern.VERTICAL_PUSH,),
            "physical_job_demand": PhysicalJobDemand.MODERATE,
            "blocked_exercise_tokens": ("barbell", "cable", "machine"),
        },
        {
            "goal": Goal.BODY_RECOMPOSITION,
            "priority_muscles": (MuscleGroup.GLUTES,),
            "body_analysis_priorities": ((MuscleGroup.HAMSTRINGS, "mild_lag"),),
            "sex": Sex.FEMALE,
            "duration_minutes": 75,
            "equipment_label": "dumbbells_only",
            "training_location": TrainingLocation.HOME,
            "home_setup": HomeTrainingSetup.DUMBBELLS_AVAILABLE,
            "available_equipment_override": frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL}),
            "blocked_caution_tags": (ExerciseCautionTag.OVERHEAD_POSITION,),
            "overhead_limit": LoadLimit.LOW,
            "stress_level": RecoveryRating.POOR,
        },
        {
            "goal": Goal.FAT_LOSS,
            "priority_muscles": (),
            "body_analysis_priorities": (),
            "sex": None,
            "duration_minutes": 30,
            "equipment_label": "bands_bodyweight",
            "training_location": TrainingLocation.HOME,
            "home_setup": HomeTrainingSetup.BODYWEIGHT_ONLY,
            "available_equipment_override": frozenset(
                {Equipment.BODYWEIGHT, Equipment.RESISTANCE_BAND}
            ),
            "training_cautions": (TrainingCaution.KNEE,),
            "blocked_caution_tags": (ExerciseCautionTag.DEEP_KNEE_FLEXION,),
            "impact_limit": ImpactLimit.LOW,
            "balance_requirement": BalanceAbility.LIMITED,
            "sleep_quality": RecoveryRating.POOR,
            "stress_level": RecoveryRating.POOR,
            "recent_recovery_problems": True,
            "physical_limitation_note": "Knee discomfort; avoid deep knee flexion and impact.",
        },
        {
            "goal": Goal.GENERAL_FITNESS,
            "priority_muscles": (MuscleGroup.GLUTES,),
            "body_analysis_priorities": (
                (MuscleGroup.HAMSTRINGS, "clear_lag"),
                (MuscleGroup.BACK, "mild_lag"),
            ),
            "sex": Sex.MALE,
            "duration_minutes": 90,
            "equipment_label": "full_gym_recovery_limited",
            "training_location": TrainingLocation.GYM,
            "home_setup": None,
            "training_cautions": (TrainingCaution.LOWER_BACK,),
            "axial_load_limit": LoadLimit.LOW,
            "physical_job_demand": PhysicalJobDemand.HIGH,
            "recent_recovery_problems": True,
            "previous_volume_sets": 8,
            "blocked_exercise_tokens": ("barbell deadlift", "good morning"),
            "physical_limitation_note": "High physical workload; limit axial loading.",
        },
        {
            "goal": Goal.HYPERTROPHY,
            "priority_muscles": (MuscleGroup.CHEST,),
            "body_analysis_priorities": (),
            "sex": Sex.FEMALE,
            "duration_minutes": 45,
            "equipment_label": "dumbbells_bench",
            "training_location": TrainingLocation.HOME,
            "home_setup": HomeTrainingSetup.DUMBBELLS_AVAILABLE,
            "available_equipment_override": frozenset(
                {Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.BENCH}
            ),
            "blocked_movement_patterns": (MovementPattern.VERTICAL_PULL,),
            "sleep_quality": RecoveryRating.GOOD,
        },
        {
            "goal": Goal.BODY_RECOMPOSITION,
            "priority_muscles": (MuscleGroup.SHOULDERS,),
            "body_analysis_priorities": (
                (MuscleGroup.CHEST, "clear_lag"),
                (MuscleGroup.TRICEPS, "mild_lag"),
            ),
            "sex": Sex.FEMALE,
            "duration_minutes": 60,
            "equipment_label": "dumbbells_only",
            "training_location": TrainingLocation.HOME,
            "home_setup": HomeTrainingSetup.DUMBBELLS_AVAILABLE,
            "available_equipment_override": frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL}),
            "blocked_caution_tags": (
                ExerciseCautionTag.OVERHEAD_POSITION,
                ExerciseCautionTag.SHOULDER_INTERNAL_ROTATION,
            ),
            "overhead_limit": LoadLimit.LOW,
            "sleep_quality": RecoveryRating.POOR,
        },
        {
            "goal": Goal.GENERAL_FITNESS,
            "priority_muscles": (),
            "body_analysis_priorities": ((MuscleGroup.HAMSTRINGS, "mild_lag"),),
            "sex": Sex.MALE,
            "duration_minutes": 45,
            "equipment_label": "bands_bodyweight",
            "training_location": TrainingLocation.HOME,
            "home_setup": HomeTrainingSetup.BODYWEIGHT_ONLY,
            "available_equipment_override": frozenset(
                {Equipment.BODYWEIGHT, Equipment.RESISTANCE_BAND}
            ),
            "training_cautions": (TrainingCaution.LOWER_BACK,),
            "blocked_movement_patterns": (MovementPattern.HIP_HINGE,),
            "axial_load_limit": LoadLimit.LOW,
            "physical_job_demand": PhysicalJobDemand.MODERATE,
            "stress_level": RecoveryRating.POOR,
            "previous_volume_sets": 10,
            "physical_limitation_note": "Occasional low-back irritation; avoid loaded hinging.",
        },
        {
            "goal": Goal.STRENGTH,
            "priority_muscles": (MuscleGroup.QUADRICEPS,),
            "body_analysis_priorities": (
                (MuscleGroup.HAMSTRINGS, "clear_lag"),
                (MuscleGroup.BACK, "clear_lag"),
            ),
            "sex": Sex.MALE,
            "duration_minutes": 90,
            "equipment_label": "full_gym",
            "training_location": TrainingLocation.GYM,
            "home_setup": None,
            "training_cautions": (TrainingCaution.KNEE,),
            "blocked_caution_tags": (ExerciseCautionTag.DEEP_KNEE_FLEXION,),
            "impact_limit": ImpactLimit.MODERATE,
            "balance_requirement": BalanceAbility.NORMAL,
        },
        {
            "goal": Goal.FAT_LOSS,
            "priority_muscles": (MuscleGroup.BACK,),
            "body_analysis_priorities": ((MuscleGroup.SHOULDERS, "mild_lag"),),
            "sex": None,
            "duration_minutes": 60,
            "equipment_label": "home_limited",
            "training_location": TrainingLocation.HOME,
            "home_setup": HomeTrainingSetup.BODYWEIGHT_ONLY,
            "available_equipment_override": frozenset({Equipment.BODYWEIGHT}),
            "impact_limit": ImpactLimit.LOW,
            "balance_requirement": BalanceAbility.LIMITED,
            "physical_job_demand": PhysicalJobDemand.HIGH,
            "blocked_exercise_tokens": ("push-up",),
            "physical_limitation_note": "Low-impact home sessions preferred.",
        },
    )
    data = {**common, **personas[variant]}
    return cast(phase11.BenchmarkProfile, cast(Any, phase11.BenchmarkProfile)(**data))


def holdout_profiles() -> tuple[phase11.BenchmarkProfile, ...]:
    return tuple(
        _persona(ExperienceLevel(level), days, variant)
        for level, days in phase11.SUPPORTED_MATRIX
        for variant in range(10)
    )


def negative_profiles() -> tuple[phase11.BenchmarkProfile, ...]:
    return (
        replace(_persona(ExperienceLevel.FIRST_MONTH, 2, 0), resistance_days=5),
        replace(_persona(ExperienceLevel.BEGINNER, 2, 1), resistance_days=5),
        replace(_persona(ExperienceLevel.INTERMEDIATE, 2, 2), resistance_days=7),
        replace(_persona(ExperienceLevel.ADVANCED, 3, 3), resistance_days=2),
    )


def input_fingerprint(profile: phase11.BenchmarkProfile) -> str:
    payload = json.dumps(phase11._jsonable(asdict(profile)), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _assert_new_population(profiles: Sequence[phase11.BenchmarkProfile]) -> None:
    fingerprints = {input_fingerprint(profile) for profile in profiles}
    phase11_fingerprints = {input_fingerprint(profile) for profile in phase11.benchmark_profiles()}
    if len(profiles) != 150 or len(fingerprints) != 150:
        raise AssertionError("Phase 11.9 must contain 150 unique profiles")
    overlap = fingerprints.intersection(phase11_fingerprints)
    if overlap:
        raise AssertionError(f"Phase 11.9 reuses Phase 11 input fingerprints: {sorted(overlap)}")
    counts = Counter(
        (profile.experience_level.value, profile.resistance_days) for profile in profiles
    )
    if counts != Counter({cell: 10 for cell in phase11.SUPPORTED_MATRIX}):
        raise AssertionError(f"invalid holdout cell coverage: {counts}")


def _template_family(reference: Any) -> str:
    tags = {str(tag) for tag in getattr(reference, "focus_tags", ())}
    if "push_pull_legs" in tags:
        return "PUSH_PULL_LEGS"
    if "upper_lower" in tags:
        return "UPPER_LOWER"
    if "full_body" in tags:
        return "FULL_BODY"
    if "body_part_rotation" in tags or "classic" in tags:
        return "BODY_PART_ROTATION"
    return "OTHER"


def _template_coverage(
    references: Sequence[Any], records: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    selected: Counter[str] = Counter()
    successful: Counter[str] = Counter()
    considered: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    rejected_by_template: dict[str, Counter[str]] = defaultdict(Counter)
    selected_by_cell: Counter[str] = Counter()
    selected_by_focus_tag: Counter[str] = Counter()
    family_by_slug = {str(ref.slug): _template_family(ref) for ref in references}
    tags_by_slug = {
        str(ref.slug): tuple(sorted(str(tag) for tag in getattr(ref, "focus_tags", ())))
        for ref in references
    }
    for record in records:
        input_data = cast(Mapping[str, object], record["input"])
        template = cast(Mapping[str, object], record["template"])
        selected_slug = template.get("selected_template")
        successful_slug = template.get("successful_template")
        if isinstance(selected_slug, str):
            selected[selected_slug] += 1
            selected_by_cell[
                f"{input_data['experience_level']}:{input_data['resistance_days']}"
            ] += 1
            selected_by_focus_tag.update(tags_by_slug.get(selected_slug, ()))
        if isinstance(successful_slug, str):
            successful[successful_slug] += 1
        for candidate in cast(Sequence[Mapping[str, object]], template.get("score_breakdown", ())):
            slug = candidate.get("slug")
            if isinstance(slug, str):
                considered[slug] += 1
        for category in cast(Sequence[str], template.get("rejection_categories", ())):
            rejected[category] += 1
            if isinstance(selected_slug, str) and not template.get("succeeded"):
                rejected_by_template[selected_slug][category] += 1
    never_selected = sorted(set(family_by_slug) - set(selected))
    suspicious: dict[str, str] = {}
    for slug in never_selected:
        if considered[slug] == 0:
            suspicious[slug] = "not_covered_by_holdout_population"
        elif rejected.total() and considered[slug] >= 3:
            suspicious[slug] = "frequently_considered_but_never_selected"
        else:
            suspicious[slug] = "rare_or_dominated"
    return {
        "active_template_count": len(references),
        "selected_at_least_once": sorted(selected),
        "successful_at_least_once": sorted(successful),
        "never_selected": never_selected,
        "never_successful": sorted(set(family_by_slug) - set(successful)),
        "selection_count_per_template": dict(sorted(selected.items())),
        "success_count_per_template": dict(sorted(successful.items())),
        "considered_count_per_template": dict(sorted(considered.items())),
        "rejection_by_template": {
            slug: dict(sorted(categories.items()))
            for slug, categories in sorted(rejected_by_template.items())
        },
        "family_by_template": dict(sorted(family_by_slug.items())),
        "selection_by_cell": dict(sorted(selected_by_cell.items())),
        "selection_by_focus_tag": dict(sorted(selected_by_focus_tag.items())),
        "selection_by_family": dict(
            sorted(
                Counter(
                    family_by_slug[slug] for slug in selected for _ in range(selected[slug])
                ).items()
            )
        ),
        "rejection_categories": dict(sorted(rejected.items())),
        "suspicious_unused": suspicious,
    }


def _aggregate(
    records: Sequence[Mapping[str, object]],
    negative_records: Sequence[Mapping[str, object]],
    references: Sequence[Any],
) -> dict[str, object]:
    aggregate = phase11._aggregate(records, len(negative_records))
    dimensions = dict(cast(Mapping[str, object], aggregate["failure_breakdowns"]))
    grouped: dict[str, dict[str, Counter[str]]] = {}
    for dimension in ("experience_level", "days", "goal", "duration", "equipment"):
        grouped[dimension] = defaultdict(Counter)
        for record in records:
            grouped[dimension][phase11._failure_dimensions(record)[dimension]][
                str(record["quality_outcome"])
            ] += 1
    grouped["limitations"] = defaultdict(Counter)
    for record in records:
        input_data = cast(Mapping[str, object], record["input"])
        labels: list[str] = []
        labels.extend(cast(Sequence[str], input_data["training_cautions"]))
        labels.extend(cast(Sequence[str], input_data["blocked_movement_patterns"]))
        labels.extend(cast(Sequence[str], input_data["blocked_caution_tags"]))
        if cast(Sequence[str], input_data["blocked_exercise_tokens"]):
            labels.append("blocked_exercise")
        limitation = "+".join(sorted(set(labels))) if labels else "none"
        grouped["limitations"][limitation][str(record["quality_outcome"])] += 1
    recovery_groups: dict[str, Counter[str]] = defaultdict(Counter)
    family_groups: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        input_data = cast(Mapping[str, object], record["input"])
        recovery = "recovery_limited" if input_data["recent_recovery_problems"] else "normal"
        if input_data["sleep_quality"] == RecoveryRating.POOR.value:
            recovery = "poor_sleep_or_stress"
        elif input_data["physical_job_demand"] != PhysicalJobDemand.LOW.value:
            recovery = "physical_job"
        recovery_groups[recovery][str(record["quality_outcome"])] += 1
        template = cast(Mapping[str, object], record["template"])
        slug = template.get("successful_template")
        family = "FALLBACK"
        if isinstance(slug, str):
            ref = next((item for item in references if item.slug == slug), None)
            family = _template_family(ref) if ref is not None else "UNKNOWN"
        family_groups[family][str(record["quality_outcome"])] += 1
    aggregate["failure_breakdowns"] = {
        **dimensions,
        "limitations": {
            key: dict(sorted(value.items()))
            for key, value in sorted(grouped["limitations"].items())
        },
        "recovery_state": {
            key: dict(sorted(value.items())) for key, value in sorted(recovery_groups.items())
        },
        "template_family": {
            key: dict(sorted(value.items())) for key, value in sorted(family_groups.items())
        },
    }
    aggregate["negative_cases"] = list(negative_records)
    aggregate["safety_violation_rate"] = (
        round(float(cast(int, aggregate["safety_violations"])) / len(records), 4)
        if records
        else 0.0
    )
    aggregate["equipment_violation_rate"] = (
        round(float(cast(int, aggregate["equipment_violations"])) / len(records), 4)
        if records
        else 0.0
    )
    aggregate["duration_diagnostics"] = _duration_diagnostics(records)
    return aggregate


def _duration_diagnostics(
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    sessions = 0.0
    budget_fit = 0.0
    overrun = 0.0
    util = 0.0
    legacy_within = 0.0
    legacy_under = 0.0
    legacy_over = 0.0
    legacy_abs_dev = 0.0
    constrained_programs = 0
    repaired_programs = 0
    major_repair_programs = 0
    proven_template_rejections = 0
    grouped: dict[str, dict[str, list[Mapping[str, object]]]] = {
        dimension: defaultdict(list)
        for dimension in ("requested_duration", "primary_goal", "experience_level", "days", "path")
    }
    successful_records: list[Mapping[str, object]] = []
    for record in records:
        final_program = record.get("final_program")
        if not isinstance(final_program, Mapping):
            continue
        successful_records.append(record)
        input_data = cast(Mapping[str, object], record["input"])
        keys = {
            "requested_duration": str(input_data["duration_minutes"]),
            "primary_goal": str(input_data["goal"]),
            "experience_level": str(input_data["experience_level"]),
            "days": str(input_data["resistance_days"]),
            "path": str(record["construction_path"]),
        }
        for dimension, key in keys.items():
            grouped[dimension][key].append(record)
        trace = cast(Sequence[Mapping[str, object]], final_program.get("trace", ()))
        duration_entry = next(
            (entry for entry in trace if entry.get("stage") == "session_duration"),
            {},
        )
        repair_classification = duration_entry.get("repair_classification")
        if repair_classification in {"minor", "major"}:
            repaired_programs += 1
        if repair_classification == "major":
            major_repair_programs += 1
        warnings = cast(
            Sequence[str],
            cast(Mapping[str, object], final_program.get("validation", {})).get("warnings", ()),
        )
        if any("SESSION_DURATION_CONSTRAINED" in warning for warning in warnings):
            constrained_programs += 1
        for entry in trace:
            if entry.get("stage") != "template_selection":
                continue
            for rejection in cast(Sequence[Mapping[str, object]], entry.get("hard_rejections", ())):
                if "REQUIRED_CORE_DURATION_INFEASIBLE" in cast(
                    Sequence[str], rejection.get("reason_codes", ())
                ):
                    proven_template_rejections += 1
    for record in successful_records:
        counts = _duration_counts_for_record(record)
        sessions += counts["sessions"]
        budget_fit += counts["budget_fit"]
        overrun += counts["overrun_minutes"]
        util += counts["utilization_sum"]
        legacy_within += counts["legacy_within"]
        legacy_under += counts["legacy_under"]
        legacy_over += counts["legacy_over"]
        legacy_abs_dev += counts["legacy_absolute_deviation"]

    return {
        "programs": len(successful_records),
        "sessions": sessions,
        "budget_fit_percentage": round(budget_fit / sessions * 100, 2) if sessions else None,
        "average_overrun_minutes": round(overrun / sessions, 2) if sessions else None,
        "average_utilization_percentage": round((util / sessions) * 100, 2) if sessions else None,
        "legacy_within_target_count": legacy_within,
        "legacy_under_target_count": legacy_under,
        "legacy_over_target_count": legacy_over,
        "legacy_duration_fit_percentage": round(legacy_within / sessions * 100, 2)
        if sessions
        else None,
        "legacy_average_absolute_deviation_minutes": round(legacy_abs_dev / sessions, 2)
        if sessions
        else None,
        "late_duration_repair_percentage": round(
            repaired_programs / len(successful_records) * 100, 2
        )
        if successful_records
        else None,
        "major_late_repair_percentage": round(
            major_repair_programs / len(successful_records) * 100, 2
        )
        if successful_records
        else None,
        "proven_duration_template_rejections": proven_template_rejections,
        "breakdowns": {
            dimension: {
                key: _duration_group_metrics(items) for key, items in sorted(values.items())
            }
            for dimension, values in grouped.items()
        },
    }


def _duration_counts_for_record(record: Mapping[str, object]) -> dict[str, float]:
    input_data = cast(Mapping[str, object], record["input"])
    final_program = cast(Mapping[str, object], record["final_program"])
    requested = cast(int, input_data["duration_minutes"])
    policy = get_session_duration_policy(requested)
    counts = {
        "sessions": 0,
        "budget_fit": 0.0,
        "overrun_minutes": 0.0,
        "utilization_sum": 0.0,
        "legacy_within": 0.0,
        "legacy_under": 0.0,
        "legacy_over": 0.0,
        "legacy_absolute_deviation": 0.0,
    }
    for day in cast(Sequence[Mapping[str, object]], final_program.get("days", ())):
        workout = calculate_main_training_minutes(day)
        counts["sessions"] += 1
        if policy.within_preferred_range(workout):
            counts["budget_fit"] += 1
        counts["overrun_minutes"] += max(0, workout - policy.maximum_minutes)
        counts["utilization_sum"] += workout / requested if requested else 0

        counts["legacy_absolute_deviation"] += abs(workout - requested)
        if policy.below_preferred_minimum(workout):
            counts["legacy_under"] += 1
        elif workout > policy.maximum_minutes:
            counts["legacy_over"] += 1
        else:
            counts["legacy_within"] += 1

    return counts


def _duration_group_metrics(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    totals = Counter[str]()
    for record in records:
        totals.update(_duration_counts_for_record(record))
    sessions = totals["sessions"]
    return {
        "programs": len(records),
        "sessions": sessions,
        "budget_fit_percentage": round(totals["budget_fit"] / sessions * 100, 2)
        if sessions
        else None,
        "average_overrun_minutes": round(totals["overrun_minutes"] / sessions, 2)
        if sessions
        else None,
        "average_utilization_percentage": round((totals["utilization_sum"] / sessions) * 100, 2)
        if sessions
        else None,
        "legacy_duration_fit_percentage": round(totals["legacy_within"] / sessions * 100, 2)
        if sessions
        else None,
        "legacy_average_absolute_deviation_minutes": round(
            totals["legacy_absolute_deviation"] / sessions, 2
        )
        if sessions
        else None,
    }


def _csv_rows(records: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    rows = []
    for record in records:
        input_data = cast(Mapping[str, object], record["input"])
        template = cast(Mapping[str, object], record["template"])
        result = cast(Mapping[str, object], record["result"])
        rows.append(
            {
                "profile_id": input_data["profile_id"],
                "input_fingerprint": input_data["input_fingerprint"],
                "experience_level": input_data["experience_level"],
                "days": input_data["resistance_days"],
                "goal": input_data["goal"],
                "duration": input_data["duration_minutes"],
                "equipment": input_data["equipment_label"],
                "limitations": ",".join(
                    sorted(
                        set(cast(Sequence[str], input_data["training_cautions"]))
                        | set(cast(Sequence[str], input_data["blocked_movement_patterns"]))
                        | set(cast(Sequence[str], input_data["blocked_caution_tags"]))
                        | ({"blocked_exercise"} if input_data["blocked_exercise_tokens"] else set())
                    )
                ),
                "quality_outcome": record["quality_outcome"],
                "construction_path": record["construction_path"],
                "selected_template": template.get("selected_template"),
                "successful_template": template.get("successful_template"),
                "template_attempt_depth": template.get("attempt_depth"),
                "template_succeeded": template.get("succeeded"),
                "fallback_reasons": ",".join(cast(Sequence[str], template.get("reason_codes", ()))),
                "success": result["success"],
                "deterministic": cast(Mapping[str, object], record["determinism"])["identical"],
                "audit_findings": ",".join(
                    str(item["code"])
                    for item in cast(Sequence[Mapping[str, object]], record["audit_findings"])
                ),
            }
        )
    return rows


def _write_summary(payload: Mapping[str, object], output_dir: Path) -> None:
    aggregate = cast(Mapping[str, object], payload["aggregate"])
    categories = cast(Mapping[str, int], aggregate["category_counts"])
    fallback = cast(Mapping[str, object], aggregate["fallback"])
    quality = cast(Mapping[str, object], aggregate["quality"])
    duration = cast(Mapping[str, object], aggregate["duration_diagnostics"])
    coverage = cast(Mapping[str, object], payload["template_coverage"])
    catalog = cast(Mapping[str, object], payload["catalog"])
    roots = cast(Mapping[str, object], payload["failure_root_causes"])
    phase11_baseline = {
        "PASS": 0,
        "PASS_WITH_CONSTRAINTS": 26,
        "QUALITY_ISSUE": 39,
        "UNSATISFIED": 10,
        "ENGINE_BUG": 0,
    }
    phase115 = payload["phase11_5_comparison"]
    lines = [
        "# Phase 11.9 Independent Holdout Benchmark",
        "",
        (
            f"Profiles: {aggregate['profiles_tested']} across "
            f"{len(phase11.SUPPORTED_MATRIX)} supported cells"
        ),
        f"Active templates: {coverage['active_template_count']}",
        f"Active exercises: {catalog['exercise_count']}",
        "",
        "## Quality",
        "",
        f"- Categories: {dict(categories)}",
        f"- Quality pass rate: {aggregate['quality_pass_rate']}",
        f"- Generation success: {fallback['overall_generation_success_rate']}",
        f"- Validation success: {quality['validation_success_rate']}",
        (
            f"- Safety/equipment violation rates: "
            f"{aggregate['safety_violation_rate']}/{aggregate['equipment_violation_rate']}"
        ),
        "",
        "## Construction",
        "",
        (
            f"- Template attempts/successes: "
            f"{fallback['template_path_attempts']}/{fallback['template_path_successes']}"
        ),
        f"- Total ranked template attempts: {fallback['total_template_attempts']}",
        f"- Attempt-depth distribution: {fallback['attempt_depth_distribution']}",
        (
            "- Successful attempt-depth distribution: "
            f"{fallback['successful_attempt_depth_distribution']}"
        ),
        f"- Recovered with alternative: {fallback['recovered_with_alternative']}",
        f"- Alternatives exhausted: {fallback['alternatives_exhausted']}",
        (
            f"- Fallback activations/successes: "
            f"{fallback['fallback_activations']}/{fallback['fallback_successes']}"
        ),
        f"- Fallback reasons: {fallback['reason_codes']}",
        (
            "- All attempt rejection categories: "
            f"{fallback['template_attempt_rejection_categories']}"
        ),
        "",
        "## Required quality metrics",
        "",
    ]
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
            "## Duration-first diagnostics",
            "",
            (f"- Budget fit: {duration['budget_fit_percentage']}%"),
            (f"- Average overrun: {duration['average_overrun_minutes']} minutes"),
            (f"- Average utilization: {duration['average_utilization_percentage']}%"),
            (
                f"- Legacy within/under/over: {duration['legacy_within_target_count']}/"
                f"{duration['legacy_under_target_count']}/{duration['legacy_over_target_count']}"
            ),
            f"- Legacy duration fit: {duration['legacy_duration_fit_percentage']}%",
            (
                "- Legacy average absolute deviation: "
                f"{duration['legacy_average_absolute_deviation_minutes']} minutes"
            ),
            f"- Constrained programs: {duration['legacy_constrained_duration_count']}",
            f"- Late repair: {duration['late_duration_repair_percentage']}%",
            f"- Major late repair: {duration['major_late_repair_percentage']}%",
            (
                "- Proven duration template rejections: "
                f"{duration['proven_duration_template_rejections']}"
            ),
            f"- Breakdowns: {duration['breakdowns']}",
            "",
            "## Template coverage",
            "",
            (
                f"- Selected: {len(cast(Sequence[str], coverage['selected_at_least_once']))}/"
                f"{coverage['active_template_count']}"
            ),
            (
                "- Successful: "
                f"{len(cast(Sequence[str], coverage['successful_at_least_once']))}/"
                f"{coverage['active_template_count']}"
            ),
            f"- Never selected: {coverage['never_selected']}",
            f"- Suspicious unused: {coverage['suspicious_unused']}",
            f"- Rejection categories: {coverage['rejection_categories']}",
            "",
            "## Root-cause clusters",
            "",
            f"- Quality issue findings: {roots['quality_issue_findings']}",
            f"- UNSATISFIED profiles: {roots['unsatisfied_profiles']}",
            "",
            "## Apples-to-apples comparison",
            "",
            f"- Phase 11 normalized categories: {phase11_baseline}",
            f"- Phase 11.5: {phase115}",
            f"- Phase 11.9: {dict(categories)}",
            "",
            "## Determinism",
            "",
            f"- {payload['determinism']}",
            "",
            "## Negative profiles",
            "",
            f"- {payload['negative_cases']}",
        ]
    )
    (output_dir / "phase11-9-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_benchmark(
    db: Session,
    output_dir: Path,
    *,
    determinism_repeats: int = 3,
) -> dict[str, object]:
    profiles = holdout_profiles()
    _assert_new_population(profiles)
    references = load_template_references(db)
    service = phase11._service_for_benchmark(db)
    catalog_by_sex = {sex: service._load_catalog(sex) for sex in (None, Sex.MALE, Sex.FEMALE)}
    catalog = catalog_by_sex[None]
    if len(catalog) < 100 or len(references) < 15:
        raise RuntimeError(
            f"real catalog too small: exercises={len(catalog)} templates={len(references)}"
        )
    records: list[dict[str, object]] = []
    determinism_indices = set(range(min(DETERMINISM_SUBSET_SIZE, len(profiles))))
    for index, profile in enumerate(profiles):
        request = phase11.profile_to_request(profile)
        case_catalog = catalog_by_sex[profile.sex]
        request = phase11.apply_catalog_constraints(request, profile, case_catalog)
        result = generate_program(request, case_catalog, RULESET, reference_templates=references)
        repeats = determinism_repeats if index in determinism_indices else 1
        repeated = [
            generate_program(request, case_catalog, RULESET, reference_templates=references)
            for _ in range(max(1, repeats))
        ]
        fingerprints = tuple(phase11.canonical_fingerprint(item) for item in repeated)
        record = phase11._case_record(profile, request, result, case_catalog, fingerprints)
        input_data = cast(dict[str, object], record["input"])
        input_data["input_fingerprint"] = input_fingerprint(profile)
        template = cast(dict[str, object], record["template"])
        template["eligible_templates"] = sorted(
            str(item["slug"])
            for item in cast(Sequence[Mapping[str, object]], template.get("score_breakdown", ()))
            if isinstance(item.get("slug"), str)
        )
        records.append(record)

    negative_records = []
    for profile in negative_profiles():
        request = phase11.profile_to_request(profile, enforce_matrix=False)
        case_catalog = catalog_by_sex[profile.sex]
        negative_result = generate_program(
            request, case_catalog, RULESET, reference_templates=references
        )
        negative_records.append(
            {
                "profile_id": profile.profile_id,
                "input_fingerprint": input_fingerprint(profile),
                "request_days": request.available_training_days,
                "error_code": negative_result.error_code.value
                if negative_result.error_code
                else None,
                "errors": negative_result.errors,
                "rejected_correctly": negative_result.error_code is not None
                and negative_result.error_code.value == "UNSUPPORTED_RESISTANCE_TRAINING_DAYS",
            }
        )

    aggregate = _aggregate(records, negative_records, references)
    quality_issue_findings = Counter(
        str(finding["code"])
        for record in records
        if record["quality_outcome"] == "QUALITY_ISSUE"
        for finding in cast(Sequence[Mapping[str, object]], record["audit_findings"])
    )
    unsatisfied_profiles = []
    for record in records:
        if record["quality_outcome"] != "UNSATISFIED":
            continue
        unsatisfied_input = cast(Mapping[str, object], record["input"])
        unsatisfied_result = cast(Mapping[str, object], record["result"])
        unsatisfied_profiles.append(
            {
                "profile_id": unsatisfied_input["profile_id"],
                "level": unsatisfied_input["experience_level"],
                "days": unsatisfied_input["resistance_days"],
                "variant": unsatisfied_input["variant"],
                "error_code": unsatisfied_result["error_code"],
                "errors": unsatisfied_result["errors"],
            }
        )
    failure_root_causes = {
        "quality_issue_findings": dict(sorted(quality_issue_findings.items())),
        "unsatisfied_profiles": unsatisfied_profiles,
    }
    determinism = {
        "subset_size": len(determinism_indices),
        "repeats": determinism_repeats,
        "rate": round(
            sum(
                bool(cast(Mapping[str, object], item["determinism"])["identical"])
                for item in records
            )
            / len(records),
            4,
        ),
        "mismatches": [
            item["input"]
            for item in records
            if not cast(Mapping[str, object], item["determinism"])["identical"]
        ],
    }
    phase11_5_comparison = {
        "profiles": 75,
        "quality_pass_rate": 0.9733,
        "generation_success_rate": 1.0,
        "template_success_rate": 0.4444,
        "fallback_activation_rate": 0.68,
        "fallback_success_rate": 1.0,
        "category_counts": {
            "PASS": 0,
            "PASS_WITH_CONSTRAINTS": 73,
            "QUALITY_ISSUE": 2,
            "UNSATISFIED": 0,
            "ENGINE_BUG": 0,
        },
    }
    payload: dict[str, object] = {
        "phase": PHASE,
        "ruleset": RULESET.version,
        "engine_version": RULESET.engine_version,
        "supported_matrix": phase11.SUPPORTED_MATRIX,
        "catalog": {
            "exercise_count": len(catalog),
            "template_count": len(references),
            "catalog_hash": service._catalog_hash(catalog),
            "template_hash": service._template_reference_hash(references),
        },
        "aggregate": aggregate,
        "failure_root_causes": failure_root_causes,
        "determinism": determinism,
        "negative_cases": negative_records,
        "phase11_5_comparison": phase11_5_comparison,
        "template_coverage": _template_coverage(references, records),
        "profiles": records,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "phase11-9-benchmark.json").write_text(
        json.dumps(phase11._jsonable(payload), indent=2, sort_keys=True), encoding="utf-8"
    )
    (output_dir / "phase11-9-profiles.json").write_text(
        json.dumps(
            phase11._jsonable(
                [
                    {
                        "profile_id": profile.profile_id,
                        "input_fingerprint": input_fingerprint(profile),
                        "input": asdict(profile),
                    }
                    for profile in profiles
                ]
            ),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    rows = _csv_rows(records)
    with (output_dir / "phase11-9-summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    _write_summary(payload, output_dir)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Phase 11.9 independent holdout benchmark")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("var/benchmarks/phase11-9-holdout"))
    parser.add_argument("--determinism-repeats", type=int, default=3)
    args = parser.parse_args()
    database_url = args.database_url or os.getenv("TEST_DATABASE_URL") or None
    if database_url is None:
        from app.config import get_settings

        database_url = get_settings().database_url
    engine = create_engine(database_url)
    with Session(engine) as db:
        payload = run_benchmark(
            db,
            args.output_dir,
            determinism_repeats=max(1, args.determinism_repeats),
        )
    print(json.dumps(phase11._jsonable(payload["aggregate"]), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
