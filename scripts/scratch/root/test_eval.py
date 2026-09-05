from enum import Enum
class TrainingTemplateMethod(str, Enum):
    STANDARD = "standard"
    SUPERSET = "superset"
    DROP_SET = "drop_set"
class Slot:
    def __init__(self, method):
        self.intensity_method = method
slots = [Slot(TrainingTemplateMethod.STANDARD) for _ in range(5)]
exercise_count = sum(2 if slot.intensity_method == TrainingTemplateMethod.SUPERSET else 1 for slot in slots)
print(exercise_count, exercise_count < 5 or exercise_count > 9)
