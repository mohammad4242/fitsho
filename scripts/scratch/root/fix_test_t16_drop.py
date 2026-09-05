import re

with open("backend/app/workouts/program_engine/template_sessions.py", "r") as f:
    content = f.read()

content = content.replace(
    'if not decision.exercise_ids:\n                    continue',
    'if not decision.exercise_ids:\n                    print(f"DROPPED SLOT! {slot.exercise_slug_hint} {slot.superset_group}")\n                    continue'
)

with open("backend/app/workouts/program_engine/template_sessions.py", "w") as f:
    f.write(content)
