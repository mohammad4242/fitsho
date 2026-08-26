from dataclasses import replace
from uuid import UUID

import pytest

from app.exercises.enums import Equipment, MovementPattern, MuscleGroup
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)
from app.workouts.program_engine.template_sessions import (
    TemplateConstructionError,
    build_template_sessions,
)
from tests.workouts.program_engine.golden_fixtures import exercise, request

TEST_RULESET = replace(
    RULESET,
    minimum_exercises_per_session=1,
    preferred_main_exercises_per_session=1,
)


def _slot(
    target: ExerciseCandidate,
    *,
    priority: str = "core",
) -> TemplateReferenceSlot:
    return TemplateReferenceSlot(
        exercise_id=target.id,
        exercise_slug_hint=target.name,
        target_muscles=(MuscleGroup.CHEST,),
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        intensity_method="rest_pause",
        adaptation_priority=priority,
        superset_group="push-a",
        sets=4,
        rep_min=8,
        rep_max=10,
        target_rir=1,
        rest_seconds=90,
    )


def _template(*slots: TemplateReferenceSlot) -> TemplateReference:
    return TemplateReference(
        slug="template-substitution-closeout",
        days_per_week=1,
        supported_levels=("beginner",),
        fitness_goal="general_fitness",
        focus_tags=("balanced",),
        intensity_methods=("rest_pause",),
        days=(
            TemplateReferenceDay(
                day_number=1,
                title="Push",
                focus=(MuscleGroup.CHEST,),
                slots=slots,
                structure_focus="push",
            ),
        ),
    )


def _normalized_request():
    return normalize_request(
        request(
            available_training_days=1,
            available_equipment=[Equipment.BODYWEIGHT],
        ),
        TEST_RULESET,
    )


def _replacement_catalog() -> tuple[
    ExerciseCandidate,
    ExerciseCandidate,
    ExerciseCandidate,
]:
    lowest_uuid = replace(
        exercise("generic-press", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        id=UUID(int=1),
        substitution_group="generic-press",
    )
    semantic_best = replace(
        exercise("curated-press", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        id=UUID(int=2),
        substitution_group="template-press",
    )
    unavailable = replace(
        exercise("barbell-template-press", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        id=UUID(int=100),
        equipment=frozenset({Equipment.BARBELL}),
        substitution_group="template-press",
        curated_alternative_ids=(semantic_best.id,),
    )
    return unavailable, lowest_uuid, semantic_best


def test_unavailable_template_exercise_uses_semantic_ranker_deterministically() -> None:
    target, lowest_uuid, semantic_best = _replacement_catalog()
    source = _normalized_request()
    catalog = (target, lowest_uuid, semantic_best)
    eligible = filter_eligible_exercises(source, catalog).eligible

    forward = build_template_sessions(
        source,
        _template(_slot(target)),
        eligible,
        TEST_RULESET,
        exercise_catalog=catalog,
    )
    reverse = build_template_sessions(
        source,
        _template(_slot(target)),
        tuple(reversed(eligible)),
        TEST_RULESET,
        exercise_catalog=tuple(reversed(catalog)),
    )

    assert forward.resolutions[0].selected_exercise_id == semantic_best.id
    assert forward.resolutions[0].selected_exercise_id != lowest_uuid.id
    assert reverse.resolutions[0].selected_exercise_id == semantic_best.id
    assert forward.drafts[0].template_target_muscles == (MuscleGroup.CHEST,)
    assert forward.drafts[0].template_structure_focus == "push"


def test_reused_template_exercise_uses_curated_same_group_candidate() -> None:
    target, lowest_uuid, semantic_best = _replacement_catalog()
    target = replace(
        target,
        equipment=frozenset({Equipment.BODYWEIGHT}),
    )
    source = _normalized_request()

    build = build_template_sessions(
        source,
        _template(_slot(target), _slot(target)),
        (target, lowest_uuid, semantic_best),
        TEST_RULESET,
        exercise_catalog=(target, lowest_uuid, semantic_best),
    )

    assert [item.id for item in build.drafts[0].exercises] == [target.id, semantic_best.id]


def test_template_recovery_never_selects_hard_ineligible_candidate() -> None:
    target, _lowest_uuid, semantic_best = _replacement_catalog()
    unsafe = replace(
        exercise("unsafe-curated-press", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        id=UUID(int=1),
        needs_review=True,
        substitution_group="template-press",
    )
    target = replace(target, curated_alternative_ids=(unsafe.id, semantic_best.id))

    build = build_template_sessions(
        _normalized_request(),
        _template(_slot(target)),
        (unsafe, semantic_best),
        TEST_RULESET,
        exercise_catalog=(target, unsafe, semantic_best),
    )

    assert build.resolutions[0].selected_exercise_id == semantic_best.id
    assert unsafe.id not in {item.id for item in build.drafts[0].exercises}


def test_core_template_slot_preserves_failure_when_no_valid_replacement_exists() -> None:
    target, _lowest_uuid, _semantic_best = _replacement_catalog()

    with pytest.raises(TemplateConstructionError) as exc_info:
        build_template_sessions(
            _normalized_request(),
            _template(_slot(target)),
            (),
            TEST_RULESET,
            exercise_catalog=(target,),
        )

    assert exc_info.value.reason_codes == (
        "TEMPLATE_CORE_SLOT_UNRESOLVABLE",
        "TEMPLATE_DAY:1",
        "TEMPLATE_PATTERN:horizontal_push",
    )


def test_optional_template_slot_preserves_omission_when_no_replacement_exists() -> None:
    target, _lowest_uuid, _semantic_best = _replacement_catalog()
    core = replace(
        exercise("available-core-press", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        id=UUID(int=200),
    )

    build = build_template_sessions(
        _normalized_request(),
        _template(_slot(core), _slot(target, priority="optional")),
        (core,),
        TEST_RULESET,
        exercise_catalog=(core, target),
    )

    assert [item.id for item in build.drafts[0].exercises] == [core.id]
    assert "TEMPLATE_OPTIONAL_SLOT_OMITTED_UNAVAILABLE" in build.reason_codes
    assert build.drafts[0].template_structure_focus == "push"
