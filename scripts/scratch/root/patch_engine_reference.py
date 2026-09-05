import re

with open("backend/app/workouts/program_engine/schemas.py", "r") as f:
    content = f.read()

# patch TemplateReferenceSlot
old_slot = """@dataclass(frozen=True)
class TemplateReferenceSlot:
    exercise_id: UUID | None
    exercise_slug_hint: str
    target_muscles: tuple[MuscleGroup, ...]
    movement_pattern: MovementPattern
    intensity_method: str
    adaptation_priority: str
    superset_group: str | None
    sets: int"""

new_slot = """@dataclass(frozen=True)
class TemplateReferenceSlot:
    exercise_id: UUID | None
    exercise_slug_hint: str
    target_muscles: tuple[MuscleGroup, ...]
    movement_pattern: MovementPattern
    intensity_method: str
    adaptation_priority: str
    superset_group: str | None
    superset_exercise_id: UUID | None = None
    superset_exercise_slug_hint: str | None = None
    sets: int"""
content = content.replace(old_slot, new_slot)
with open("backend/app/workouts/program_engine/schemas.py", "w") as f:
    f.write(content)

with open("backend/app/training_templates/engine_reference.py", "r") as f:
    content2 = f.read()

old_ref = """def _slot_reference(slot: TrainingProgramTemplateSlot) -> TemplateReferenceSlot:
    return TemplateReferenceSlot(
        exercise_id=slot.exercise_id,
        exercise_slug_hint=slot.exercise_slug_hint,
        target_muscles=tuple(MuscleGroup(muscle) for muscle in slot.target_muscles),"""

new_ref = """def _slot_reference(slot: TrainingProgramTemplateSlot) -> TemplateReferenceSlot:
    return TemplateReferenceSlot(
        exercise_id=slot.exercise_id,
        exercise_slug_hint=slot.exercise_slug_hint,
        superset_exercise_id=slot.superset_exercise_id,
        superset_exercise_slug_hint=slot.superset_exercise_slug_hint,
        target_muscles=tuple(MuscleGroup(muscle) for muscle in slot.target_muscles),"""

content2 = content2.replace(old_ref, new_ref)
with open("backend/app/training_templates/engine_reference.py", "w") as f:
    f.write(content2)
