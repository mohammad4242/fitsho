import re

with open("backend/app/workouts/program_engine/template_sessions.py", "r") as f:
    content = f.read()

content = content.replace(
    'return TemplateSessionBuild(',
    'print("RESOLUTIONS:", [(r.superset_group, r.requested_exercise_id, r.selected_exercise_id) for r in resolutions])\n    return TemplateSessionBuild('
)

with open("backend/app/workouts/program_engine/template_sessions.py", "w") as f:
    f.write(content)
