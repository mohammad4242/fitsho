from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy.orm import Session

from app.athlete_state.service import AthleteStateBuilder
from app.auth.models import User
from app.body_analysis.enums import BodyArea
from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseType,
    MediaType,
    MovementPattern,
    MuscleGroup,
)
from app.exercises.models import Exercise, ExerciseEquipment
from app.exercises.taxonomy import FOCUSES_BY_MUSCLE
from app.profile.enums import (
    ExperienceLevel,
    FitnessGoal,
    HomeTrainingSetup,
    Sex,
    TrainingLocation,
)
from app.profile.models import BodyMeasurement, UserProfile
from app.workout_cycles.body_progress_models import WorkoutCycleBodyProgressComparison
from app.workout_cycles.enums import (
    WorkoutCycleFeedbackProgress,
    WorkoutCycleStatus,
    WorkoutCycleWeeklyCheckInDifficulty,
    WorkoutCycleWeeklyCheckInRecovery,
    WorkoutExercisePreferenceType,
    WorkoutExerciseReplacementReason,
    WorkoutExerciseReplacementScope,
    WorkoutExerciseSafetySignalType,
)
from app.workout_cycles.models import (
    WorkoutCycle,
    WorkoutCycleFeedback,
    WorkoutCycleWeeklyCheckIn,
    WorkoutExercisePreference,
    WorkoutExerciseReplacement,
    WorkoutExerciseSafetySignal,
)
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise

_NAMESPACE = UUID("8f6ab0b0-85b8-5f2f-99e0-3d1707b4e7ad")
_BASE_TIME = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class CheckInFixture:
    week_number: int
    sessions_completed: int
    perceived_difficulty: WorkoutCycleWeeklyCheckInDifficulty
    recovery_rating: WorkoutCycleWeeklyCheckInRecovery
    has_pain_or_limitation: bool = False


@dataclass(frozen=True)
class FeedbackFixture:
    progressed_muscles: tuple[MuscleGroup, ...] = ()
    lagging_muscles: tuple[MuscleGroup, ...] = ()
    next_training_days: int | None = None
    next_session_duration_minutes: int | None = None
    measurements: dict[str, object] | None = None


@dataclass(frozen=True)
class ReplacementFixture:
    reason: WorkoutExerciseReplacementReason
    scope: WorkoutExerciseReplacementScope
    week_number: int = 1
    preference_type: WorkoutExercisePreferenceType | None = None
    safety_signal: bool = False


@dataclass(frozen=True)
class BodyProgressFixture:
    improved_areas: tuple[BodyArea, ...] = ()
    unchanged_areas: tuple[BodyArea, ...] = ()
    lagging_areas: tuple[BodyArea, ...] = ()


@dataclass(frozen=True)
class CycleFixture:
    duration_weeks: int
    check_ins: tuple[CheckInFixture, ...] = ()
    feedback: FeedbackFixture | None = None
    replacements: tuple[ReplacementFixture, ...] = ()
    body_progress: BodyProgressFixture | None = None


@dataclass(frozen=True)
class ScenarioProfile:
    experience_level: ExperienceLevel
    fitness_goal: FitnessGoal
    training_days_per_week: int
    training_location: TrainingLocation
    home_training_setup: HomeTrainingSetup | None
    session_duration_minutes: int


@dataclass(frozen=True)
class LongitudinalScenario:
    key: str
    profile: ScenarioProfile
    cycles: tuple[CycleFixture, ...]
    defining_signals: frozenset[str]

    def fingerprint(self) -> str:
        payload = _jsonable(asdict(self))
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()


@dataclass(frozen=True)
class MaterializedLongitudinalScenario:
    scenario: LongitudinalScenario
    user: User
    cycles: tuple[WorkoutCycle, ...]

    @property
    def cycle_ids(self) -> tuple[UUID, ...]:
        return tuple(cycle.id for cycle in self.cycles)

    def build_state(self, db: Session):
        return AthleteStateBuilder(db).build(self.user.id)


def materialize_scenario(
    db: Session, scenario: LongitudinalScenario
) -> MaterializedLongitudinalScenario:
    user = User(
        id=_id(scenario.key, "user"),
        email=f"longitudinal-{scenario.key}@example.com",
        password_hash="synthetic-fixture",
    )
    db.add(user)
    db.flush()
    profile = UserProfile(
        user_id=user.id,
        display_name=f"Scenario {scenario.key}",
        birth_date=date(1995, 1, 1),
        sex=Sex.PREFER_NOT_TO_SAY,
        height_cm=175,
        fitness_goal=scenario.profile.fitness_goal,
        experience_level=scenario.profile.experience_level,
        training_days_per_week=scenario.profile.training_days_per_week,
        training_location=scenario.profile.training_location,
        home_training_setup=scenario.profile.home_training_setup,
        session_duration_minutes=scenario.profile.session_duration_minutes,
        plan_duration_weeks=scenario.cycles[-1].duration_weeks,
    )
    db.add(profile)
    db.add(
        BodyMeasurement(
            id=_id(scenario.key, "profile-measurement"),
            user_id=user.id,
            weight_kg=Decimal("75.00"),
            measured_at=_BASE_TIME - timedelta(days=1),
        )
    )
    db.flush()

    catalog = _create_exercise_catalog(db, scenario)

    cycles: list[WorkoutCycle] = []
    for index, cycle_fixture in enumerate(scenario.cycles):
        plan, prescribed, original, alternatives = _create_plan(
            db,
            scenario,
            index=index,
            duration_weeks=cycle_fixture.duration_weeks,
            replacement_count=len(cycle_fixture.replacements),
            original=catalog["chest"],
            alternatives=tuple(catalog.values()),
        )
        started_at = _BASE_TIME + timedelta(days=index * 40)
        is_current = index == len(scenario.cycles) - 1
        if index > 0:
            plan.previous_program_id = cycles[index - 1].workout_plan_id
        plan.activated_at = started_at
        cycle = WorkoutCycle(
            id=_id(scenario.key, f"cycle/{index}"),
            user_id=user.id,
            workout_plan_id=plan.id,
            duration_weeks=cycle_fixture.duration_weeks,
            status=WorkoutCycleStatus.ACTIVE if is_current else WorkoutCycleStatus.COMPLETED,
            started_at=started_at,
            completed_at=None
            if is_current
            else started_at + timedelta(days=cycle_fixture.duration_weeks * 7),
        )
        db.add(cycle)
        db.flush()
        cycles.append(cycle)
        _create_check_ins(db, user.id, cycle, cycle_fixture.check_ins)
        _create_feedback(db, cycle, cycle_fixture.feedback)
        replacements = _create_replacements(
            db,
            user.id,
            cycle,
            prescribed,
            original,
            alternatives,
            cycle_fixture.replacements,
        )
        _create_body_progress(db, user.id, cycle, cycle_fixture.body_progress)
        db.flush()
        _create_preferences_and_safety(db, user.id, cycle, replacements, cycle_fixture.replacements)
    db.flush()
    return MaterializedLongitudinalScenario(scenario=scenario, user=user, cycles=tuple(cycles))


def longitudinal_scenarios() -> tuple[LongitudinalScenario, ...]:
    return (
        LongitudinalScenario(
            key="novice",
            profile=ScenarioProfile(
                ExperienceLevel.BEGINNER,
                FitnessGoal.IMPROVE_FITNESS,
                2,
                TrainingLocation.GYM,
                None,
                45,
            ),
            cycles=(CycleFixture(4), CycleFixture(4)),
            defining_signals=frozenset({"novice", "minimal_history"}),
        ),
        LongitudinalScenario(
            key="intermediate_hypertrophy",
            profile=ScenarioProfile(
                ExperienceLevel.INTERMEDIATE,
                FitnessGoal.BUILD_MUSCLE,
                4,
                TrainingLocation.GYM,
                None,
                60,
            ),
            cycles=(
                CycleFixture(
                    4,
                    check_ins=(
                        CheckInFixture(
                            1,
                            4,
                            WorkoutCycleWeeklyCheckInDifficulty.APPROPRIATE,
                            WorkoutCycleWeeklyCheckInRecovery.GOOD,
                        ),
                    ),
                    feedback=FeedbackFixture(progressed_muscles=(MuscleGroup.CHEST,)),
                ),
                CycleFixture(
                    6,
                    check_ins=(
                        CheckInFixture(
                            1,
                            4,
                            WorkoutCycleWeeklyCheckInDifficulty.APPROPRIATE,
                            WorkoutCycleWeeklyCheckInRecovery.GOOD,
                        ),
                    ),
                ),
            ),
            defining_signals=frozenset({"intermediate", "hypertrophy", "good_recovery"}),
        ),
        LongitudinalScenario(
            key="advanced_strength",
            profile=ScenarioProfile(
                ExperienceLevel.ADVANCED,
                FitnessGoal.BUILD_MUSCLE,
                4,
                TrainingLocation.GYM,
                None,
                90,
            ),
            cycles=(
                CycleFixture(
                    6,
                    check_ins=(
                        CheckInFixture(
                            1,
                            4,
                            WorkoutCycleWeeklyCheckInDifficulty.HARD,
                            WorkoutCycleWeeklyCheckInRecovery.GOOD,
                        ),
                    ),
                ),
                CycleFixture(8),
            ),
            defining_signals=frozenset({"advanced", "strength", "long_cycle"}),
        ),
        LongitudinalScenario(
            key="plateau_lagging_muscle",
            profile=ScenarioProfile(
                ExperienceLevel.INTERMEDIATE,
                FitnessGoal.BUILD_MUSCLE,
                4,
                TrainingLocation.GYM,
                None,
                60,
            ),
            cycles=(
                CycleFixture(
                    6,
                    check_ins=(
                        CheckInFixture(
                            1,
                            4,
                            WorkoutCycleWeeklyCheckInDifficulty.APPROPRIATE,
                            WorkoutCycleWeeklyCheckInRecovery.GOOD,
                        ),
                    ),
                    feedback=FeedbackFixture(lagging_muscles=(MuscleGroup.SHOULDERS,)),
                    body_progress=BodyProgressFixture(lagging_areas=(BodyArea.SHOULDERS,)),
                ),
                CycleFixture(6),
            ),
            defining_signals=frozenset({"plateau", "lagging_muscle", "body_progress"}),
        ),
        LongitudinalScenario(
            key="low_adherence",
            profile=ScenarioProfile(
                ExperienceLevel.INTERMEDIATE,
                FitnessGoal.BUILD_MUSCLE,
                4,
                TrainingLocation.GYM,
                None,
                60,
            ),
            cycles=(
                CycleFixture(
                    4,
                    check_ins=(
                        CheckInFixture(
                            1,
                            0,
                            WorkoutCycleWeeklyCheckInDifficulty.APPROPRIATE,
                            WorkoutCycleWeeklyCheckInRecovery.GOOD,
                        ),
                    ),
                ),
                CycleFixture(4),
            ),
            defining_signals=frozenset({"low_adherence", "zero_completed_sessions"}),
        ),
        LongitudinalScenario(
            key="poor_recovery",
            profile=ScenarioProfile(
                ExperienceLevel.INTERMEDIATE,
                FitnessGoal.BUILD_MUSCLE,
                4,
                TrainingLocation.GYM,
                None,
                60,
            ),
            cycles=(
                CycleFixture(
                    6,
                    check_ins=tuple(
                        CheckInFixture(
                            week,
                            3,
                            WorkoutCycleWeeklyCheckInDifficulty.TOO_HARD,
                            WorkoutCycleWeeklyCheckInRecovery.POOR,
                        )
                        for week in (1, 2, 3)
                    ),
                ),
                CycleFixture(6),
            ),
            defining_signals=frozenset({"poor_recovery", "too_hard", "repeated_signal"}),
        ),
        LongitudinalScenario(
            key="home_equipment_limited",
            profile=ScenarioProfile(
                ExperienceLevel.BEGINNER,
                FitnessGoal.IMPROVE_FITNESS,
                3,
                TrainingLocation.HOME,
                HomeTrainingSetup.BODYWEIGHT_ONLY,
                45,
            ),
            cycles=(CycleFixture(4), CycleFixture(4)),
            defining_signals=frozenset({"home", "bodyweight_only", "equipment_limited"}),
        ),
        LongitudinalScenario(
            key="persistent_discomfort",
            profile=ScenarioProfile(
                ExperienceLevel.INTERMEDIATE,
                FitnessGoal.BUILD_MUSCLE,
                4,
                TrainingLocation.GYM,
                None,
                60,
            ),
            cycles=(
                CycleFixture(
                    4,
                    replacements=(
                        ReplacementFixture(
                            WorkoutExerciseReplacementReason.UNCOMFORTABLE,
                            WorkoutExerciseReplacementScope.PERSISTENT,
                            preference_type=WorkoutExercisePreferenceType.UNCOMFORTABLE,
                        ),
                    ),
                ),
                CycleFixture(6),
            ),
            defining_signals=frozenset({"persistent_discomfort", "preference"}),
        ),
        LongitudinalScenario(
            key="pain_safety",
            profile=ScenarioProfile(
                ExperienceLevel.INTERMEDIATE,
                FitnessGoal.BUILD_MUSCLE,
                4,
                TrainingLocation.GYM,
                None,
                60,
            ),
            cycles=(
                CycleFixture(
                    4,
                    replacements=(
                        ReplacementFixture(
                            WorkoutExerciseReplacementReason.PAIN_OR_DISCOMFORT,
                            WorkoutExerciseReplacementScope.THIS_TIME,
                            week_number=1,
                            safety_signal=True,
                        ),
                        ReplacementFixture(
                            WorkoutExerciseReplacementReason.PAIN_OR_DISCOMFORT,
                            WorkoutExerciseReplacementScope.THIS_TIME,
                            week_number=2,
                            safety_signal=True,
                        ),
                    ),
                ),
                CycleFixture(6),
            ),
            defining_signals=frozenset({"pain", "safety_signal", "repeated_signal"}),
        ),
    )


def _create_plan(
    db: Session,
    scenario: LongitudinalScenario,
    *,
    index: int,
    duration_weeks: int,
    replacement_count: int,
    original: Exercise,
    alternatives: tuple[Exercise, ...],
) -> tuple[WorkoutPlan, Any, Exercise, tuple[Exercise, ...]]:
    plan_alternatives = tuple(item for item in alternatives if item.id != original.id)[
        :replacement_count
    ]
    plan = WorkoutPlan(
        id=_id(scenario.key, f"plan/{index}"),
        user_id=_id(scenario.key, "user"),
        status=WorkoutPlanStatus.ACTIVE
        if index == len(scenario.cycles) - 1
        else WorkoutPlanStatus.SUPERSEDED,
        generation_signature=hashlib.sha256(f"{scenario.key}/plan/{index}".encode()).hexdigest(),
        profile_snapshot={"plan_duration_weeks": duration_weeks},
        provider="longitudinal_fixture",
        model_id="fixture",
        prompt_version="fixture",
        generation_policy_version="fixture",
        candidate_set_hash="f" * 64,
        generation_method="coach_review",
        aggregate_metrics={
            "weekly_direct_sets_by_muscle": {
                muscle.value: float(scenario.profile.training_days_per_week * 2)
                for muscle in _fixture_tracked_muscles()
            },
            "weekly_effective_sets_by_muscle": {
                muscle.value: float(scenario.profile.training_days_per_week * 2)
                for muscle in _fixture_tracked_muscles()
            },
        },
    )
    for day_number in range(1, scenario.profile.training_days_per_week + 1):
        day = WorkoutDay(
            id=_id(scenario.key, f"day/{index}/{day_number}"),
            day_number=day_number,
            title_en=f"Fixture Day {day_number}",
            title_fa=f"روز آزمایشی {day_number}",
            estimated_duration_minutes=30,
        )
        day.exercises.append(
            WorkoutPlanExercise(
                id=_id(scenario.key, f"plan-exercise/{index}/{day_number}"),
                exercise_id=original.id,
                order_index=1,
                sets=3,
                reps_min=8,
                reps_max=12,
                rest_seconds=90,
                rir=2,
                estimated_minutes=10,
                exercise_snapshot={},
                substitution_exercise_ids=[str(item.id) for item in plan_alternatives],
            )
        )
        plan.days.append(day)
    db.add(plan)
    db.flush()
    return plan, plan.days[0].exercises[0], original, plan_alternatives


def _fixture_tracked_muscles() -> tuple[MuscleGroup, ...]:
    return (
        MuscleGroup.CHEST,
        MuscleGroup.BACK,
        MuscleGroup.SHOULDERS,
        MuscleGroup.BICEPS,
        MuscleGroup.TRICEPS,
        MuscleGroup.TRAPS,
        MuscleGroup.FOREARMS,
        MuscleGroup.GLUTES,
        MuscleGroup.QUADRICEPS,
        MuscleGroup.HAMSTRINGS,
        MuscleGroup.CALVES,
        MuscleGroup.ABS,
    )


def _create_check_ins(
    db: Session,
    user_id: UUID,
    cycle: WorkoutCycle,
    check_ins: tuple[CheckInFixture, ...],
) -> None:
    for item in check_ins:
        db.add(
            WorkoutCycleWeeklyCheckIn(
                id=_id(str(user_id), f"check-in/{cycle.id}/{item.week_number}"),
                user_id=user_id,
                cycle_id=cycle.id,
                week_number=item.week_number,
                sessions_completed=item.sessions_completed,
                perceived_difficulty=item.perceived_difficulty,
                recovery_rating=item.recovery_rating,
                has_pain_or_limitation=item.has_pain_or_limitation,
                submitted_at=cycle.started_at + timedelta(days=item.week_number * 7 - 1),
            )
        )


def _create_feedback(
    db: Session,
    cycle: WorkoutCycle,
    feedback: FeedbackFixture | None,
) -> None:
    if feedback is None:
        return
    db.add(
        WorkoutCycleFeedback(
            id=_id(str(cycle.id), "feedback"),
            cycle_id=cycle.id,
            measurements=feedback.measurements or {},
            strength_progress=WorkoutCycleFeedbackProgress.IMPROVED
            if feedback.progressed_muscles
            else None,
            progressed_muscles=[muscle.value for muscle in feedback.progressed_muscles],
            lagging_muscles=[muscle.value for muscle in feedback.lagging_muscles],
            next_training_days=feedback.next_training_days,
            next_session_duration_minutes=feedback.next_session_duration_minutes,
            submitted_at=cycle.started_at + timedelta(days=cycle.duration_weeks * 7),
        )
    )


def _create_replacements(
    db: Session,
    user_id: UUID,
    cycle: WorkoutCycle,
    prescribed: Any,
    original: Exercise,
    alternatives: tuple[Exercise, ...],
    specs: tuple[ReplacementFixture, ...],
) -> tuple[WorkoutExerciseReplacement, ...]:
    replacements = []
    for index, (spec, alternative) in enumerate(zip(specs, alternatives, strict=True)):
        replacement = WorkoutExerciseReplacement(
            id=_id(str(cycle.id), f"replacement/{index}"),
            user_id=user_id,
            cycle_id=cycle.id,
            workout_plan_exercise_id=prescribed.id,
            original_exercise_id=original.id,
            replacement_exercise_id=alternative.id,
            reason=spec.reason,
            scope=spec.scope,
            week_number=spec.week_number,
        )
        db.add(replacement)
        replacements.append(replacement)
    db.flush()
    return tuple(replacements)


def _create_preferences_and_safety(
    db: Session,
    user_id: UUID,
    cycle: WorkoutCycle,
    replacements: tuple[WorkoutExerciseReplacement, ...],
    specs: tuple[ReplacementFixture, ...],
) -> None:
    for replacement, spec in zip(replacements, specs, strict=True):
        if spec.preference_type is not None:
            db.add(
                WorkoutExercisePreference(
                    id=_id(str(replacement.id), "preference"),
                    user_id=user_id,
                    exercise_id=replacement.original_exercise_id,
                    preference_type=spec.preference_type,
                    source_replacement_id=replacement.id,
                )
            )
        if spec.safety_signal:
            db.add(
                WorkoutExerciseSafetySignal(
                    id=_id(str(replacement.id), "safety"),
                    user_id=user_id,
                    cycle_id=cycle.id,
                    workout_plan_exercise_id=replacement.workout_plan_exercise_id,
                    original_exercise_id=replacement.original_exercise_id,
                    replacement_exercise_id=replacement.replacement_exercise_id,
                    signal_type=WorkoutExerciseSafetySignalType.PAIN_OR_DISCOMFORT,
                    week_number=replacement.week_number,
                    source_replacement_id=replacement.id,
                )
            )


def _create_body_progress(
    db: Session,
    user_id: UUID,
    cycle: WorkoutCycle,
    body_progress: BodyProgressFixture | None,
) -> None:
    if body_progress is None:
        return
    start_measurement = BodyMeasurement(
        id=_id(str(cycle.id), "start-measurement"),
        user_id=user_id,
        cycle_id=cycle.id,
        weight_kg=Decimal("80.00"),
        measured_at=cycle.started_at,
    )
    end_measurement = BodyMeasurement(
        id=_id(str(cycle.id), "end-measurement"),
        user_id=user_id,
        cycle_id=cycle.id,
        weight_kg=Decimal("78.00"),
        measured_at=cycle.started_at + timedelta(days=cycle.duration_weeks * 7),
    )
    db.add_all([start_measurement, end_measurement])
    db.flush()
    comparison = WorkoutCycleBodyProgressComparison(
        id=_id(str(cycle.id), "body-comparison"),
        user_id=user_id,
        cycle_id=cycle.id,
        start_measurement_id=start_measurement.id,
        end_measurement_id=end_measurement.id,
        comparison_result={
            "measurement": {
                "status": "complete",
                "start_measurement_id": str(start_measurement.id),
                "end_measurement_id": str(end_measurement.id),
                "start_measured_at": cycle.started_at.isoformat(),
                "end_measured_at": (
                    cycle.started_at + timedelta(days=cycle.duration_weeks * 7)
                ).isoformat(),
                "metrics": {"weight_kg": {"start": 80.0, "end": 78.0, "delta": -2.0}},
            },
            "body_analysis": {
                "status": "complete",
                "start_session_id": None,
                "end_session_id": None,
                "start_analysis_id": None,
                "end_analysis_id": None,
                "start_result_version_id": None,
                "end_result_version_id": None,
                "start_created_at": None,
                "end_created_at": None,
                "comparison": None,
                "improved_areas": [area.value for area in body_progress.improved_areas],
                "unchanged_areas": [area.value for area in body_progress.unchanged_areas],
                "lagging_areas": [area.value for area in body_progress.lagging_areas],
            },
            "missing_data": [],
            "provenance": {
                "cycle_id": str(cycle.id),
                "cycle_started_at": cycle.started_at.isoformat(),
                "cycle_completed_at": (
                    cycle.completed_at.isoformat() if cycle.completed_at else None
                ),
            },
        },
    )
    db.add(comparison)


def _create_exercise_catalog(db: Session, scenario: LongitudinalScenario) -> dict[str, Exercise]:
    m = MuscleGroup
    p = MovementPattern
    u = BodyRegion.UPPER_BODY
    lower = BodyRegion.LOWER_BODY
    c = BodyRegion.CORE
    definitions = (
        ("chest", m.CHEST, p.HORIZONTAL_PUSH, u),
        ("dumbbell_chest", m.CHEST, p.HORIZONTAL_PUSH, u),
        ("chest_alt", m.CHEST, p.HORIZONTAL_PUSH, u),
        ("chest_extra", m.CHEST, p.HORIZONTAL_PUSH, u),
        ("back", m.BACK, p.HORIZONTAL_PULL, u),
        ("back_alt", m.BACK, p.HORIZONTAL_PULL, u),
        ("back_tertiary", m.BACK, p.HORIZONTAL_PULL, u),
        ("back_vertical", m.BACK, p.VERTICAL_PULL, u),
        ("back_vertical_alt", m.BACK, p.VERTICAL_PULL, u),
        ("shoulders", m.SHOULDERS, p.VERTICAL_PUSH, u),
        ("shoulders_alt", m.SHOULDERS, p.VERTICAL_PUSH, u),
        ("shoulder_abduction", m.SHOULDERS, p.SHOULDER_ABDUCTION, u),
        ("shoulder_abduction_alt", m.SHOULDERS, p.SHOULDER_ABDUCTION, u),
        ("shoulders_row", m.SHOULDERS, p.HORIZONTAL_PULL, u),
        ("traps", m.TRAPS, p.SHRUG, u),
        ("traps_alt", m.TRAPS, p.SHRUG, u),
        ("biceps", m.BICEPS, p.ELBOW_FLEXION, u),
        ("biceps_alt", m.BICEPS, p.ELBOW_FLEXION, u),
        ("biceps_tertiary", m.BICEPS, p.ELBOW_FLEXION, u),
        ("triceps", m.TRICEPS, p.ELBOW_EXTENSION, u),
        ("triceps_alt", m.TRICEPS, p.ELBOW_EXTENSION, u),
        ("triceps_tertiary", m.TRICEPS, p.ELBOW_EXTENSION, u),
        ("quadriceps", m.QUADRICEPS, p.SQUAT, lower),
        ("quadriceps_extension", m.QUADRICEPS, p.KNEE_EXTENSION, lower),
        ("hamstrings", m.HAMSTRINGS, p.HIP_HINGE, lower),
        ("hamstrings_curl", m.HAMSTRINGS, p.KNEE_FLEXION, lower),
        ("glutes", m.GLUTES, p.HIP_EXTENSION, lower),
        ("abs", m.ABS, p.CORE_ANTI_EXTENSION, c),
        ("abs_rotation", m.ABS, p.CORE_ANTI_ROTATION, c),
        ("calves", m.CALVES, p.CALF_RAISE, lower),
        ("calves_alt", m.CALVES, p.CALF_RAISE, lower),
    )
    return {
        role: _exercise(
            db,
            scenario.key,
            role,
            muscle=muscle,
            pattern=pattern,
            body_region=body_region,
            equipment=(
                (Equipment.DUMBBELL,) if role == "dumbbell_chest" else (Equipment.BODYWEIGHT,)
            ),
        )
        for role, muscle, pattern, body_region in definitions
    }


def _exercise(
    db: Session,
    scenario_key: str,
    role: str,
    *,
    muscle: MuscleGroup,
    pattern: MovementPattern,
    body_region: BodyRegion,
    equipment: tuple[Equipment, ...],
) -> Exercise:
    focuses = FOCUSES_BY_MUSCLE[muscle]
    slug_key = scenario_key.replace("_", "-")
    role_slug = role.replace("_", "-")
    exercise = Exercise(
        id=_id(scenario_key, f"exercise/{role}"),
        slug=f"longitudinal-{slug_key}-{role_slug}",
        name_en=f"Longitudinal {scenario_key} {role}",
        name_fa=f"حرکت طولی {scenario_key} {role}",
        body_region=body_region,
        primary_muscle=muscle,
        muscle_focus=focuses[0] if focuses else None,
        difficulty=Difficulty.BEGINNER,
        movement_pattern=pattern,
        exercise_type=ExerciseType.COMPOUND,
        instructions_en=["Set up.", "Move safely.", "Finish."],
        instructions_fa=["آماده شو.", "ایمن حرکت کن.", "تمام کن."],
        safety_notes_en=["Synthetic fixture."],
        safety_notes_fa=["دادهٔ آزمایشی."],
        media_path="/fixtures/placeholder.svg",
        media_type=MediaType.PLACEHOLDER,
        is_active=True,
        is_programmable=True,
        needs_review=False,
    )
    exercise.equipment_items.extend(ExerciseEquipment(equipment=item) for item in equipment)
    db.add(exercise)
    db.flush()
    return exercise


def _id(scenario_key: str, path: str) -> UUID:
    return uuid5(_NAMESPACE, f"{scenario_key}/{path}")


def _jsonable(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {
            str(key): _jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (set, frozenset)):
        return [_jsonable(item) for item in sorted(value, key=repr)]
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value
