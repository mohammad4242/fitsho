import re

with open("backend/app/workouts/program_engine/template_sessions.py", "r") as f:
    content = f.read()

content = content.replace(
    'for slot in expanded_slots:',
    'print("EXPANDED SLOTS:", [(s.superset_group, s.exercise_id, getattr(s, "superset_exercise_id", "N/A")) for s in expanded_slots])\n        for slot in expanded_slots:'
)

with open("backend/app/workouts/program_engine/template_sessions.py", "w") as f:
    f.write(content)
