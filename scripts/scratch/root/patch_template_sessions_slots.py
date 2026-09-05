import re

with open("backend/app/workouts/program_engine/template_sessions.py", "r") as f:
    content = f.read()

# I will find all instances of `superset_group=None,` or `superset_group=...,` 
# and add `superset_exercise_id=None, superset_exercise_slug_hint=None,` if not already present.

# First let's do the specific one in _add_targeted_accessories:
content = re.sub(
    r'(superset_group=None,)(\s*sets=3)',
    r'\1\n                    superset_exercise_id=None,\n                    superset_exercise_slug_hint=None,\2',
    content
)

# And there might be another one in `_repair_volume_deficit`
content = re.sub(
    r'(superset_group=None,)(\s*sets=gap_sets)',
    r'\1\n                    superset_exercise_id=None,\n                    superset_exercise_slug_hint=None,\2',
    content
)


with open("backend/app/workouts/program_engine/template_sessions.py", "w") as f:
    f.write(content)

