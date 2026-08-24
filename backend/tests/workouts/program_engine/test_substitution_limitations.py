from dataclasses import replace
from uuid import UUID

import pytest

from app.exercises.enums import (
    Equipment,
    ExerciseCautionTag,
    MovementPattern,
    MuscleGroup,
)
from app.training_templates.tags import TemplateFocusTag
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.enums import (
    BalanceAbility,
    LoadLimit,
    SplitType,
    StabilityDemand,
)
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    SessionDraft,
    SplitPlan,
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
    WeeklyVolumePlan,
)
from app.workouts.program_engine.session_builder import build_sessions
from app.workouts.program_engine.substitution_engine import (
    SubstitutionContext,
    rank_substitutions,
)
from app.workouts.program_engine.substitution_policy import SubstitutionCause
from app.workouts.program_engine.template_sessions import build_template_sessions
from tests.workouts.program_engine.golden_fixtures import exercise, request


def _candidate(
    slug: str,
    pattern: MovementPattern,
    *,
    equipment: frozenset[Equipment] = frozenset({Equipment.BODYWEIGHT}),
    caution_tags: frozenset[ExerciseCautionTag] = frozenset(),
    axial_loading_level: LoadLimit = LoadLimit.LOW,
    stability_demand: StabilityDemand = StabilityDemand.LOW,
    range_of_motion_profile: frozenset[str] = frozenset({"short"}),
    muscle: MuscleGroup = MuscleGroup.QUADRICEPS,
) -> ExerciseCandidate:
    return replace(
        exercise(slug, pattern, muscle, equipment=equipment),
        caution_tags=caution_tags,
        axial_loading_level=axial_loading_level,
        stability_demand=stability_demand,
        range_of_motion_profile=range_of_motion_profile,
    )


def _rank_case(name: str, target, unsafe, safe, **request_overrides: object):
    return pytest.param(
        name,
        target,
        unsafe,
        safe,
        request_overrides,
        id=name,
    )


@pytest.mark.parametrize(
    ("name", "target", "unsafe", "safe", "request_overrides"),
    (
        _rank_case(
            "lower-back-axial-load",
            _candidate(
                "axial-target",
                MovementPattern.SQUAT,
                caution_tags=frozenset({ExerciseCautionTag.LOWER_BACK_LOADING}),
                axial_loading_level=LoadLimit.HIGH,
            ),
            _candidate(
                "axial-unsafe",
                MovementPattern.SQUAT,
                caution_tags=frozenset({ExerciseCautionTag.LOWER_BACK_LOADING}),
                axial_loading_level=LoadLimit.HIGH,
            ),
            _candidate("axial-safe", MovementPattern.SQUAT, axial_loading_level=LoadLimit.LOW),
            axial_load_limit=LoadLimit.LOW,
            blocked_caution_tags=frozenset({ExerciseCautionTag.LOWER_BACK_LOADING}),
        ),
        _rank_case(
            "knee-deep-flexion",
            _candidate(
                "knee-target",
                MovementPattern.KNEE_EXTENSION,
                caution_tags=frozenset({ExerciseCautionTag.DEEP_KNEE_FLEXION}),
            ),
            _candidate(
                "knee-unsafe",
                MovementPattern.KNEE_EXTENSION,
                caution_tags=frozenset({ExerciseCautionTag.DEEP_KNEE_FLEXION}),
            ),
            _candidate("knee-safe", MovementPattern.KNEE_EXTENSION),
            blocked_caution_tags=frozenset({ExerciseCautionTag.DEEP_KNEE_FLEXION}),
        ),
        _rank_case(
            "shoulder-overhead-no-filler",
            _candidate(
                "overhead-target",
                MovementPattern.VERTICAL_PUSH,
                muscle=MuscleGroup.SHOULDERS,
            ),
            _candidate(
                "overhead-unsafe",
                MovementPattern.VERTICAL_PUSH,
                muscle=MuscleGroup.SHOULDERS,
            ),
            _candidate(
                "overhead-unrelated",
                MovementPattern.HORIZONTAL_PUSH,
                muscle=MuscleGroup.SHOULDERS,
            ),
            overhead_limit=LoadLimit.NONE,
        ),
        _rank_case(
            "wrist-loading",
            _candidate("wrist-target", MovementPattern.HORIZONTAL_PUSH, muscle=MuscleGroup.CHEST),
            _candidate("wrist-unsafe", MovementPattern.HORIZONTAL_PUSH, muscle=MuscleGroup.CHEST),
            _candidate(
                "wrist-safe",
                MovementPattern.HORIZONTAL_PUSH,
                equipment=frozenset({Equipment.DUMBBELL}),
                muscle=MuscleGroup.CHEST,
            ),
            blocked_caution_tags=frozenset({ExerciseCautionTag.WRIST_LOADING}),
        ),
        _rank_case(
            "balance",
            _candidate(
                "balance-target", MovementPattern.SQUAT, stability_demand=StabilityDemand.HIGH
            ),
            _candidate(
                "balance-unsafe", MovementPattern.SQUAT, stability_demand=StabilityDemand.HIGH
            ),
            _candidate("balance-safe", MovementPattern.SQUAT, stability_demand=StabilityDemand.LOW),
            balance_requirement=BalanceAbility.LIMITED,
        ),
        _rank_case(
            "range-of-motion",
            _candidate(
                "rom-target",
                MovementPattern.KNEE_EXTENSION,
                range_of_motion_profile=frozenset({"deep"}),
            ),
            _candidate(
                "rom-unsafe",
                MovementPattern.KNEE_EXTENSION,
                range_of_motion_profile=frozenset({"deep"}),
            ),
            _candidate("rom-safe", MovementPattern.KNEE_EXTENSION),
            allowed_range_of_motion=frozenset({"short"}),
        ),
        _rank_case(
            "simultaneous-constraints",
            _candidate(
                "multi-target",
                MovementPattern.HORIZONTAL_PUSH,
                muscle=MuscleGroup.CHEST,
                axial_loading_level=LoadLimit.HIGH,
                stability_demand=StabilityDemand.HIGH,
                range_of_motion_profile=frozenset({"deep"}),
            ),
            _candidate(
                "multi-unsafe",
                MovementPattern.HORIZONTAL_PUSH,
                muscle=MuscleGroup.CHEST,
                axial_loading_level=LoadLimit.HIGH,
                stability_demand=StabilityDemand.HIGH,
                range_of_motion_profile=frozenset({"deep"}),
            ),
            _candidate(
                "multi-safe",
                MovementPattern.HORIZONTAL_PUSH,
                equipment=frozenset({Equipment.DUMBBELL}),
                muscle=MuscleGroup.CHEST,
            ),
            blocked_caution_tags=frozenset({ExerciseCautionTag.WRIST_LOADING}),
            axial_load_limit=LoadLimit.LOW,
            balance_requirement=BalanceAbility.LIMITED,
            allowed_range_of_motion=frozenset({"short"}),
        ),
    ),
)
def test_limitation_matrix_never_surfaces_unsafe_replacements(
    name: str,
    target,
    unsafe,
    safe,
    request_overrides: dict[str, object],
) -> None:
    source = normalize_request(request(**request_overrides))
    decision = rank_substitutions(
        source,
        target,
        (unsafe, safe),
        SubstitutionContext(
            cause=SubstitutionCause.SAFETY,
            allowed_patterns=frozenset({target.movement_pattern}),
            target_muscles=frozenset({target.primary_muscle}),
        ),
        ruleset=RULESET,
    )

    option_ids = decision.exercise_ids
    assert unsafe.id not in option_ids, name
    if name == "shoulder-overhead-no-filler":
        assert decision.options == ()
    else:
        assert safe.id in option_ids


def _simultaneous_request():
    return normalize_request(
        request(
            available_equipment=frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL}),
            blocked_caution_tags=frozenset({ExerciseCautionTag.WRIST_LOADING}),
            axial_load_limit=LoadLimit.LOW,
            balance_requirement=BalanceAbility.LIMITED,
            allowed_range_of_motion=frozenset({"short"}),
            available_training_days=1,
        )
    )


def _simultaneous_catalog():
    target = _candidate(
        "builder-target",
        MovementPattern.HORIZONTAL_PUSH,
        muscle=MuscleGroup.CHEST,
        axial_loading_level=LoadLimit.HIGH,
        stability_demand=StabilityDemand.HIGH,
        range_of_motion_profile=frozenset({"deep"}),
    )
    unsafe = _candidate(
        "builder-unsafe",
        MovementPattern.HORIZONTAL_PUSH,
        muscle=MuscleGroup.CHEST,
        axial_loading_level=LoadLimit.HIGH,
        stability_demand=StabilityDemand.HIGH,
        range_of_motion_profile=frozenset({"deep"}),
    )
    safe = _candidate(
        "builder-safe",
        MovementPattern.HORIZONTAL_PUSH,
        equipment=frozenset({Equipment.DUMBBELL}),
        muscle=MuscleGroup.CHEST,
    )
    safe_pull = _candidate(
        "builder-safe-pull",
        MovementPattern.HORIZONTAL_PULL,
        muscle=MuscleGroup.BACK,
    )
    safe_knee = _candidate(
        "builder-safe-knee",
        MovementPattern.KNEE_EXTENSION,
        muscle=MuscleGroup.QUADRICEPS,
    )
    safe_hinge = _candidate(
        "builder-safe-hinge",
        MovementPattern.HIP_HINGE,
        muscle=MuscleGroup.HAMSTRINGS,
    )
    safe_shoulder = _candidate(
        "builder-safe-shoulder",
        MovementPattern.SHOULDER_ABDUCTION,
        muscle=MuscleGroup.SHOULDERS,
    )
    return (
        target,
        unsafe,
        safe,
        (
            target,
            unsafe,
            safe,
            safe_pull,
            safe_knee,
            safe_hinge,
            safe_shoulder,
        ),
    )


def _assert_builder_substitutions_are_safe(
    drafts: tuple[SessionDraft, ...], unsafe_id: UUID
) -> None:
    assert drafts
    for draft in drafts:
        assert all(unsafe_id not in alternatives for alternatives in draft.substitutions.values())


def test_dynamic_builder_keeps_simultaneous_constraint_replacements_safe() -> None:
    source = _simultaneous_request()
    target, unsafe, safe, catalog = _simultaneous_catalog()
    eligible = filter_eligible_exercises(source, catalog).eligible
    drafts = build_sessions(
        source,
        SplitPlan(SplitType.FULL_BODY, ("full_body",), (0,), 0, ()),
        WeeklyVolumePlan((), ()),
        eligible,
        RULESET,
    )

    _assert_builder_substitutions_are_safe(drafts, unsafe.id)
    assert all(target.id not in {item.id for item in draft.exercises} for draft in drafts)
    assert any(safe.id in {item.id for item in draft.exercises} for draft in drafts)


def test_template_builder_keeps_simultaneous_constraint_replacements_safe() -> None:
    source = _simultaneous_request()
    target, unsafe, safe, catalog = _simultaneous_catalog()
    eligible = filter_eligible_exercises(source, catalog).eligible
    patterns = (
        (MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        (MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        (MovementPattern.KNEE_EXTENSION, MuscleGroup.QUADRICEPS),
        (MovementPattern.HIP_HINGE, MuscleGroup.HAMSTRINGS),
        (MovementPattern.SHOULDER_ABDUCTION, MuscleGroup.SHOULDERS),
    )
    day = TemplateReferenceDay(
        day_number=1,
        title="Safe full body",
        focus=(MuscleGroup.CHEST, MuscleGroup.BACK, MuscleGroup.QUADRICEPS),
        slots=tuple(
            TemplateReferenceSlot(
                exercise_id=target.id if pattern is patterns[0][0] else None,
                exercise_slug_hint=pattern.value,
                target_muscles=(muscle,),
                movement_pattern=pattern,
                intensity_method="standard",
                adaptation_priority="core",
                superset_group=None,
                sets=3,
                rep_min=8,
                rep_max=12,
                target_rir=2,
                rest_seconds=90,
            )
            for pattern, muscle in patterns
        ),
    )
    template = TemplateReference(
        slug="safe-full-body",
        days_per_week=1,
        training_level="beginner",
        fitness_goal="general_fitness",
        focus_tags=(TemplateFocusTag.FULL_BODY,),
        intensity_methods=("standard",),
        days=(day,),
    )
    build = build_template_sessions(source, template, eligible, RULESET)

    _assert_builder_substitutions_are_safe(build.drafts, unsafe.id)
    assert all(target.id not in {item.id for item in draft.exercises} for draft in build.drafts)
    assert any(safe.id in {item.id for item in draft.exercises} for draft in build.drafts)
