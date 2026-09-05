import re

with open("backend/app/training_templates/service.py", "r") as f:
    content = f.read()

content = content.replace(
    'day.slots.append(',
    'print("SEEDING SLOT:", slot_seed.superset_group)\\n            day.slots.append('
)

with open("backend/app/training_templates/service.py", "w") as f:
    f.write(content)
