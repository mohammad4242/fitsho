import re

with open("backend/app/admin/schemas.py", "r") as f:
    content = f.read()

# Replace min_length=5 if it exists
content = re.sub(r'slots: list\[AdminTrainingTemplateSlotWrite\] = Field\(min_length=\d+, max_length=\d+\)', 'slots: list[AdminTrainingTemplateSlotWrite] = Field(min_length=1)', content)

# Remove the custom validation loop
val_injection = """        for day in self.days:
            exercise_count = sum(2 if slot.intensity_method == TrainingTemplateMethod.SUPERSET else 1 for slot in day.slots)
            if exercise_count < 5 or exercise_count > 9:
                raise ValueError("Each day must contain exactly 5 to 9 runtime exercises (a superset counts as two)")
"""
content = content.replace(val_injection, "")

with open("backend/app/admin/schemas.py", "w") as f:
    f.write(content)
