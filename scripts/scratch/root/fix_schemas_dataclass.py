import re

with open("backend/app/workouts/program_engine/schemas.py", "r") as f:
    content = f.read()

content = content.replace("superset_exercise_id: UUID | None = None", "superset_exercise_id: UUID | None")
content = content.replace("superset_exercise_slug_hint: str | None = None", "superset_exercise_slug_hint: str | None")

with open("backend/app/workouts/program_engine/schemas.py", "w") as f:
    f.write(content)
