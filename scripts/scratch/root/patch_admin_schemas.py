import re

with open("backend/app/admin/schemas.py", "r") as f:
    content = f.read()

content = content.replace(
    "slots: list[AdminTrainingTemplateSlotWrite] = Field(min_length=5, max_length=9)",
    "slots: list[AdminTrainingTemplateSlotWrite] = Field(min_length=1)"
)

val_injection = """        for day in self.days:
            exercise_count = sum(2 if slot.intensity_method == TrainingTemplateMethod.SUPERSET else 1 for slot in day.slots)
            if exercise_count < 5 or exercise_count > 9:
                raise ValueError("Each day must contain exactly 5 to 9 runtime exercises (a superset counts as two)")
"""

content = content.replace("        for day in self.days:\n            for slot in day.slots:", val_injection + "        for day in self.days:\n            for slot in day.slots:")

with open("backend/app/admin/schemas.py", "w") as f:
    f.write(content)

