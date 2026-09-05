import re

with open("backend/app/training_templates/service.py", "r") as f:
    content = f.read()

old_loop = """        for slot_order, slot_seed in enumerate(day_seed.slots, start=1):
            exercise_id = _exercise_id_for_slot(slot_seed.catalog_slug_hints, exercises_by_slug)
            day.slots.append(
                TrainingProgramTemplateSlot(
                    slot_order=slot_order,
                    exercise_id=exercise_id,
                    exercise_slug_hint=slot_seed.exercise_slug_hint,
                    placeholder_name_en=slot_seed.placeholder_name_en,
                    placeholder_name_fa=slot_seed.placeholder_name_fa,
                    target_muscles=[muscle.value for muscle in slot_seed.target_muscles],
                    movement_pattern=slot_seed.movement_pattern,
                    intensity_method=slot_seed.intensity_method,
                    adaptation_priority=slot_seed.adaptation_priority,
                    superset_group=slot_seed.superset_group,
                    sets=slot_seed.sets,
                    rep_min=slot_seed.rep_min,
                    rep_max=slot_seed.rep_max,
                    target_rir=slot_seed.target_rir,
                    rest_seconds=slot_seed.rest_seconds,
                )
            )"""

new_loop = """        merged_slots = []
        superset_pending = {}
        for slot_seed in day_seed.slots:
            if slot_seed.intensity_method.value == "superset" and slot_seed.superset_group:
                group = slot_seed.superset_group
                if group not in superset_pending:
                    superset_pending[group] = slot_seed
                else:
                    merged_slots.append((superset_pending.pop(group), slot_seed))
            else:
                merged_slots.append((slot_seed, None))

        for slot_order, (slot_seed, second_seed) in enumerate(merged_slots, start=1):
            exercise_id = _exercise_id_for_slot(slot_seed.catalog_slug_hints, exercises_by_slug)
            superset_exercise_id = None
            superset_exercise_slug_hint = None
            if second_seed is not None:
                superset_exercise_id = _exercise_id_for_slot(second_seed.catalog_slug_hints, exercises_by_slug)
                superset_exercise_slug_hint = second_seed.exercise_slug_hint
                
            day.slots.append(
                TrainingProgramTemplateSlot(
                    slot_order=slot_order,
                    exercise_id=exercise_id,
                    exercise_slug_hint=slot_seed.exercise_slug_hint,
                    superset_exercise_id=superset_exercise_id,
                    superset_exercise_slug_hint=superset_exercise_slug_hint,
                    placeholder_name_en=slot_seed.placeholder_name_en,
                    placeholder_name_fa=slot_seed.placeholder_name_fa,
                    target_muscles=[muscle.value for muscle in slot_seed.target_muscles],
                    movement_pattern=slot_seed.movement_pattern,
                    intensity_method=slot_seed.intensity_method,
                    adaptation_priority=slot_seed.adaptation_priority,
                    superset_group=None,
                    sets=slot_seed.sets,
                    rep_min=slot_seed.rep_min,
                    rep_max=slot_seed.rep_max,
                    target_rir=slot_seed.target_rir,
                    rest_seconds=slot_seed.rest_seconds,
                )
            )"""

content = content.replace(old_loop, new_loop)

with open("backend/app/training_templates/service.py", "w") as f:
    f.write(content)
