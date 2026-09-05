import re

with open("backend/app/training_templates/service.py", "r") as f:
    content = f.read()

content = content.replace(
    'superset_group=slot_seed.superset_group,',
    'superset_group=slot_seed.superset_group, # HEY PRINT THIS\n'
)

with open("backend/app/training_templates/service.py", "w") as f:
    f.write(content)
