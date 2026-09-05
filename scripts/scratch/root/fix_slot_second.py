import re

with open("backend/app/workouts/program_engine/template_sessions.py", "r") as f:
    content = f.read()

old_expansion = """                slot_second = replace(
                    slot_first,
                    exercise_id=slot.superset_exercise_id,
                    exercise_slug_hint=slot.superset_exercise_slug_hint,
                    superset_exercise_id=None,
                    superset_exercise_slug_hint=None
                )"""

new_expansion = """                second_candidate = next((ex for ex in eligible if ex.id == slot.superset_exercise_id), None)
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
                    superset_exercise_slug_hint=None
                )"""

content = content.replace(old_expansion, new_expansion)

with open("backend/app/workouts/program_engine/template_sessions.py", "w") as f:
    f.write(content)
