"""Read-only, deterministic audit of programmable exercise substitution metadata."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database.session import get_engine
from app.exercises.enums import (
    Equipment,
    ExerciseContentType,
    ExerciseLabel,
    ExerciseType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.models import Exercise, ExerciseAlternative
from app.exercises.substitution_groups import LEGACY_BROAD_SUBSTITUTION_GROUPS
from app.exercises.taxonomy import FOCUSES_BY_MUSCLE
from app.workouts.program_engine.equipment import effective_required_equipment
from app.workouts.program_engine.exercise_semantics import ExerciseRoleSignature

HOME_EQUIPMENT = frozenset(
    {
        Equipment.BODYWEIGHT,
        Equipment.DUMBBELL,
        Equipment.RESISTANCE_BAND,
        Equipment.BENCH,
        Equipment.PULL_UP_BAR,
    }
)


@dataclass(frozen=True, slots=True)
class ExerciseRef:
    """Stable, immutable exercise identity used by audit findings."""

    id: str
    slug: str

    @classmethod
    def from_exercise(cls, exercise: Exercise) -> ExerciseRef:
        return cls(id=str(exercise.id), slug=exercise.slug)

    def as_json(self) -> dict[str, str]:
        return {"id": self.id, "slug": self.slug}


@dataclass(frozen=True, slots=True)
class SemanticTuple:
    """Persisted semantics used to detect mixed substitution groups."""

    movement_pattern: MovementPattern
    primary_muscle: MuscleGroup | None
    muscle_focus: MuscleFocus | None
    exercise_type: ExerciseType

    def as_json(self) -> dict[str, str | None]:
        return {
            "movement_pattern": self.movement_pattern.value,
            "primary_muscle": self.primary_muscle.value if self.primary_muscle else None,
            "muscle_focus": self.muscle_focus.value if self.muscle_focus else None,
            "exercise_type": self.exercise_type.value,
        }


@dataclass(frozen=True, slots=True)
class MixedSubstitutionGroup:
    group: str
    semantic_tuples: tuple[SemanticTuple, ...]
    exercises: tuple[ExerciseRef, ...]

    def as_json(self) -> dict[str, Any]:
        return {
            "group": self.group,
            "semantic_tuples": [item.as_json() for item in self.semantic_tuples],
            "exercises": [item.as_json() for item in self.exercises],
        }


@dataclass(frozen=True, slots=True)
class AlternativeCoverage:
    exercise: ExerciseRef
    alternatives: tuple[ExerciseRef, ...]

    def as_json(self) -> dict[str, Any]:
        return {
            "exercise": self.exercise.as_json(),
            "alternatives": [item.as_json() for item in self.alternatives],
        }


@dataclass(frozen=True, slots=True)
class RoleCoverage:
    signature: ExerciseRoleSignature
    candidates: tuple[ExerciseRef, ...]
    home_compatible_candidates: tuple[ExerciseRef, ...]

    def as_json(self) -> dict[str, Any]:
        return {
            "signature": _signature_as_json(self.signature),
            "candidates": [item.as_json() for item in self.candidates],
            "home_compatible_candidates": [
                item.as_json() for item in self.home_compatible_candidates
            ],
        }


@dataclass(frozen=True, slots=True)
class SubstitutionMetadataAuditReport:
    """Immutable result of auditing the programmable resistance catalogue."""

    exercises: tuple[ExerciseRef, ...]
    missing_primary_muscle: tuple[ExerciseRef, ...]
    missing_muscle_focus: tuple[ExerciseRef, ...]
    movement_pattern_other: tuple[ExerciseRef, ...]
    exercise_type_other: tuple[ExerciseRef, ...]
    missing_equipment: tuple[ExerciseRef, ...]
    equipment_other: tuple[ExerciseRef, ...]
    missing_body_position: tuple[ExerciseRef, ...]
    missing_stability_demand: tuple[ExerciseRef, ...]
    missing_skill_demand: tuple[ExerciseRef, ...]
    missing_impact_level: tuple[ExerciseRef, ...]
    missing_axial_loading_level: tuple[ExerciseRef, ...]
    missing_laterality: tuple[ExerciseRef, ...]
    missing_substitution_group: tuple[ExerciseRef, ...]
    legacy_broad_substitution_groups: tuple[ExerciseRef, ...]
    mixed_substitution_groups: tuple[MixedSubstitutionGroup, ...]
    alternative_coverage: tuple[AlternativeCoverage, ...]
    uncovered_alternative_exercises: tuple[ExerciseRef, ...]
    home_role_coverage: tuple[RoleCoverage, ...]
    home_incompatible_roles: tuple[RoleCoverage, ...]
    singleton_roles: tuple[RoleCoverage, ...]

    def as_json(self) -> dict[str, Any]:
        payload = {
            "exercises": _refs_as_json(self.exercises),
            "missing_primary_muscle": _refs_as_json(self.missing_primary_muscle),
            "missing_muscle_focus": _refs_as_json(self.missing_muscle_focus),
            "movement_pattern_other": _refs_as_json(self.movement_pattern_other),
            "exercise_type_other": _refs_as_json(self.exercise_type_other),
            "missing_equipment": _refs_as_json(self.missing_equipment),
            "equipment_other": _refs_as_json(self.equipment_other),
            "missing_body_position": _refs_as_json(self.missing_body_position),
            "missing_stability_demand": _refs_as_json(self.missing_stability_demand),
            "missing_skill_demand": _refs_as_json(self.missing_skill_demand),
            "missing_impact_level": _refs_as_json(self.missing_impact_level),
            "missing_axial_loading_level": _refs_as_json(self.missing_axial_loading_level),
            "missing_laterality": _refs_as_json(self.missing_laterality),
            "missing_substitution_group": _refs_as_json(self.missing_substitution_group),
            "legacy_broad_substitution_groups": _refs_as_json(
                self.legacy_broad_substitution_groups
            ),
            "mixed_substitution_groups": [
                item.as_json() for item in self.mixed_substitution_groups
            ],
            "alternative_coverage": [item.as_json() for item in self.alternative_coverage],
            "uncovered_alternative_exercises": _refs_as_json(self.uncovered_alternative_exercises),
            "home_role_coverage": [item.as_json() for item in self.home_role_coverage],
            "home_incompatible_roles": [item.as_json() for item in self.home_incompatible_roles],
            "singleton_roles": [item.as_json() for item in self.singleton_roles],
        }
        return {key: payload[key] for key in sorted(payload)}

    to_dict = as_json


def audit_catalogue(db: Session) -> SubstitutionMetadataAuditReport:
    """Audit persisted metadata without changing the database or catalog rows."""

    exercises = list(
        db.scalars(
            select(Exercise)
            .where(
                Exercise.content_type == ExerciseContentType.EXERCISE,
                Exercise.is_programmable.is_(True),
                Exercise.exercise_type != ExerciseType.MOBILITY,
            )
            .options(
                selectinload(Exercise.labels),
                selectinload(Exercise.equipment_items),
                selectinload(Exercise.secondary_muscles),
                selectinload(Exercise.alternatives).selectinload(
                    ExerciseAlternative.alternative_exercise
                ),
            )
            .order_by(Exercise.slug.asc(), Exercise.id.asc())
        )
    )
    exercises = [
        exercise
        for exercise in exercises
        if not any(item.label is ExerciseLabel.CARDIO for item in exercise.labels)
    ]
    refs = tuple(ExerciseRef.from_exercise(exercise) for exercise in exercises)

    def refs_where(predicate: Any) -> tuple[ExerciseRef, ...]:
        return tuple(
            ExerciseRef.from_exercise(exercise) for exercise in exercises if predicate(exercise)
        )

    missing_primary = refs_where(lambda item: item.primary_muscle is None)
    missing_focus = refs_where(_missing_muscle_focus)
    movement_other = refs_where(lambda item: item.movement_pattern is MovementPattern.OTHER)
    type_other = refs_where(lambda item: item.exercise_type is ExerciseType.OTHER)
    missing_equipment = refs_where(lambda item: not item.equipment_items)
    equipment_other = refs_where(
        lambda item: any(entry.equipment is Equipment.OTHER for entry in item.equipment_items)
    )
    missing_body_position = refs_where(lambda item: item.body_position is None)
    missing_stability = refs_where(lambda item: item.stability_demand is None)
    missing_skill = refs_where(lambda item: item.skill_demand is None)
    missing_impact = refs_where(lambda item: item.impact_level is None)
    missing_axial = refs_where(lambda item: item.axial_loading_level is None)
    missing_laterality = refs_where(lambda item: item.laterality is None)
    missing_group = refs_where(lambda item: not item.substitution_group)
    legacy_groups = refs_where(
        lambda item: item.substitution_group in LEGACY_BROAD_SUBSTITUTION_GROUPS
    )

    mixed_groups = _mixed_groups(exercises)
    alternatives = _alternative_coverage(exercises)
    uncovered = tuple(item.exercise for item in alternatives if not item.alternatives)
    role_coverage = _role_coverage(exercises)
    home_incompatible = tuple(item for item in role_coverage if not item.home_compatible_candidates)
    singleton = tuple(item for item in role_coverage if len(item.candidates) == 1)

    return SubstitutionMetadataAuditReport(
        exercises=refs,
        missing_primary_muscle=missing_primary,
        missing_muscle_focus=missing_focus,
        movement_pattern_other=movement_other,
        exercise_type_other=type_other,
        missing_equipment=missing_equipment,
        equipment_other=equipment_other,
        missing_body_position=missing_body_position,
        missing_stability_demand=missing_stability,
        missing_skill_demand=missing_skill,
        missing_impact_level=missing_impact,
        missing_axial_loading_level=missing_axial,
        missing_laterality=missing_laterality,
        missing_substitution_group=missing_group,
        legacy_broad_substitution_groups=legacy_groups,
        mixed_substitution_groups=mixed_groups,
        alternative_coverage=alternatives,
        uncovered_alternative_exercises=uncovered,
        home_role_coverage=role_coverage,
        home_incompatible_roles=home_incompatible,
        singleton_roles=singleton,
    )


audit_substitution_metadata = audit_catalogue


def _missing_muscle_focus(exercise: Exercise) -> bool:
    primary = exercise.primary_muscle
    return (
        primary is not None and bool(FOCUSES_BY_MUSCLE[primary]) and exercise.muscle_focus is None
    )


def _semantic_tuple(exercise: Exercise) -> SemanticTuple:
    return SemanticTuple(
        movement_pattern=exercise.movement_pattern,
        primary_muscle=exercise.primary_muscle,
        muscle_focus=exercise.muscle_focus,
        exercise_type=exercise.exercise_type,
    )


def _mixed_groups(exercises: list[Exercise]) -> tuple[MixedSubstitutionGroup, ...]:
    grouped: dict[str, dict[SemanticTuple, list[ExerciseRef]]] = {}
    for exercise in exercises:
        if not exercise.substitution_group:
            continue
        semantic = _semantic_tuple(exercise)
        grouped.setdefault(exercise.substitution_group, {}).setdefault(semantic, []).append(
            ExerciseRef.from_exercise(exercise)
        )

    findings: list[MixedSubstitutionGroup] = []
    for group in sorted(grouped):
        semantics = grouped[group]
        if len(semantics) < 2:
            continue
        ordered_semantics = tuple(
            sorted(
                semantics,
                key=lambda item: (
                    item.movement_pattern.value,
                    item.primary_muscle.value if item.primary_muscle else "",
                    item.muscle_focus.value if item.muscle_focus else "",
                    item.exercise_type.value,
                ),
            )
        )
        refs = tuple(sorted((ref for values in semantics.values() for ref in values), key=_ref_key))
        findings.append(
            MixedSubstitutionGroup(
                group=group,
                semantic_tuples=ordered_semantics,
                exercises=refs,
            )
        )
    return tuple(findings)


def _alternative_coverage(exercises: list[Exercise]) -> tuple[AlternativeCoverage, ...]:
    findings: list[AlternativeCoverage] = []
    for exercise in exercises:
        alternatives = tuple(
            sorted(
                (
                    ExerciseRef.from_exercise(item.alternative_exercise)
                    for item in exercise.alternatives
                    if item.alternative_exercise is not None
                ),
                key=_ref_key,
            )
        )
        findings.append(
            AlternativeCoverage(
                exercise=ExerciseRef.from_exercise(exercise),
                alternatives=alternatives,
            )
        )
    return tuple(findings)


def _role_coverage(exercises: list[Exercise]) -> tuple[RoleCoverage, ...]:
    grouped: dict[ExerciseRoleSignature, list[tuple[ExerciseRef, frozenset[Equipment]]]] = {}
    for exercise in exercises:
        signature = _role_signature(exercise)
        if signature is None:
            continue
        equipment = frozenset(item.equipment for item in exercise.equipment_items)
        grouped.setdefault(signature, []).append((ExerciseRef.from_exercise(exercise), equipment))

    result: list[RoleCoverage] = []
    for signature, candidates in grouped.items():
        ordered = sorted(candidates, key=lambda item: _ref_key(item[0]))
        refs = tuple(item[0] for item in ordered)
        home_refs = tuple(
            ref
            for ref, equipment in ordered
            if equipment
            and effective_required_equipment(equipment, signature.movement_pattern).issubset(
                HOME_EQUIPMENT
            )
        )
        result.append(
            RoleCoverage(
                signature=signature,
                candidates=refs,
                home_compatible_candidates=home_refs,
            )
        )
    return tuple(sorted(result, key=_role_key))


def _role_signature(exercise: Exercise) -> ExerciseRoleSignature | None:
    movement_pattern = exercise.movement_pattern
    primary_muscle = exercise.primary_muscle
    exercise_type = exercise.exercise_type
    body_position = exercise.body_position
    laterality = exercise.laterality
    substitution_group = exercise.substitution_group
    if (
        movement_pattern is MovementPattern.OTHER
        or primary_muscle is None
        or exercise_type is ExerciseType.OTHER
        or body_position is None
        or laterality is None
        or not substitution_group
    ):
        return None
    secondary_muscles = tuple(
        sorted(
            {item.muscle for item in exercise.secondary_muscles},
            key=lambda muscle: muscle.value,
        )
    )
    return ExerciseRoleSignature(
        movement_pattern=movement_pattern,
        primary_muscle=primary_muscle,
        muscle_focus=exercise.muscle_focus,
        exercise_type=exercise_type,
        secondary_muscles=secondary_muscles,
        body_position=body_position,
        laterality=laterality,
        substitution_group=substitution_group,
    )


def _role_key(item: RoleCoverage) -> tuple[str, ...]:
    signature = item.signature
    return (
        signature.movement_pattern.value,
        signature.primary_muscle.value if signature.primary_muscle else "",
        signature.muscle_focus.value if signature.muscle_focus else "",
        signature.exercise_type.value,
        signature.body_position.value,
        signature.laterality.value,
        signature.substitution_group or "",
        ",".join(muscle.value for muscle in signature.secondary_muscles),
    )


def _signature_as_json(signature: ExerciseRoleSignature) -> dict[str, Any]:
    return {
        "movement_pattern": signature.movement_pattern.value,
        "primary_muscle": signature.primary_muscle.value if signature.primary_muscle else None,
        "muscle_focus": signature.muscle_focus.value if signature.muscle_focus else None,
        "exercise_type": signature.exercise_type.value,
        "secondary_muscles": [item.value for item in signature.secondary_muscles],
        "body_position": signature.body_position.value,
        "laterality": signature.laterality.value,
        "substitution_group": signature.substitution_group,
    }


def _ref_key(item: ExerciseRef) -> tuple[str, str]:
    return item.slug, item.id


def _refs_as_json(items: tuple[ExerciseRef, ...]) -> list[dict[str, str]]:
    return [item.as_json() for item in items]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit programmable exercise substitution metadata"
    )
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    settings = get_settings()
    with Session(get_engine(settings.database_url)) as db:
        report = audit_catalogue(db)
    payload = report.as_json()
    if arguments.format == "json":
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if arguments.output:
            arguments.output.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
    else:
        summary = {key: len(value) for key, value in payload.items() if isinstance(value, list)}
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
