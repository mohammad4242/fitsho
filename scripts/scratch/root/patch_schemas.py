import re

with open("backend/app/admin/schemas.py", "r") as f:
    content = f.read()

# AdminTrainingTemplateSlot
slot_read_replacement = """    rest_seconds: int
    exercise: AdminTrainingTemplateExercise | None
    superset_exercise: AdminTrainingTemplateExercise | None = None
"""
content = re.sub(r'    rest_seconds: int\n    exercise: AdminTrainingTemplateExercise \| None\n', slot_read_replacement, content)

# AdminTrainingTemplateSlotWrite
slot_write_replacement = """    adaptation_priority: TrainingTemplateSlotPriority = TrainingTemplateSlotPriority.ACCESSORY
    superset_group: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=32),
    ] = None
    superset_exercise_id: UUID | None = None
    sets: int = Field(ge=1, le=10)"""
content = re.sub(r'    adaptation_priority: TrainingTemplateSlotPriority = TrainingTemplateSlotPriority.ACCESSORY\n    superset_group: Annotated\[\n        str \| None,\n        StringConstraints\(strip_whitespace=True, min_length=1, max_length=32\),\n    \] = None\n    sets: int = Field\(ge=1, le=10\)', slot_write_replacement, content)

# validate_program_shape
validate_shape_old = """        for day in self.days:
            groups: dict[str, list[int]] = {}
            for index, slot in enumerate(day.slots):
                if slot.intensity_method is TrainingTemplateMethod.SUPERSET:
                    if slot.superset_group is None:
                        raise ValueError("Superset slots require a group")
                    groups.setdefault(slot.superset_group, []).append(index)
                elif slot.superset_group is not None:
                    raise ValueError("Only superset slots may declare a superset group")
            if any(
                len(indices) != 2 or indices[1] != indices[0] + 1
                for indices in groups.values()
            ):
                raise ValueError("Superset groups must contain one adjacent pair")
        return self"""

validate_shape_new = """        for day in self.days:
            for slot in day.slots:
                if slot.intensity_method is TrainingTemplateMethod.SUPERSET:
                    if slot.superset_exercise_id is None:
                        raise ValueError("Superset slots require a superset_exercise_id")
                    if slot.exercise_id == slot.superset_exercise_id:
                        raise ValueError("Superset exercises must be different")
                else:
                    if slot.superset_exercise_id is not None:
                        raise ValueError("Only superset slots may declare a superset_exercise_id")
        return self"""

content = content.replace(validate_shape_old, validate_shape_new)

with open("backend/app/admin/schemas.py", "w") as f:
    f.write(content)
