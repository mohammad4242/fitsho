from __future__ import annotations

# Dynamic wrappers intentionally access engine-imported callables by name.
# ruff: noqa: B009
import argparse
import hashlib
import json
import subprocess
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

import app.main  # noqa: F401  # Register all SQLAlchemy models for standalone execution.
from app.config import get_settings
from app.database.session import get_engine
from app.exercises.enums import Equipment, ExerciseLabel
from app.profile.enums import TrainingLocation
from app.training_templates.engine_reference import load_template_references
from app.training_templates.models import TrainingProgramTemplate, TrainingProgramTemplateDay
from app.training_templates.tags import TemplateFocusTag
from app.workouts import service as workout_service
from app.workouts.program_engine import engine, session_duration
from app.workouts.program_engine.duration_policy import (
    calculate_main_training_minutes,
    calculate_main_training_minutes_from_exercises,
    calculate_total_session_minutes,
    get_session_duration_policy,
    get_session_exercise_count_policy,
    is_main_training_exercise,
)
from app.workouts.program_engine.enums import (
    Goal,
    PhysicalJobDemand,
    RecoveryRating,
    TrainingExperience,
    TrainingStatus,
)
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ProgramGenerationRequest,
    ProgramGenerationResult,
    RecentTrainingHistory,
    TemplateReference,
    WorkoutDay,
)
from app.workouts.program_engine.supplemental_policy import (
    exercise_count_breakdown,
    is_supplemental_muscle,
)
from app.workouts.program_engine.volume_policy import session_hard_volume_cap

DURATIONS = (30, 45, 60, 75, 90)
LEVELS = ("intermediate", "advanced")
DAY_COUNTS = (4, 5, 6)
REPORT_SCHEMA_VERSION = 1


def _json_ready(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return _json_ready(asdict(value))
    if isinstance(value, Mapping):
        return {str(_json_ready(key)): _json_ready(item) for key, item in value.items()}
    if isinstance(value, Iterable) and not isinstance(value, str | bytes):
        return [_json_ready(item) for item in value]
    return str(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _command_text(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout.strip()


def _worktree_provenance(project_root: Path) -> dict[str, object]:
    diff = subprocess.run(
        ("git", "diff", "--binary"), cwd=project_root, check=True, stdout=subprocess.PIPE
    ).stdout
    status = _command_text("git", "-C", str(project_root), "status", "--porcelain=v1")
    relevant_files = (
        project_root / "backend/app/training_templates/engine_reference.py",
        project_root / "backend/app/training_templates/seed_data.py",
        project_root / "backend/app/workouts/program_engine/engine.py",
        project_root / "backend/app/workouts/program_engine/template_selector.py",
        project_root / "backend/app/workouts/program_engine/template_scoring.py",
        project_root / "backend/app/workouts/program_engine/topology_preference.py",
        project_root / "backend/app/workouts/program_engine/session_duration.py",
        project_root / "backend/app/workouts/program_engine/volume_repair.py",
        project_root / "backend/app/workouts/program_engine/recovery.py",
        project_root / "backend/app/workouts/program_engine/validation.py",
        project_root / "backend/app/workouts/program_engine/final_gate.py",
    )
    return {
        "head": _command_text("git", "-C", str(project_root), "rev-parse", "HEAD"),
        "branch": _command_text("git", "-C", str(project_root), "branch", "--show-current"),
        "worktree_diff_sha256": hashlib.sha256(diff).hexdigest(),
        "dirty_entry_count": len(status.splitlines()) if status else 0,
        "relevant_file_hashes": {
            str(path.relative_to(project_root)): _sha256_file(path) for path in relevant_files
        },
    }


def _load_catalog(db: Session) -> tuple[object, ...]:
    service = object.__new__(workout_service.WorkoutGenerationService)
    service._db = db
    return cast(tuple[object, ...], service._load_catalog())


def _load_template_models(db: Session) -> tuple[TrainingProgramTemplate, ...]:
    return tuple(
        db.scalars(
            select(TrainingProgramTemplate)
            .where(
                TrainingProgramTemplate.is_active.is_(True),
                TrainingProgramTemplate.days_per_week.in_(DAY_COUNTS),
            )
            .options(
                selectinload(TrainingProgramTemplate.days).selectinload(
                    TrainingProgramTemplateDay.slots
                ),
                selectinload(TrainingProgramTemplate.structure),
            )
            .order_by(TrainingProgramTemplate.days_per_week, TrainingProgramTemplate.slug)
        ).all()
    )


def _broad_focus(value: str) -> str:
    lowered = value.lower()
    if "push" in lowered or lowered in {"chest", "chest_triceps", "shoulders_triceps"}:
        return "push"
    if "pull" in lowered or lowered in {"back", "back_biceps"}:
        return "pull"
    if any(token in lowered for token in ("leg", "lower", "quad", "posterior")):
        return "legs"
    return lowered


def _classify_topology(template: TemplateReference) -> str:
    tags = {str(tag) for tag in template.focus_tags}
    if "arnold" in template.slug.lower():
        return "Arnold-style"
    if TemplateFocusTag.SPECIALIZATION.value in tags:
        return "Specialization"
    if {
        TemplateFocusTag.PUSH_PULL_LEGS.value,
        TemplateFocusTag.UPPER_LOWER.value,
    }.issubset(tags):
        return "PPL+UL"
    if TemplateFocusTag.PUSH_PULL_LEGS.value in tags:
        if template.days_per_week == 6:
            focuses = tuple(day.structure_focus for day in template.days)
            first = tuple(_broad_focus(item) for item in focuses[:3])
            second = tuple(_broad_focus(item) for item in focuses[3:])
            if first == ("push", "pull", "legs") and second == first:
                return "PPLx2"
        return "PPL"
    if TemplateFocusTag.UPPER_LOWER.value in tags:
        return "Upper/Lower"
    if TemplateFocusTag.BODY_PART_ROTATION.value in tags:
        return "Body-Part"
    return "Other"


def _template_inventory(
    models: tuple[TrainingProgramTemplate, ...], references: tuple[TemplateReference, ...]
) -> list[dict[str, object]]:
    models_by_slug = {item.slug: item for item in models}
    inventory: list[dict[str, object]] = []
    for reference in references:
        if reference.days_per_week not in DAY_COUNTS:
            continue
        supported = tuple(level for level in reference.supported_levels if level in LEVELS)
        if not supported:
            continue
        model = models_by_slug[reference.slug]
        days: list[dict[str, object]] = []
        for model_day, reference_day in zip(model.days, reference.days, strict=True):
            slots = tuple(model_day.slots)
            days.append(
                {
                    "day_number": model_day.day_number,
                    "title_en": model_day.title_en,
                    "title_fa": model_day.title_fa,
                    "structure_focus": model_day.structure_focus,
                    "initial_slot_count": len(slots),
                    "initial_exercise_count_including_superset_companions": len(slots)
                    + sum(slot.superset_exercise_id is not None for slot in slots),
                    "core_slots": sum(slot.adaptation_priority.value == "core" for slot in slots),
                    "accessory_slots": sum(
                        slot.adaptation_priority.value == "accessory" for slot in slots
                    ),
                    "optional_slots": sum(
                        slot.adaptation_priority.value == "optional" for slot in slots
                    ),
                    "target_muscles": tuple(model_day.direct_target_muscles),
                    "intensity_methods": tuple(
                        dict.fromkeys(slot.intensity_method.value for slot in slots)
                    ),
                    "slots": tuple(
                        {
                            "order": slot.slot_order,
                            "exercise_slug_hint": slot.exercise_slug_hint,
                            "superset_exercise_slug_hint": slot.superset_exercise_slug_hint,
                            "adaptation_priority": slot.adaptation_priority.value,
                            "target_muscles": tuple(slot.target_muscles),
                            "movement_pattern": slot.movement_pattern.value,
                            "intensity_method": slot.intensity_method.value,
                            "sets": slot.sets,
                            "rep_min": slot.rep_min,
                            "rep_max": slot.rep_max,
                            "target_rir": slot.target_rir,
                            "rest_seconds": slot.rest_seconds,
                        }
                        for slot in slots
                    ),
                    "reference_focus": tuple(item.value for item in reference_day.focus),
                }
            )
        focus_tags = tuple(str(tag) for tag in reference.focus_tags)
        inventory.append(
            {
                "slug": reference.slug,
                "name_en": model.name_en,
                "name_fa": model.name_fa,
                "days_per_week": reference.days_per_week,
                "supported_levels": supported,
                "focus_tags": focus_tags,
                "split_type": reference.split_type.value,
                "topology": _classify_topology(reference),
                "structure_slug": model.structure.slug if model.structure is not None else None,
                "structure_family": (
                    model.structure.family.value
                    if model.structure is not None and model.structure.family is not None
                    else None
                ),
                "structure_split_type": (
                    model.structure.split_type.value
                    if model.structure is not None and model.structure.split_type is not None
                    else None
                ),
                "intensity_methods": tuple(reference.intensity_methods),
                "specialization_tags": tuple(
                    tag
                    for tag in focus_tags
                    if tag
                    not in {
                        TemplateFocusTag.FULL_BODY.value,
                        TemplateFocusTag.UPPER_LOWER.value,
                        TemplateFocusTag.PUSH_PULL_LEGS.value,
                        TemplateFocusTag.BODY_PART_ROTATION.value,
                        TemplateFocusTag.BALANCED.value,
                    }
                ),
                "days": days,
            }
        )
    return inventory


def _baseline_request(level: str, days: int, duration: int) -> ProgramGenerationRequest:
    experience = TrainingExperience(level)
    training_age_months = 30 if experience is TrainingExperience.INTERMEDIATE else 84
    consistent_weeks = 52 if experience is TrainingExperience.INTERMEDIATE else 156
    return ProgramGenerationRequest(
        user_id=uuid5(
            NAMESPACE_URL, f"https://fitsho.local/template-survival/{level}/{days}/{duration}"
        ),
        age=30,
        height_cm=178,
        weight_kg=80,
        primary_goal=Goal.HYPERTROPHY,
        training_experience=experience,
        training_age_months=training_age_months,
        current_activity_level="high",
        available_training_days=days,
        session_duration_minutes=duration,
        available_equipment=frozenset(Equipment),
        training_location=TrainingLocation.GYM,
        priority_muscles=frozenset(),
        injuries_and_limitations=(),
        blocked_exercises=frozenset(),
        blocked_movement_patterns=frozenset(),
        blocked_caution_tags=frozenset(),
        sleep_quality=RecoveryRating.GOOD,
        stress_level=RecoveryRating.AVERAGE,
        physical_job_demand=PhysicalJobDemand.LOW,
        recent_training_history=RecentTrainingHistory(
            consistent_weeks=consistent_weeks, completed_session_ratio=0.95
        ),
        program_duration_weeks=8,
        seed_optional=20260830,
    )


def _snapshot_day(day: WorkoutDay) -> dict[str, object]:
    breakdown = exercise_count_breakdown(day.exercises)
    return {
        "day_index": day.day_index,
        "weekday": day.weekday,
        "title": day.title,
        "focus": day.focus,
        "template_structure_focus": day.template_structure_focus,
        "template_target_muscles": tuple(item.value for item in day.template_target_muscles),
        "main_exercise_count": breakdown.main_count,
        "supplemental_exercise_count": breakdown.supplemental_count,
        "total_exercise_count": breakdown.total_count,
        "main_working_sets": sum(
            exercise.sets for exercise in day.exercises if is_main_training_exercise(exercise)
        ),
        "total_working_sets": sum(exercise.sets for exercise in day.exercises),
        "main_training_minutes": calculate_main_training_minutes(day),
        "total_session_minutes": calculate_total_session_minutes(day),
        "exercises": tuple(
            {
                "exercise_id": str(exercise.exercise_id),
                "slug": exercise.exercise_slug,
                "name": exercise.exercise_name,
                "primary_muscle": (
                    exercise.primary_muscle.value if exercise.primary_muscle is not None else None
                ),
                "exercise_type": exercise.exercise_type.value,
                "sets": exercise.sets,
                "estimated_minutes": exercise.estimated_minutes,
                "reason_codes": exercise.reason_codes,
            }
            for exercise in day.exercises
        ),
    }


def _snapshot_days(days: Sequence[WorkoutDay]) -> tuple[dict[str, object], ...]:
    return tuple(_snapshot_day(day) for day in days)


class DiagnosticRecorder(AbstractContextManager["DiagnosticRecorder"]):
    def __init__(self) -> None:
        self.case_id = ""
        self.current_template: str | None = None
        self.attempts: dict[str, dict[str, object]] = {}
        self._patches: list[tuple[ModuleType, str, object]] = []
        self._active_repair_operation: dict[str, object] | None = None

    def __enter__(self) -> DiagnosticRecorder:
        self._install()
        return self

    def __exit__(self, *args: object) -> None:
        for module, name, original in reversed(self._patches):
            setattr(module, name, original)

    def begin(self, case_id: str) -> None:
        self.case_id = case_id
        self.current_template = None
        self.attempts = {}

    def finish(self) -> dict[str, object]:
        return cast(dict[str, object], _json_ready(self.attempts))

    def _attempt(self, slug: str | None = None) -> dict[str, object] | None:
        target = slug or self.current_template
        if target is None:
            return None
        return self.attempts.setdefault(
            target,
            {
                "slug": target,
                "stages": [],
                "duration_operations": [],
                "set_addition_attempts": [],
                "exercise_addition_attempts": [],
            },
        )

    def _append_stage(self, stage: str, **payload: object) -> None:
        attempt = self._attempt()
        if attempt is None:
            return
        cast(list[object], attempt["stages"]).append({"stage": stage, **payload})

    def _patch(self, module: ModuleType, name: str, wrapper: Callable[..., object]) -> None:
        original = getattr(module, name)
        self._patches.append((module, name, original))
        setattr(module, name, wrapper)

    def _install(self) -> None:
        original_build = cast(Callable[..., Any], getattr(engine, "build_template_sessions"))

        def build_wrapper(*args: object, **kwargs: object) -> object:
            reference = cast(TemplateReference, args[1])
            self.current_template = reference.slug
            self._attempt(reference.slug)
            try:
                result = original_build(*args, **kwargs)
            except Exception as error:
                reason_codes = tuple(getattr(error, "reason_codes", (str(error),)))
                self._append_stage(
                    "template_construction",
                    status="failed",
                    error_type=type(error).__name__,
                    reason_codes=reason_codes,
                )
                raise
            self._append_stage(
                "template_construction",
                status="succeeded",
                drafts=tuple(
                    {
                        "day_index": draft.day_index,
                        "focus": draft.focus,
                        "exercise_count": len(draft.exercises),
                        "exercise_ids": tuple(str(item.id) for item in draft.exercises),
                        "reason_codes": draft.reason_codes,
                    }
                    for draft in result.drafts
                ),
            )
            return result

        self._patch(engine, "build_template_sessions", build_wrapper)

        original_reference = cast(Callable[..., Any], getattr(engine, "_reference_program"))

        def reference_wrapper(*args: object, **kwargs: object) -> object:
            reference = cast(TemplateReference, args[7])
            self.current_template = reference.slug
            return original_reference(*args, **kwargs)

        self._patch(engine, "_reference_program", reference_wrapper)

        original_dynamic = cast(Callable[..., Any], getattr(engine, "_program_for_split"))

        def dynamic_wrapper(*args: object, **kwargs: object) -> object:
            self.current_template = None
            return original_dynamic(*args, **kwargs)

        self._patch(engine, "_program_for_split", dynamic_wrapper)

        original_prescribe = cast(Callable[..., Any], getattr(engine, "prescribe_sessions"))

        def prescribe_wrapper(*args: object, **kwargs: object) -> object:
            result = original_prescribe(*args, **kwargs)
            self._append_stage("session_building", status="completed", days=_snapshot_days(result))
            return result

        self._patch(engine, "prescribe_sessions", prescribe_wrapper)

        original_volume = cast(Callable[..., Any], getattr(engine, "repair_weekly_volume"))

        def volume_wrapper(*args: object, **kwargs: object) -> object:
            before = _snapshot_days(cast(Sequence[WorkoutDay], args[0]))
            result = original_volume(*args, **kwargs)
            days, reasons = result
            self._append_stage(
                "volume_repair",
                status="completed",
                before=before,
                after=_snapshot_days(days),
                reason_codes=reasons,
            )
            return result

        self._patch(engine, "repair_weekly_volume", volume_wrapper)

        original_duration = cast(Callable[..., Any], getattr(engine, "repair_session_durations"))

        def duration_wrapper(*args: object, **kwargs: object) -> object:
            before_days = cast(Sequence[WorkoutDay], args[0])
            result = original_duration(*args, **kwargs)
            attempt = self._attempt()
            operation = {
                "certification": bool(kwargs.get("_certification", False)),
                "before": _snapshot_days(before_days),
                "after": _snapshot_days(result.days),
                "reason_codes": result.reasons,
                "evidence": tuple(item.as_trace() for item in result.evidence),
            }
            if attempt is not None:
                cast(list[object], attempt["duration_operations"]).append(operation)
            self._append_stage("duration_repair", status="completed", **operation)
            return result

        self._patch(engine, "repair_session_durations", duration_wrapper)

        original_recovery = cast(Callable[..., Any], getattr(engine, "repair_recovery_weekdays"))

        def recovery_wrapper(*args: object, **kwargs: object) -> object:
            before = _snapshot_days(cast(Sequence[WorkoutDay], args[1]))
            split, days, reasons = original_recovery(*args, **kwargs)
            self._append_stage(
                "recovery_repair",
                status="completed",
                before=before,
                after=_snapshot_days(days),
                reason_codes=reasons,
                weekdays=split.weekdays,
            )
            return split, days, reasons

        self._patch(engine, "repair_recovery_weekdays", recovery_wrapper)

        original_validation = cast(Callable[..., Any], getattr(engine, "validate_program"))

        def validation_wrapper(*args: object, **kwargs: object) -> object:
            result = original_validation(*args, **kwargs)
            program = cast(Any, args[0])
            self._append_stage(
                "validation",
                status="passed" if result.is_valid else "failed",
                days=_snapshot_days(program.weekly_schedule),
                errors=result.errors,
                warnings=result.warnings,
                metrics=result.metrics,
            )
            return result

        self._patch(engine, "validate_program", validation_wrapper)

        original_gate = cast(Callable[..., Any], getattr(engine, "evaluate_final_program"))

        def gate_wrapper(*args: object, **kwargs: object) -> object:
            result = original_gate(*args, **kwargs)
            program = cast(Any, args[0])
            self._append_stage(
                "final_quality_gate",
                status="accepted" if result.is_accepted else "rejected",
                days=_snapshot_days(program.weekly_schedule),
                reason_codes=result.reason_codes,
                constraint_reason_codes=result.constraint_reason_codes,
                metrics=result.metrics,
            )
            return result

        self._patch(engine, "evaluate_final_program", gate_wrapper)
        self._install_duration_operation_tracing()

    def _install_duration_operation_tracing(self) -> None:
        original_set = cast(Callable[..., Any], getattr(session_duration, "_select_set_addition"))

        def set_wrapper(*args: object, **kwargs: object) -> object:
            day = cast(WorkoutDay, args[0])
            exercises = cast(list[object], args[1])
            operation: dict[str, object] = {
                "day_index": day.day_index,
                "before_main_training_minutes": calculate_main_training_minutes(day),
                "before_main_exercise_count": exercise_count_breakdown(exercises).main_count,
                "rejection_categories": Counter(),
            }
            self._active_repair_operation = operation
            try:
                result = original_set(*args, **kwargs)
                if result is None:
                    self._diagnose_set_rejections(*args)
            finally:
                self._active_repair_operation = None
            operation["success"] = result is not None
            if result is not None:
                _index, updated = result
                operation["selected_exercise_id"] = str(updated.exercise_id)
                operation["selected_exercise_name"] = updated.exercise_name
                operation["selected_sets"] = updated.sets
            operation["rejection_categories"] = dict(
                cast(Counter[str], operation["rejection_categories"])
            )
            attempt = self._attempt()
            if attempt is not None:
                cast(list[object], attempt["set_addition_attempts"]).append(operation)
            return result

        self._patch(session_duration, "_select_set_addition", set_wrapper)

        original_exercise = cast(
            Callable[..., Any], getattr(session_duration, "_select_exercise_addition")
        )

        def exercise_wrapper(*args: object, **kwargs: object) -> object:
            day = cast(WorkoutDay, args[0])
            exercises = cast(list[object], args[1])
            operation: dict[str, object] = {
                "day_index": day.day_index,
                "before_main_training_minutes": calculate_main_training_minutes(day),
                "before_main_exercise_count": exercise_count_breakdown(exercises).main_count,
                "candidate_pool_size": len(cast(Sequence[object], args[3])),
                "rejection_categories": Counter(),
            }
            self._active_repair_operation = operation
            try:
                result = original_exercise(*args, **kwargs)
            finally:
                self._active_repair_operation = None
            operation["success"] = result is not None
            if result is not None:
                operation["selected_exercise_id"] = str(result.exercise_id)
                operation["selected_exercise_name"] = result.exercise_name
                operation["selected_primary_muscle"] = (
                    result.primary_muscle.value if result.primary_muscle is not None else None
                )
            self._diagnose_exercise_prefilters(operation, *args)
            operation["rejection_categories"] = dict(
                cast(Counter[str], operation["rejection_categories"])
            )
            attempt = self._attempt()
            if attempt is not None:
                cast(list[object], attempt["exercise_addition_attempts"]).append(operation)
            return result

        self._patch(session_duration, "_select_exercise_addition", exercise_wrapper)

        original_hard_volume = cast(
            Callable[..., Any], getattr(session_duration, "_within_weekly_hard_volume")
        )

        def hard_volume_wrapper(*args: object, **kwargs: object) -> object:
            result = original_hard_volume(*args, **kwargs)
            if result is False and self._active_repair_operation is not None:
                categories = cast(
                    Counter[str], self._active_repair_operation["rejection_categories"]
                )
                categories["weekly_hard_volume_cap"] += 1
            return result

        self._patch(session_duration, "_within_weekly_hard_volume", hard_volume_wrapper)

        original_acceptable = cast(
            Callable[..., Any], getattr(session_duration, "_acceptable_volume_change")
        )

        def acceptable_wrapper(*args: object, **kwargs: object) -> object:
            result = original_acceptable(*args, **kwargs)
            if result is False and self._active_repair_operation is not None:
                categories = cast(
                    Counter[str], self._active_repair_operation["rejection_categories"]
                )
                categories["acceptable_volume_preference"] += 1
            return result

        self._patch(session_duration, "_acceptable_volume_change", acceptable_wrapper)

    def _diagnose_set_rejections(self, *args: object) -> None:
        if self._active_repair_operation is None:
            return
        exercises = cast(list[Any], args[1])
        request = cast(Any, args[2])
        policy = cast(Any, args[3])
        ruleset = cast(Any, args[4])
        categories = cast(Counter[str], self._active_repair_operation["rejection_categories"])
        for exercise in exercises:
            if not is_main_training_exercise(exercise) or exercise.primary_muscle is None:
                categories["no_useful_candidate"] += 1
                continue
            if exercise.sets >= ruleset.max_working_sets_for_exercise(
                training_status=request.training_status,
                goal=request.primary_goal,
                exercise_type=exercise.exercise_type,
                is_priority=exercise.primary_muscle in request.source.priority_muscles,
                weekly_exposure_count=1,
            ):
                categories["exercise_set_cap"] += 1
            direct_sets = sum(
                item.sets for item in exercises if item.primary_muscle is exercise.primary_muscle
            )
            if direct_sets + 1 > session_hard_volume_cap(request.source.training_age_months):
                categories["session_volume_cap"] += 1
            updated = session_duration._with_additional_set(exercise, ruleset)
            simulated = [*exercises]
            simulated[exercises.index(exercise)] = updated
            if calculate_main_training_minutes_from_exercises(simulated) > policy.maximum_minutes:
                categories["duration_maximum"] += 1
        if not categories:
            categories["no_useful_candidate"] += 1

    def _diagnose_exercise_prefilters(self, operation: dict[str, object], *args: object) -> None:
        day = cast(WorkoutDay, args[0])
        exercises = cast(list[Any], args[1])
        candidates = cast(Sequence[Any], args[3])
        ruleset = cast(Any, args[5])
        categories = cast(Counter[str], operation["rejection_categories"])
        existing_ids = {item.exercise_id for item in exercises}
        template_muscles = frozenset(day.template_target_muscles).union(
            item.primary_muscle for item in exercises if item.primary_muscle is not None
        )
        count_policy = get_session_exercise_count_policy(
            cast(Any, args[4]).requested_minutes, ruleset
        )
        if exercise_count_breakdown(exercises).main_count >= count_policy.maximum_main_exercises:
            categories["duration_maximum"] += len(candidates)
            return
        for candidate in candidates:
            if candidate.id in existing_ids:
                categories["duplicate"] += 1
                continue
            if is_supplemental_muscle(candidate.primary_muscle):
                categories["no_useful_candidate"] += 1
                continue
            if (
                day.focus.startswith("template_reference")
                and template_muscles
                and candidate.primary_muscle not in template_muscles
            ):
                categories["wrong_template_muscle"] += 1
                continue
            candidate_is_safe = cast(
                Callable[[Any, Any], bool],
                getattr(session_duration, "_candidate_is_safe"),
            )
            if not candidate_is_safe(candidate, cast(Any, args[2])):
                categories["safety"] += 1
                continue
            if not is_main_training_exercise(candidate) or ExerciseLabel.CARDIO in candidate.labels:
                categories["no_useful_candidate"] += 1
                continue
            has_near_equivalent = cast(
                Callable[[Any, Sequence[Any]], bool],
                getattr(session_duration, "has_near_equivalent"),
            )
            if has_near_equivalent(candidate, exercises):
                categories["near_equivalent"] += 1
                continue
            if candidate.primary_muscle is not None:
                direct_sets = sum(
                    item.sets
                    for item in exercises
                    if item.primary_muscle is candidate.primary_muscle
                )
                session_cap = session_hard_volume_cap(cast(Any, args[2]).source.training_age_months)
                if direct_sets + ruleset.minimum_working_sets > session_cap:
                    categories["session_volume_cap"] += 1
        if not categories and operation.get("success") is False:
            categories["no_useful_candidate"] += 1


def _walk_trace(value: object) -> Iterable[dict[str, object]]:
    if isinstance(value, Mapping):
        item = {str(key): cast(object, child) for key, child in value.items()}
        yield item
        for child in value.values():
            yield from _walk_trace(child)
    elif isinstance(value, Iterable) and not isinstance(value, str | bytes):
        for child in value:
            yield from _walk_trace(child)


def _trace_entries(result: ProgramGenerationResult, stage: str) -> list[dict[str, object]]:
    return [item for item in _walk_trace(result.decision_trace) if item.get("stage") == stage]


def _selection_trace(result: ProgramGenerationResult) -> dict[str, object] | None:
    return next(iter(_trace_entries(result, "template_selection")), None)


def _attempt_sequence(result: ProgramGenerationResult) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    seen: set[tuple[object, object, object]] = set()
    for item in _trace_entries(result, "template_attempt"):
        key = (item.get("rank"), item.get("slug"), item.get("status"))
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
    return sorted(items, key=lambda item: cast(int, item.get("rank", 9999)))


def _failure_stage(
    template_slug: str,
    selection: dict[str, object] | None,
    attempt: dict[str, object] | None,
    diagnostics: dict[str, object] | None,
) -> str | None:
    if attempt is not None and attempt.get("status") == "succeeded":
        return None
    if attempt is None:
        hard_rejections = (
            cast(Sequence[Mapping[str, object]], selection.get("hard_rejections", ()))
            if selection
            else ()
        )
        if any(item.get("slug") == template_slug for item in hard_rejections):
            return "hard_eligibility"
        return "not_attempted"
    stages = cast(Sequence[Mapping[str, object]], (diagnostics or {}).get("stages", ()))
    for stage_name in ("final_quality_gate", "validation"):
        if any(
            stage.get("stage") == stage_name and stage.get("status") in {"rejected", "failed"}
            for stage in stages
        ):
            return stage_name
    reason_text = " ".join(
        str(item) for item in cast(Sequence[object], attempt.get("reason_codes", ()))
    )
    if "DURATION" in reason_text:
        return "duration_repair"
    if "RECOVERY" in reason_text:
        return "recovery_repair"
    if "VOLUME" in reason_text:
        return "volume_repair"
    if "TEMPLATE_SESSION" in reason_text or "INITIAL_TEMPLATE" in reason_text:
        return "template_construction"
    return "adaptation_or_validation"


def _reason_codes_for_template(
    template_slug: str,
    selection: dict[str, object] | None,
    attempt: dict[str, object] | None,
) -> tuple[str, ...]:
    if attempt is not None:
        return tuple(str(item) for item in cast(Sequence[object], attempt.get("reason_codes", ())))
    if selection is not None:
        for rejected in cast(Sequence[Mapping[str, object]], selection.get("hard_rejections", ())):
            if rejected.get("slug") == template_slug:
                return tuple(
                    str(item) for item in cast(Sequence[object], rejected.get("reason_codes", ()))
                )
    return ("TEMPLATE_NOT_ATTEMPTED",)


def _primary_root_cause(reason_codes: Sequence[str]) -> str | None:
    priority_fragments = (
        "SESSION_DURATION_TARGET_UNSATISFIED",
        "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS",
        "MAIN_EXERCISE_COUNT",
        "WEEKLY_MUSCLE_VOLUME",
        "PER_SESSION_MUSCLE_VOLUME",
        "RECOVERY_SPACING",
        "RECOVERY",
        "TEMPLATE_SESSION_EXERCISE_COUNT_UNSATISFIED",
        "TEMPLATE_SESSION",
        "REQUIRED_CORE_DURATION_INFEASIBLE",
        "CORE_SLOT_UNRESOLVABLE",
        "VALIDATION",
    )
    for fragment in priority_fragments:
        for code in reason_codes:
            if fragment in code:
                return code
    return reason_codes[0] if reason_codes else None


def _forced_case(
    recorder: DiagnosticRecorder,
    template: TemplateReference,
    request: ProgramGenerationRequest,
    catalog: tuple[object, ...],
) -> dict[str, object]:
    level = request.training_experience.value
    duration = request.session_duration_minutes
    case_id = f"forced:{template.slug}:{level}:{duration}"
    recorder.begin(case_id)
    result = engine.generate_program(
        request,
        cast(tuple[Any, ...], catalog),
        RULESET,
        reference_templates=(template,),
    )
    diagnostics_by_slug = recorder.finish()
    selection = _selection_trace(result)
    attempts = _attempt_sequence(result)
    attempt = next((item for item in attempts if item.get("slug") == template.slug), None)
    survived = attempt is not None and attempt.get("status") == "succeeded"
    reason_codes = () if survived else _reason_codes_for_template(template.slug, selection, attempt)
    diagnostics = cast(dict[str, object] | None, diagnostics_by_slug.get(template.slug))
    policy = get_session_duration_policy(duration)
    count_policy = get_session_exercise_count_policy(duration, RULESET)
    return {
        "case_id": case_id,
        "template_slug": template.slug,
        "level": level,
        "normalized_training_status": normalize_request(request, RULESET).training_status.value,
        "days": template.days_per_week,
        "duration": duration,
        "duration_policy": {
            "requested_main_training_minutes": duration,
            "minimum_main_training_minutes": policy.minimum_minutes,
            "maximum_main_training_minutes": policy.maximum_minutes,
            "minimum_main_exercises": count_policy.minimum_main_exercises,
            "maximum_main_exercises": count_policy.maximum_main_exercises,
        },
        "forced_template_result": "PASS" if survived else "FAIL",
        "failure_stage": _failure_stage(template.slug, selection, attempt, diagnostics),
        "primary_failure_cause": _primary_root_cause(reason_codes),
        "reason_codes": reason_codes,
        "overall_engine_result": "SUCCESS" if result.is_success else "FAILURE",
        "overall_error_code": result.error_code.value if result.error_code is not None else None,
        "overall_errors": result.errors,
        "fallback_split": (
            result.program.split.split_type.value if result.program is not None else None
        ),
        "selection": selection,
        "attempt": attempt,
        "diagnostics": diagnostics,
    }


def _competition_case(
    recorder: DiagnosticRecorder,
    templates: tuple[TemplateReference, ...],
    request: ProgramGenerationRequest,
    catalog: tuple[object, ...],
) -> dict[str, object]:
    level = request.training_experience.value
    duration = request.session_duration_minutes
    days = request.available_training_days
    case_id = f"competition:{days}:{level}:{duration}"
    recorder.begin(case_id)
    result = engine.generate_program(
        request,
        cast(tuple[Any, ...], catalog),
        RULESET,
        reference_templates=templates,
    )
    diagnostics = recorder.finish()
    selection = _selection_trace(result)
    attempts = _attempt_sequence(result)
    successful_attempt = next(
        (item for item in attempts if item.get("status") == "succeeded"), None
    )
    final_template = successful_attempt.get("slug") if successful_attempt is not None else None
    rankings = (
        cast(Sequence[Mapping[str, object]], selection.get("candidates", ())) if selection else ()
    )
    upper_lower_slugs = {
        template.slug for template in templates if template.split_type.value == "upper_lower"
    }
    upper_lower_rank = next(
        (
            cast(int, item.get("rank"))
            for item in rankings
            if cast(str, item.get("slug", "")) in upper_lower_slugs
        ),
        None,
    )
    professional_before_upper_lower = (
        sum(
            cast(int, item.get("rank", 9999)) < upper_lower_rank
            and cast(dict[str, int], item.get("score", {})).get("professional_structure", 0) > 0
            for item in rankings
        )
        if upper_lower_rank is not None
        else 0
    )
    return {
        "case_id": case_id,
        "level": level,
        "normalized_training_status": normalize_request(request, RULESET).training_status.value,
        "days": days,
        "duration": duration,
        "input_template_slugs": tuple(template.slug for template in templates),
        "input_template_count": len(templates),
        "overall_engine_result": "SUCCESS" if result.is_success else "FAILURE",
        "overall_error_code": result.error_code.value if result.error_code is not None else None,
        "overall_errors": result.errors,
        "final_selected_template": final_template,
        "final_split_type": (
            result.program.split.split_type.value if result.program is not None else None
        ),
        "final_topology_source": "template" if final_template is not None else "dynamic_fallback",
        "selection": selection,
        "attempt_sequence": attempts,
        "professional_templates_before_first_upper_lower": professional_before_upper_lower,
        "diagnostics": diagnostics,
    }


def _aggregate(
    inventory: Sequence[Mapping[str, object]],
    forced_cases: Sequence[Mapping[str, object]],
    competition_cases: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    topology_by_slug = {str(item["slug"]): str(item["topology"]) for item in inventory}
    topology_rows: dict[str, dict[str, object]] = {}
    duration_rows: dict[int, dict[str, object]] = {}
    level_rows: dict[str, dict[str, object]] = {}
    template_rows: dict[str, dict[str, object]] = {}
    root_causes: Counter[str] = Counter()

    def bucket(target: dict[Any, dict[str, object]], key: object) -> dict[str, object]:
        return target.setdefault(
            key,
            {
                "tests": 0,
                "passed": 0,
                "failed": 0,
                "duration_failures": 0,
                "volume_failures": 0,
                "recovery_failures": 0,
                "construction_failures": 0,
                "validation_failures": 0,
            },
        )

    for case in forced_cases:
        slug = str(case["template_slug"])
        passed = case["forced_template_result"] == "PASS"
        reason_codes = tuple(str(item) for item in cast(Sequence[object], case["reason_codes"]))
        reason_text = " ".join(reason_codes)
        primary = case.get("primary_failure_cause")
        if not passed and primary is not None:
            root_causes[str(primary)] += 1
        targets = (
            bucket(topology_rows, topology_by_slug[slug]),
            bucket(duration_rows, int(cast(int, case["duration"]))),
            bucket(level_rows, str(case["level"])),
            bucket(template_rows, slug),
        )
        for row in targets:
            row["tests"] = int(cast(int, row["tests"])) + 1
            outcome_key = "passed" if passed else "failed"
            row[outcome_key] = int(cast(int, row[outcome_key])) + 1
            if not passed:
                row["duration_failures"] = int(cast(int, row["duration_failures"])) + int(
                    "DURATION" in reason_text or "MAIN_EXERCISE_COUNT" in reason_text
                )
                row["volume_failures"] = int(cast(int, row["volume_failures"])) + int(
                    "VOLUME" in reason_text
                )
                row["recovery_failures"] = int(cast(int, row["recovery_failures"])) + int(
                    "RECOVERY" in reason_text
                )
                row["construction_failures"] = int(cast(int, row["construction_failures"])) + int(
                    case.get("failure_stage") == "template_construction"
                )
                row["validation_failures"] = int(cast(int, row["validation_failures"])) + int(
                    case.get("failure_stage") in {"validation", "final_quality_gate"}
                )

    for collection in (topology_rows, duration_rows, level_rows, template_rows):
        for row in collection.values():
            tests = int(cast(int, row["tests"]))
            row["success_rate"] = round(int(cast(int, row["passed"])) / tests * 100, 1)

    upper = topology_rows.get("Upper/Lower", {"tests": 0, "passed": 0})
    professional_cases = [
        case
        for case in forced_cases
        if topology_by_slug[str(case["template_slug"])] != "Upper/Lower"
    ]
    professional_passed = sum(
        case["forced_template_result"] == "PASS" for case in professional_cases
    )
    return {
        "overall": {
            "tests": len(forced_cases),
            "passed": sum(case["forced_template_result"] == "PASS" for case in forced_cases),
            "failed": sum(case["forced_template_result"] == "FAIL" for case in forced_cases),
            "success_rate": round(
                sum(case["forced_template_result"] == "PASS" for case in forced_cases)
                / len(forced_cases)
                * 100,
                1,
            ),
            "upper_lower_survival_rate": round(
                int(cast(int, upper.get("passed", 0)))
                / max(1, int(cast(int, upper.get("tests", 0))))
                * 100,
                1,
            ),
            "professional_topology_survival_rate": round(
                professional_passed / max(1, len(professional_cases)) * 100, 1
            ),
            "competition_scenarios": len(competition_cases),
            "competition_upper_lower_outputs": sum(
                case.get("final_split_type") in {"upper_lower", "upper_lower_x3"}
                or (
                    case.get("final_selected_template") is not None
                    and topology_by_slug.get(str(case["final_selected_template"])) == "Upper/Lower"
                )
                for case in competition_cases
            ),
        },
        "by_topology": topology_rows,
        "by_duration": duration_rows,
        "by_level": level_rows,
        "by_template": template_rows,
        "root_causes": tuple(
            {"code": code, "count": count} for code, count in root_causes.most_common()
        ),
    }


def run_audit(output_path: Path, *, forced_limit: int | None = None) -> dict[str, object]:
    backend_root = Path(__file__).resolve().parents[1]
    project_root = backend_root.parent
    settings = get_settings()
    with Session(get_engine(settings.database_url)) as db:
        all_references = load_template_references(db)
        references = tuple(
            item
            for item in all_references
            if item.days_per_week in DAY_COUNTS
            and any(level in item.supported_levels for level in LEVELS)
        )
        models = _load_template_models(db)
        inventory = _template_inventory(models, references)
        catalog = _load_catalog(db)

        expected_keys = {
            (reference.slug, level, duration)
            for reference in references
            for level in reference.supported_levels
            if level in LEVELS
            for duration in DURATIONS
        }
        requests: dict[tuple[int, str, int], ProgramGenerationRequest] = {}
        baseline_statuses: list[dict[str, object]] = []
        for days in DAY_COUNTS:
            for level in LEVELS:
                for duration in DURATIONS:
                    request = _baseline_request(level, days, duration)
                    normalized = normalize_request(request, RULESET)
                    expected_status = TrainingStatus(level)
                    if normalized.training_status is not expected_status:
                        raise RuntimeError(
                            f"Invalid baseline {days}/{level}/{duration}: "
                            f"{normalized.training_status.value}"
                        )
                    requests[(days, level, duration)] = request
                    baseline_statuses.append(
                        {
                            "days": days,
                            "level": level,
                            "duration": duration,
                            "normalized_training_status": normalized.training_status.value,
                            "assumptions": normalized.assumptions,
                        }
                    )

        forced_plan = [
            (reference, level, duration)
            for reference in references
            for level in reference.supported_levels
            if level in LEVELS
            for duration in DURATIONS
        ]
        if forced_limit is not None:
            forced_plan = forced_plan[:forced_limit]

        forced_cases: list[dict[str, object]] = []
        competition_cases: list[dict[str, object]] = []
        with DiagnosticRecorder() as recorder:
            for reference, level, duration in forced_plan:
                forced_cases.append(
                    _forced_case(
                        recorder,
                        reference,
                        requests[(reference.days_per_week, level, duration)],
                        catalog,
                    )
                )
            if forced_limit is None:
                for days in DAY_COUNTS:
                    for level in LEVELS:
                        scenario_templates = tuple(
                            reference
                            for reference in references
                            if reference.days_per_week == days
                            and level in reference.supported_levels
                        )
                        for duration in DURATIONS:
                            competition_cases.append(
                                _competition_case(
                                    recorder,
                                    scenario_templates,
                                    requests[(days, level, duration)],
                                    catalog,
                                )
                            )

        actual_keys = {
            (
                str(case["template_slug"]),
                str(case["level"]),
                int(cast(int, case["duration"])),
            )
            for case in forced_cases
        }
        expected_competitions = len(DAY_COUNTS) * len(LEVELS) * len(DURATIONS)
        coverage = {
            "expected_template_level_duration_cases": len(expected_keys),
            "executed_forced_cases": len(forced_cases),
            "expected_competition_scenarios": expected_competitions,
            "executed_competition_scenarios": len(competition_cases),
            "missing_forced_keys": tuple(sorted(expected_keys - actual_keys)),
            "unexpected_forced_keys": tuple(sorted(actual_keys - expected_keys)),
            "complete": forced_limit is None
            and actual_keys == expected_keys
            and len(competition_cases) == expected_competitions,
        }
        if forced_limit is None and not coverage["complete"]:
            raise RuntimeError(f"Audit matrix coverage incomplete: {coverage}")

        exercise_counts = Counter(
            "eligible_baseline"
            if item.is_active and item.is_programmable and not item.needs_review
            else "filtered_baseline"
            for item in cast(Sequence[Any], catalog)
        )
        payload = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "provenance": {
                **_worktree_provenance(project_root),
                "database_url_redacted": settings.database_url.rsplit("@", maxsplit=1)[-1],
                "template_reference_count_all_active": len(all_references),
                "template_reference_count_audited": len(references),
                "exercise_catalog_count": len(catalog),
                "exercise_catalog_baseline_eligibility_counts": dict(exercise_counts),
                "template_reference_sha256": hashlib.sha256(
                    json.dumps(
                        _json_ready([asdict(item) for item in references]),
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest(),
            },
            "baseline": {
                "profile_contract": {
                    "training_location": "gym",
                    "available_equipment": tuple(item.value for item in Equipment),
                    "injuries_and_limitations": (),
                    "blocked_caution_tags": (),
                    "sleep_quality": "good",
                    "stress_level": "average",
                    "physical_job_demand": "low",
                    "primary_goal": "hypertrophy",
                    "priority_muscles": (),
                    "intermediate_training_age_months": 30,
                    "advanced_training_age_months": 84,
                    "intermediate_consistent_weeks": 52,
                    "advanced_consistent_weeks": 156,
                },
                "normalization_checks": baseline_statuses,
            },
            "template_inventory": inventory,
            "forced_cases": forced_cases,
            "competition_cases": competition_cases,
            "coverage": coverage,
            "aggregates": _aggregate(inventory, forced_cases, competition_cases),
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(_json_ready(payload), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return cast(dict[str, object], _json_ready(payload))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit real 4/5/6-day template survival.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../reports/fitsho_4_5_6_day_template_survival_raw.json"),
    )
    parser.add_argument("--forced-limit", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    payload = run_audit(args.output.resolve(), forced_limit=args.forced_limit)
    coverage = cast(dict[str, object], payload["coverage"])
    aggregates = cast(dict[str, object], payload["aggregates"])
    overall = cast(dict[str, object], aggregates["overall"])
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "templates": len(cast(list[object], payload["template_inventory"])),
                "forced_cases": coverage["executed_forced_cases"],
                "competition_cases": coverage["executed_competition_scenarios"],
                "passed": overall["passed"],
                "failed": overall["failed"],
                "coverage_complete": coverage["complete"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
