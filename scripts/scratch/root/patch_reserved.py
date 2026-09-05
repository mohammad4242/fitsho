import re

with open("backend/app/workouts/program_engine/template_sessions.py", "r") as f:
    content = f.read()

# patch reserved
old_reserved = """    reserved: Counter[UUID] = Counter(
        slot.exercise_id
        for day in template.days
        for slot in day.slots
        if slot.exercise_id is not None
    )"""
new_reserved = """    reserved_ids = []
    for day in template.days:
        for slot in day.slots:
            if slot.exercise_id is not None:
                reserved_ids.append(slot.exercise_id)
            if getattr(slot, 'superset_exercise_id', None) is not None:
                reserved_ids.append(slot.superset_exercise_id)
    reserved: Counter[UUID] = Counter(reserved_ids)"""

content = content.replace(old_reserved, new_reserved)

# patch flattened slots in build_template_sessions
# I need to find `        for slot in reference_day.slots:`
old_loop = """        selected: list[tuple[ExerciseCandidate, TemplateReferenceSlot]] = []
        for slot in reference_day.slots:
            if slot.exercise_id is not None:
                reserved[slot.exercise_id] -= 1"""

new_loop = """        selected: list[tuple[ExerciseCandidate, TemplateReferenceSlot]] = []
        
        expanded_slots = []
        for slot in reference_day.slots:
            if slot.intensity_method == "superset" and getattr(slot, 'superset_exercise_id', None):
                group_id = slot.superset_group or f"auto_{str(slot.exercise_id)[:8]}_{str(slot.superset_exercise_id)[:8]}"
                from dataclasses import replace
                slot_first = replace(slot, superset_group=group_id)
                expanded_slots.append(slot_first)
                
                second_candidate = next((ex for ex in eligible if ex.id == slot.superset_exercise_id), None)
                if second_candidate:
                    second_muscles = (second_candidate.primary_muscle,)
                    second_pattern = second_candidate.movement_pattern
                else:
                    second_muscles = slot.target_muscles
                    second_pattern = slot.movement_pattern
                
                slot_second = replace(
                    slot_first,
                    exercise_id=slot.superset_exercise_id,
                    exercise_slug_hint=slot.superset_exercise_slug_hint,
                    target_muscles=second_muscles,
                    movement_pattern=second_pattern,
                    superset_exercise_id=None,
                    superset_exercise_slug_hint=None,
                )
                expanded_slots.append(slot_second)
            else:
                expanded_slots.append(slot)

        for slot in expanded_slots:
            if slot.exercise_id is not None:
                reserved[slot.exercise_id] -= 1"""

content = content.replace(old_loop, new_loop)
with open("backend/app/workouts/program_engine/template_sessions.py", "w") as f:
    f.write(content)
