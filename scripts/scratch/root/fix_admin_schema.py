import re

with open("backend/app/admin/schemas.py", "r") as f:
    content = f.read()

content = content.replace(
    'if exercise_count < 5 or exercise_count > 9:',
    'if exercise_count < 4 or exercise_count > 9:'
)
content = content.replace(
    'raise ValueError("Each day must contain exactly 5 to 9 runtime exercises (a superset counts as two)")',
    'raise ValueError("Each day must contain exactly 4 to 9 runtime exercises (a superset counts as two)")'
)

with open("backend/app/admin/schemas.py", "w") as f:
    f.write(content)
