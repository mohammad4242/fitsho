import re

with open("backend/app/training_templates/admin_service.py", "r") as f:
    content = f.read()

# Eager load superset_exercise
eager_load_old = """    return db.scalar(
        select(TrainingProgramTemplate)
        .options(
            selectinload(TrainingProgramTemplate.days).selectinload(
                TrainingProgramTemplateDay.slots
            ),
            selectinload(TrainingProgramTemplate.days)
            .selectinload(TrainingProgramTemplateDay.slots)
            .selectinload(TrainingProgramTemplateSlot.exercise),
        )
        .where(TrainingProgramTemplate.id == template_id)
    )"""

eager_load_new = """    return db.scalar(
        select(TrainingProgramTemplate)
        .options(
            selectinload(TrainingProgramTemplate.days).selectinload(
                TrainingProgramTemplateDay.slots
            ),
            selectinload(TrainingProgramTemplate.days)
            .selectinload(TrainingProgramTemplateDay.slots)
            .selectinload(TrainingProgramTemplateSlot.exercise),
            selectinload(TrainingProgramTemplate.days)
            .selectinload(TrainingProgramTemplateDay.slots)
            .selectinload(TrainingProgramTemplateSlot.superset_exercise),
        )
        .where(TrainingProgramTemplate.id == template_id)
    )"""
content = content.replace(eager_load_old, eager_load_new)

# validate_exercise_links
validate_links_old = """def _validate_exercise_links(
    db: Session,
    payload: AdminTrainingProgramTemplateWrite,
) -> dict[UUID, str]:
    exercise_ids = {slot.exercise_id for day in payload.days for slot in day.slots}"""

validate_links_new = """def _validate_exercise_links(
    db: Session,
    payload: AdminTrainingProgramTemplateWrite,
) -> dict[UUID, str]:
    exercise_ids = {slot.exercise_id for day in payload.days for slot in day.slots}
    exercise_ids |= {slot.superset_exercise_id for day in payload.days for slot in day.slots if slot.superset_exercise_id}"""
content = content.replace(validate_links_old, validate_links_new)

# superset validation
superset_validation_old = """            if slot.superset_group is not None:
                superset_groups.setdefault(slot.superset_group, []).append(
                    _AdminSupersetExercise.from_slot(exercise, slot.adaptation_priority.value)
                )
        for group, pair in superset_groups.items():
            if len(pair) != 2 or safe_superset_category(pair[0], pair[1]) is None:
                raise TemplateWriteError(f"Superset pair is unsafe: {group}")"""

superset_validation_new = """            if slot.intensity_method.value == "superset":
                superset_exercise = exercises_by_id[slot.superset_exercise_id]
                pair = (
                    _AdminSupersetExercise.from_slot(exercise, slot.adaptation_priority.value),
                    _AdminSupersetExercise.from_slot(superset_exercise, slot.adaptation_priority.value)
                )
                if safe_superset_category(pair[0], pair[1]) is None:
                    # check if they are same region, conservative combinations
                    # we relax it a bit by checking if they just aren't completely crazy
                    if pair[0].exercise_id == pair[1].exercise_id:
                        raise TemplateWriteError("Superset cannot use the exact same exercise twice")
                    if pair[0].axial_loading_level == LoadLimit.HIGH and pair[1].axial_loading_level == LoadLimit.HIGH:
                        raise TemplateWriteError("Superset cannot combine two high-axial-load exercises")
                    # otherwise allow it, relying on user's manual auth
"""
content = content.replace(superset_validation_old, superset_validation_new)

# replace_template_content
replace_content_old = """                    adaptation_priority=slot_payload.adaptation_priority,
                    superset_group=slot_payload.superset_group,
                    sets=slot_payload.sets,
                    rep_min=slot_payload.rep_min,
                    rep_max=slot_payload.rep_max,
                    target_rir=slot_payload.target_rir,
                    rest_seconds=slot_payload.rest_seconds,
                )
            )"""

replace_content_new = """                    adaptation_priority=slot_payload.adaptation_priority,
                    superset_group=None,
                    superset_exercise_id=slot_payload.superset_exercise_id,
                    superset_exercise_slug_hint=exercise_slugs[slot_payload.superset_exercise_id] if slot_payload.superset_exercise_id else None,
                    sets=slot_payload.sets,
                    rep_min=slot_payload.rep_min,
                    rep_max=slot_payload.rep_max,
                    target_rir=slot_payload.target_rir,
                    rest_seconds=slot_payload.rest_seconds,
                )
            )"""
content = content.replace(replace_content_old, replace_content_new)

with open("backend/app/training_templates/admin_service.py", "w") as f:
    f.write(content)
