import re

with open("backend/app/workouts/program_engine/template_sessions.py", "r") as f:
    content = f.read()

content = content.replace(
    'group_id = slot.superset_group or f"auto_{slot.exercise_id}_{slot.superset_exercise_id}"',
    'group_id = slot.superset_group or f"auto_{str(slot.exercise_id)[:8]}_{str(slot.superset_exercise_id)[:8]}"'
)

with open("backend/app/workouts/program_engine/template_sessions.py", "w") as f:
    f.write(content)
