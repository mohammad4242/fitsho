"""Canonical direct-muscle scope and hierarchy for a workout session.

The policy is deliberately independent of the construction pipeline.  Callers can use it
while selecting candidates, placing volume, ordering a session, or auditing a finished day.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.supplemental_policy import is_core_or_supplemental_exercise

if TYPE_CHECKING:
    from app.workouts.program_engine.schemas import SessionDraft, TemplateReferenceDay, WorkoutDay


class SessionMuscleRole(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    ACCESSORY = "accessory"
    DISALLOWED = "disallowed"


@dataclass(frozen=True)
class SessionCoherenceDecision:
    stage: str
    muscle_requested: MuscleGroup
    candidate_day: int
    candidate_day_role: SessionMuscleRole
    status: str
    reason: str

    def as_trace(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "muscle_requested": self.muscle_requested.value,
            "candidate_day": self.candidate_day,
            "candidate_day_role": self.candidate_day_role.value,
            "status": self.status,
            "reason": self.reason,
        }


def record_coherence_decision(
    decisions: list[SessionCoherenceDecision] | None,
    decision: SessionCoherenceDecision,
) -> None:
    if decisions is not None and decision not in decisions:
        decisions.append(decision)


def ordered_coherence_decisions(
    decisions: Iterable[SessionCoherenceDecision],
) -> tuple[SessionCoherenceDecision, ...]:
    """Return deterministic trace order independent of candidate/catalog iteration."""
    return tuple(
        sorted(
            set(decisions),
            key=lambda decision: (
                decision.stage,
                decision.candidate_day,
                decision.muscle_requested.value,
                decision.candidate_day_role.value,
                decision.status,
                decision.reason,
            ),
        )
    )


# Ordered groups are the source of truth for session ordering.  The first group receives
# direct primary work before the later groups; groups inside a tier are intentionally broad.
_FOCUS_HIERARCHY: dict[str, tuple[tuple[MuscleGroup, ...], ...]] = {
    "chest_triceps": (
        (MuscleGroup.CHEST,),
        (MuscleGroup.TRICEPS,),
    ),
    "back_biceps": (
        (MuscleGroup.BACK,),
        (MuscleGroup.BICEPS,),
    ),
    "shoulders_traps": ((MuscleGroup.SHOULDERS,), (MuscleGroup.TRAPS,)),
    "quadriceps_calves": ((MuscleGroup.QUADRICEPS,), (MuscleGroup.CALVES,)),
    "biceps": ((MuscleGroup.BICEPS,),),
    "triceps": ((MuscleGroup.TRICEPS,),),
    "chest": ((MuscleGroup.CHEST,),),
    "back": ((MuscleGroup.BACK,),),
    "shoulders": ((MuscleGroup.SHOULDERS,), (MuscleGroup.TRAPS,)),
    "arms": ((MuscleGroup.BICEPS, MuscleGroup.TRICEPS),),
    "posterior_chain_core": (
        (MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES),
        (),
        (MuscleGroup.CALVES, MuscleGroup.ABS),
    ),
    "push": (
        (MuscleGroup.CHEST, MuscleGroup.SHOULDERS),
        (MuscleGroup.TRICEPS,),
    ),
    "pull": (
        (MuscleGroup.BACK,),
        (MuscleGroup.BICEPS,),
        (MuscleGroup.SHOULDERS, MuscleGroup.TRAPS),
    ),
    "upper": (
        (MuscleGroup.CHEST, MuscleGroup.BACK),
        (MuscleGroup.SHOULDERS,),
        (MuscleGroup.TRAPS, MuscleGroup.BICEPS, MuscleGroup.TRICEPS),
        (MuscleGroup.FOREARMS,),
    ),
    "lower": (
        (MuscleGroup.QUADRICEPS, MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES),
        (MuscleGroup.CALVES,),
        (MuscleGroup.ABS,),
    ),
    "full_body": (
        (
            MuscleGroup.CHEST,
            MuscleGroup.BACK,
            MuscleGroup.QUADRICEPS,
            MuscleGroup.HAMSTRINGS,
            MuscleGroup.GLUTES,
        ),
        (
            MuscleGroup.SHOULDERS,
            MuscleGroup.BICEPS,
            MuscleGroup.TRICEPS,
            MuscleGroup.CALVES,
        ),
        (
            MuscleGroup.TRAPS,
            MuscleGroup.FOREARMS,
            MuscleGroup.ABDUCTORS,
            MuscleGroup.ADDUCTORS,
            MuscleGroup.ABS,
        ),
    ),
}

_FOCUS_ALLOWED: dict[str, frozenset[MuscleGroup]] = {
    "chest_triceps": frozenset({MuscleGroup.CHEST, MuscleGroup.TRICEPS}),
    "back_biceps": frozenset({MuscleGroup.BACK, MuscleGroup.BICEPS}),
    "shoulders_traps": frozenset({MuscleGroup.SHOULDERS, MuscleGroup.TRAPS}),
    "quadriceps_calves": frozenset({MuscleGroup.QUADRICEPS, MuscleGroup.CALVES}),
    "chest": frozenset({MuscleGroup.CHEST}),
    "back": frozenset({MuscleGroup.BACK}),
    "shoulders": frozenset({MuscleGroup.SHOULDERS, MuscleGroup.TRAPS}),
    "arms": frozenset({MuscleGroup.BICEPS, MuscleGroup.TRICEPS}),
    "biceps": frozenset({MuscleGroup.BICEPS}),
    "triceps": frozenset({MuscleGroup.TRICEPS}),
    "posterior_chain_core": frozenset(
        {MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES, MuscleGroup.CALVES, MuscleGroup.ABS}
    ),
    "push": frozenset({MuscleGroup.CHEST, MuscleGroup.SHOULDERS, MuscleGroup.TRICEPS}),
    "pull": frozenset({MuscleGroup.BACK, MuscleGroup.BICEPS}),
    "upper": frozenset(
        {
            MuscleGroup.CHEST,
            MuscleGroup.BACK,
            MuscleGroup.SHOULDERS,
            MuscleGroup.TRAPS,
            MuscleGroup.BICEPS,
            MuscleGroup.TRICEPS,
        }
    ),
    "lower": frozenset(
        {
            MuscleGroup.QUADRICEPS,
            MuscleGroup.HAMSTRINGS,
            MuscleGroup.GLUTES,
            MuscleGroup.CALVES,
            MuscleGroup.ABS,
        }
    ),
    "full_body": frozenset(muscle for group in _FOCUS_HIERARCHY["full_body"] for muscle in group),
}


def _hierarchy_for_focus(focus: str) -> tuple[tuple[MuscleGroup, ...], ...]:
    if focus.startswith("template_reference"):
        return _FOCUS_HIERARCHY["full_body"]
    if focus.startswith("upper"):
        return _FOCUS_HIERARCHY["upper"]
    if focus.startswith("lower") or focus == "legs":
        return _FOCUS_HIERARCHY["lower"]
    if focus.startswith("full_body"):
        return _FOCUS_HIERARCHY["full_body"]
    if focus == "other":
        return _FOCUS_HIERARCHY["full_body"]
    return _FOCUS_HIERARCHY.get(focus, ())


def _default_allowed_for_focus(focus: str) -> frozenset[MuscleGroup]:
    if focus.startswith("upper"):
        return _FOCUS_ALLOWED["upper"]
    if focus.startswith("lower") or focus == "legs":
        return _FOCUS_ALLOWED["lower"]
    if focus.startswith("full_body"):
        return _FOCUS_ALLOWED["full_body"]
    return _FOCUS_ALLOWED.get(focus, frozenset())


def _roles_for(
    allowed: frozenset[MuscleGroup],
    hierarchy: tuple[tuple[MuscleGroup, ...], ...],
) -> tuple[frozenset[MuscleGroup], frozenset[MuscleGroup], frozenset[MuscleGroup]]:
    primary = frozenset(hierarchy[0]).intersection(allowed) if hierarchy else frozenset()
    secondary = frozenset(hierarchy[1]).intersection(allowed) if len(hierarchy) > 1 else frozenset()
    accessory = (
        frozenset(muscle for group in hierarchy[2:] for muscle in group)
        .intersection(allowed)
        if len(hierarchy) > 2
        else frozenset()
    )
    assigned = primary | secondary | accessory
    # Exact template metadata may intentionally add a small group to a structural focus
    # (for example Shoulders + Calves). It remains allowed but never outranks the focus block.
    accessory = accessory | (allowed - assigned)
    return primary, secondary, accessory


@dataclass(frozen=True)
class SessionCoherence:
    """Immutable direct scope and role hierarchy for one session."""

    focus: str
    allowed_direct_muscles: frozenset[MuscleGroup]
    primary_muscles: frozenset[MuscleGroup]
    secondary_muscles: frozenset[MuscleGroup]
    accessory_muscles: frozenset[MuscleGroup]
    source: str = "dynamic_focus"

    @classmethod
    def from_dynamic_focus(cls, focus: str) -> SessionCoherence:
        allowed = _default_allowed_for_focus(focus)
        primary, secondary, accessory = _roles_for(allowed, _hierarchy_for_focus(focus))
        return cls(focus, allowed, primary, secondary, accessory)

    @classmethod
    def from_focus(cls, focus: str) -> SessionCoherence:
        return cls.from_dynamic_focus(focus)

    @classmethod
    def from_template_reference_day(cls, day: TemplateReferenceDay) -> SessionCoherence:
        structure_focus = getattr(day, "structure_focus", "full_body") or "full_body"
        targets = frozenset(getattr(day, "focus", ()))
        hierarchy = _hierarchy_for_focus(structure_focus)
        primary, secondary, accessory = _roles_for(targets, hierarchy)
        return cls(
            focus=f"template_reference_{getattr(day, 'day_number', '')}".rstrip("_"),
            allowed_direct_muscles=targets,
            primary_muscles=primary,
            secondary_muscles=secondary,
            accessory_muscles=accessory,
            source="template_reference_day",
        )

    @classmethod
    def from_session_draft(cls, draft: SessionDraft | object) -> SessionCoherence:
        targets = frozenset(getattr(draft, "template_target_muscles", ()))
        if targets:
            structure_focus = getattr(draft, "template_structure_focus", "full_body")
            hierarchy = _hierarchy_for_focus(structure_focus)
            primary, secondary, accessory = _roles_for(targets, hierarchy)
            return cls(
                focus=getattr(draft, "focus", ""),
                allowed_direct_muscles=targets,
                primary_muscles=primary,
                secondary_muscles=secondary,
                accessory_muscles=accessory,
                source="template_session_draft",
            )
        return cls.from_dynamic_focus(getattr(draft, "focus", ""))

    @classmethod
    def from_workout_day(cls, day: WorkoutDay | object) -> SessionCoherence:
        targets = frozenset(getattr(day, "template_target_muscles", ()))
        if targets:
            structure_focus = getattr(day, "template_structure_focus", "full_body")
            hierarchy = _hierarchy_for_focus(structure_focus)
            primary, secondary, accessory = _roles_for(targets, hierarchy)
            return cls(
                focus=getattr(day, "focus", ""),
                allowed_direct_muscles=targets,
                primary_muscles=primary,
                secondary_muscles=secondary,
                accessory_muscles=accessory,
                source="template_workout_day",
            )
        focus = getattr(day, "focus", "")
        if focus.startswith("template_reference"):
            structure_focus = getattr(day, "template_structure_focus", "full_body")
            structural = cls.from_dynamic_focus(structure_focus)
            return cls(
                focus=focus,
                allowed_direct_muscles=structural.allowed_direct_muscles,
                primary_muscles=structural.primary_muscles,
                secondary_muscles=structural.secondary_muscles,
                accessory_muscles=structural.accessory_muscles,
                source="template_workout_day",
            )
        return cls.from_dynamic_focus(focus)

    @property
    def allowed_muscles(self) -> frozenset[MuscleGroup]:
        return self.allowed_direct_muscles

    @property
    def primary(self) -> frozenset[MuscleGroup]:
        return self.primary_muscles

    @property
    def secondary(self) -> frozenset[MuscleGroup]:
        return self.secondary_muscles

    @property
    def accessory(self) -> frozenset[MuscleGroup]:
        return self.accessory_muscles

    def role_for(self, muscle: MuscleGroup | None) -> SessionMuscleRole:
        if muscle is None or muscle not in self.allowed_direct_muscles:
            return SessionMuscleRole.DISALLOWED
        if muscle in self.primary_muscles:
            return SessionMuscleRole.PRIMARY
        if muscle in self.secondary_muscles:
            return SessionMuscleRole.SECONDARY
        if muscle in self.accessory_muscles:
            return SessionMuscleRole.ACCESSORY
        return SessionMuscleRole.DISALLOWED

    def allows_direct(self, muscle: MuscleGroup | None) -> bool:
        return self.role_for(muscle) is not SessionMuscleRole.DISALLOWED

    def role_rank(self, muscle: MuscleGroup | None) -> int:
        return {
            SessionMuscleRole.PRIMARY: 0,
            SessionMuscleRole.SECONDARY: 1,
            SessionMuscleRole.ACCESSORY: 2,
            SessionMuscleRole.DISALLOWED: 3,
        }[self.role_for(muscle)]

    def ordered_blocks(self) -> tuple[frozenset[MuscleGroup], ...]:
        """Return non-empty direct-muscle blocks in coach-prescribed order."""
        return tuple(
            block
            for block in (
                self.primary_muscles,
                self.secondary_muscles,
                self.accessory_muscles,
            )
            if block
        )

    def placement_rank(
        self,
        muscle: MuscleGroup | None,
        *,
        existing_exposure: bool = False,
        user_priority: bool = False,
    ) -> tuple[int, int, int, int, str]:
        """Return a deterministic lower-is-better placement key."""
        role = self.role_for(muscle)
        return (
            self._intended_day_rank(role),
            self.role_rank(muscle),
            0 if existing_exposure and role is not SessionMuscleRole.DISALLOWED else 1,
            0 if user_priority and role is not SessionMuscleRole.DISALLOWED else 1,
            muscle.value if muscle is not None else "",
        )

    def _intended_day_rank(self, role: SessionMuscleRole) -> int:
        if role is SessionMuscleRole.DISALLOWED:
            return 3
        if self.source == "template_workout_day" or self.source == "template_session_draft":
            return 0 if role is SessionMuscleRole.PRIMARY else 1
        if self.focus in {"push", "pull", "lower", "legs", "upper", "full_body", "other"}:
            return 1
        return 0 if role is SessionMuscleRole.PRIMARY else 1

    def trace(self) -> dict[str, Any]:
        def ordered(muscles: frozenset[MuscleGroup]) -> list[str]:
            return sorted(muscle.value for muscle in muscles)

        return {
            "focus": self.focus,
            "source": self.source,
            "allowed_direct_muscles": ordered(self.allowed_direct_muscles),
            "primary_muscles": ordered(self.primary_muscles),
            "secondary_muscles": ordered(self.secondary_muscles),
            "accessory_muscles": ordered(self.accessory_muscles),
        }

    def audit(self, day: WorkoutDay | SessionDraft | object) -> dict[str, Any]:
        exercises = tuple(getattr(day, "exercises", ()))
        direct = [
            item.primary_muscle
            for item in exercises
            if getattr(item, "primary_muscle", None) is not None
            and not is_core_or_supplemental_exercise(item)
        ]
        counts: dict[str, int] = {}
        for muscle in direct:
            counts[muscle.value] = counts.get(muscle.value, 0) + 1
        orphan = sorted(
            {muscle.value for muscle in direct if not self.allows_direct(muscle)}
        )
        return {
            "direct_groups": sorted(counts),
            "direct_exercise_counts": dict(sorted(counts.items())),
            "orphan_direct_exposures": orphan,
            "focus_preserved": not orphan,
            "exercise_count": len(exercises),
        }


def hierarchy_for_focus(focus: str) -> tuple[tuple[MuscleGroup, ...], ...]:
    return _hierarchy_for_focus(focus)


def direct_scope_for_focus(focus: str) -> frozenset[MuscleGroup]:
    return _default_allowed_for_focus(focus)


def specialization_focus_for_priorities(
    priorities: frozenset[MuscleGroup] | tuple[MuscleGroup, ...] | set[MuscleGroup],
    *,
    highest_target: MuscleGroup | None = None,
) -> str:
    priority_set = set(priorities)
    if priority_set == {MuscleGroup.BICEPS}:
        return "biceps"
    if priority_set == {MuscleGroup.TRICEPS}:
        return "triceps"
    for muscle_groups, focus in (
        ((MuscleGroup.CHEST, MuscleGroup.TRICEPS), "chest_triceps"),
        ((MuscleGroup.BACK, MuscleGroup.BICEPS), "back_biceps"),
        ((MuscleGroup.SHOULDERS, MuscleGroup.TRAPS), "shoulders_traps"),
        ((MuscleGroup.QUADRICEPS, MuscleGroup.CALVES), "quadriceps_calves"),
        ((MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES, MuscleGroup.ABS), "posterior_chain_core"),
    ):
        if set(muscle_groups).intersection(priority_set):
            return focus
    if highest_target is MuscleGroup.BACK:
        return "back_biceps"
    if highest_target is MuscleGroup.SHOULDERS:
        return "shoulders_traps"
    if highest_target in {MuscleGroup.QUADRICEPS, MuscleGroup.CALVES}:
        return "quadriceps_calves"
    if highest_target in {MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES}:
        return "posterior_chain_core"
    return "chest_triceps"


__all__ = [
    "SessionCoherence",
    "SessionCoherenceDecision",
    "SessionMuscleRole",
    "direct_scope_for_focus",
    "hierarchy_for_focus",
    "ordered_coherence_decisions",
    "record_coherence_decision",
    "specialization_focus_for_priorities",
]
