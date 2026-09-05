import re
with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

bad = """    if variant == 10:
        training_cautions = (TrainingCaution.LOWER_BACK,)
    elif variant == 11:
        training_cautions = (TrainingCaution.SHOULDER,)
    elif variant == 12:
        training_cautions = (TrainingCaution.KNEE,)
    elif variant == 13:
        training_cautions = (TrainingCaution.WRIST,)
    elif variant == 14:
        allowed_rom = frozenset({"spinal_flexion"})
    elif variant == 15:
        allowed_rom = frozenset({"deep_knee_flexion"})"""

good = """    if variant == 10:
        training_cautions = (TrainingCaution.LOWER_BACK,)
    elif variant == 11:
        training_cautions = (TrainingCaution.SHOULDER,)
    elif variant == 12:
        training_cautions = (TrainingCaution.KNEE,)
    elif variant == 13:
        training_cautions = (TrainingCaution.WRIST,)

    if variant == 14:
        allowed_rom = frozenset({"spinal_flexion"})
    elif variant == 15:
        allowed_rom = frozenset({"deep_knee_flexion"})
    else:
        allowed_rom = frozenset()"""

content = content.replace(bad, good)

with open("tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content)
