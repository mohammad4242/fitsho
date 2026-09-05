import re

with open("backend/app/admin/schemas.py", "r") as f:
    content = f.read()

content = content.replace(
    'exercise_count = sum(2 if slot.intensity_method == TrainingTemplateMethod.SUPERSET else 1 for slot in day.slots)',
    'print("METHODS:", [slot.intensity_method for slot in day.slots])\n            exercise_count = sum(2 if slot.intensity_method == TrainingTemplateMethod.SUPERSET else 1 for slot in day.slots)'
)

with open("backend/app/admin/schemas.py", "w") as f:
    f.write(content)
