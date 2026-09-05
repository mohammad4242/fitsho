import re

with open("backend/app/workouts/program_engine/schemas.py", "r") as f:
    content = f.read()

# I will just put superset_exercise_id and superset_exercise_slug_hint without defaults.
# It doesn't need to have a default, we pass it every time.

old_slot = """@dataclass(frozen=True)
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

new_slot = """@dataclass(frozen=True)
class TemplateReferenceSlot:
    exercise_id: UUID | None
    exercise_slug_hint: str
    target_muscles: tuple[MuscleGroup, ...]
    movement_pattern: MovementPattern
    intensity_method: str
    adaptation_priority: str
    superset_group: str | None
    superset_exercise_id: UUID | None
    superset_exercise_slug_hint: str | None
    sets: int"""

content = content.replace(old_slot, new_slot)
with open("backend/app/workouts/program_engine/schemas.py", "w") as f:
    f.write(content)
