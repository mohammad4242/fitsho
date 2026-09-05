import re

with open("backend/app/training_templates/service.py", "r") as f:
    content = f.read()

content = content.replace("superset_group=None,", "superset_group=slot_seed.superset_group,")

with open("backend/app/training_templates/service.py", "w") as f:
    f.write(content)
