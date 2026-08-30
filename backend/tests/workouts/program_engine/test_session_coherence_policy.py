from __future__ import annotations

from types import SimpleNamespace

from app.exercises.enums import ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine.focus_topology import FocusAffinity, priority_affinity
from app.workouts.program_engine.session_coherence import (
    SessionCoherence,
    SessionMuscleRole,
)
from app.workouts.program_engine.slot_compatibility import (
    evaluate_candidate_slot_compatibility,
    focus_scope,
)
from scripts.audit_session_coherence import summarize_coherence


def test_dynamic_focus_exposes_exact_roles_without_secondary_scope() -> None:
    policy = SessionCoherence.from_dynamic_focus("chest_triceps")

    assert policy.allowed_direct_muscles == frozenset({MuscleGroup.CHEST, MuscleGroup.TRICEPS})
    assert policy.role_for(MuscleGroup.CHEST) is SessionMuscleRole.PRIMARY
    assert policy.role_for(MuscleGroup.TRICEPS) is SessionMuscleRole.SECONDARY
    assert policy.role_for(MuscleGroup.SHOULDERS) is SessionMuscleRole.DISALLOWED


def test_template_targets_are_exact_even_when_structure_is_broad() -> None:
    day = SimpleNamespace(
        focus=(MuscleGroup.CHEST,),
        structure_focus="chest_triceps",
    )

    policy = SessionCoherence.from_template_reference_day(day)

    assert policy.allowed_direct_muscles == frozenset({MuscleGroup.CHEST})
    assert policy.role_for(MuscleGroup.TRICEPS) is SessionMuscleRole.DISALLOWED


def test_template_only_minor_group_is_accessory_not_primary() -> None:
    day = SimpleNamespace(
        focus=(MuscleGroup.SHOULDERS, MuscleGroup.TRAPS, MuscleGroup.CALVES),
        structure_focus="shoulders",
    )

    policy = SessionCoherence.from_template_reference_day(day)

    assert policy.role_for(MuscleGroup.SHOULDERS) is SessionMuscleRole.PRIMARY
    assert policy.role_for(MuscleGroup.TRAPS) is SessionMuscleRole.SECONDARY
    assert policy.role_for(MuscleGroup.CALVES) is SessionMuscleRole.ACCESSORY


def test_dedicated_primary_role_outranks_existing_grouped_exposure() -> None:
    dedicated = SessionCoherence.from_dynamic_focus("shoulders_traps")
    grouped = SessionCoherence.from_dynamic_focus("push")

    assert dedicated.placement_rank(
        MuscleGroup.SHOULDERS,
        existing_exposure=False,
    ) < grouped.placement_rank(
        MuscleGroup.SHOULDERS,
        existing_exposure=True,
    )


def test_out_of_scope_primary_is_rejected_even_when_secondary_matches() -> None:
    candidate = SimpleNamespace(
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        primary_muscle=MuscleGroup.SHOULDERS,
        secondary_muscles=(MuscleGroup.CHEST,),
        exercise_type=ExerciseType.COMPOUND,
        labels=(),
    )

    result = evaluate_candidate_slot_compatibility(
        candidate,
        allowed_patterns=frozenset({MovementPattern.HORIZONTAL_PUSH}),
        day_focus="chest_triceps",
    )

    assert not result.compatible
    assert result.reason_codes == ("SLOT_SEMANTIC_MISMATCH",)


def test_focus_scope_uses_the_same_exact_muscle_scope_as_coherence() -> None:
    _patterns, muscles = focus_scope("push")

    assert muscles == SessionCoherence.from_dynamic_focus("push").allowed_direct_muscles


def test_priority_affinity_delegates_to_central_hierarchy() -> None:
    assert priority_affinity("chest_triceps", MuscleGroup.CHEST) is FocusAffinity.DEDICATED
    assert priority_affinity("chest_triceps", MuscleGroup.TRICEPS) is FocusAffinity.GROUPED
    assert priority_affinity("upper_a", MuscleGroup.CHEST) is FocusAffinity.NONE
    assert priority_affinity("upper_a", MuscleGroup.FOREARMS) is FocusAffinity.NONE


def test_priority_day_key_prefers_existing_intended_exposure() -> None:
    from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy

    policy = object.__new__(PriorityAllocationPolicy)
    object.__setattr__(policy, "priorities", (MuscleGroup.CHEST,))
    object.__setattr__(policy, "explicit_priorities", (MuscleGroup.CHEST,))
    object.__setattr__(policy, "clear_lag_priorities", ())
    object.__setattr__(policy, "mild_lag_priorities", ())
    object.__setattr__(policy, "supplemental_priorities", ())
    object.__setattr__(policy, "supplemental_body_priorities", ())
    object.__setattr__(policy, "preferred_frequency", 2)
    object.__setattr__(policy, "recovery_limited", False)
    object.__setattr__(policy, "minimum_recovery_gap_days", 2)
    days = (
        SimpleNamespace(
            focus="chest_triceps",
            exercises=(SimpleNamespace(primary_muscle=MuscleGroup.CHEST),),
            weekday=0,
        ),
        SimpleNamespace(
            focus="chest_triceps",
            exercises=(),
            weekday=3,
        ),
        SimpleNamespace(
            focus="lower",
            exercises=(),
            weekday=5,
        ),
    )

    assert policy.day_priority_key(days, MuscleGroup.CHEST, 0)[0] < policy.day_priority_key(
        days, MuscleGroup.CHEST, 1
    )[0]
    assert policy.day_priority_key(days, MuscleGroup.CHEST, 2)[0] > policy.day_priority_key(
        days, MuscleGroup.CHEST, 1
    )[0]


def test_session_coherence_trace_is_compact_and_deterministic() -> None:
    policy = SessionCoherence.from_dynamic_focus("lower")
    trace = policy.trace()

    assert trace["focus"] == "lower"
    assert trace["allowed_direct_muscles"] == [
        MuscleGroup.ABS.value,
        MuscleGroup.CALVES.value,
        MuscleGroup.GLUTES.value,
        MuscleGroup.HAMSTRINGS.value,
        MuscleGroup.QUADRICEPS.value,
    ]
    assert set(trace) == {
        "focus",
        "source",
        "allowed_direct_muscles",
        "primary_muscles",
        "secondary_muscles",
        "accessory_muscles",
    }


def test_audit_summary_uses_canonical_out_of_scope_metric_key() -> None:
    summary = summarize_coherence(
        [
            {
                "status": "SUCCESS",
                "session_coherence": {
                    "orphan_direct_exposure_count": 1,
                    "post_construction_out_of_scope_direct_muscle_additions": 2,
                },
            }
        ]
    )

    assert summary["orphan_direct_exposure_count"] == 1
    assert summary["post_construction_out_of_scope_direct_additions"] == 2
