import re

with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    code = f.read()

# Increase variant range from 25 to 26 (to add wrist caution and maybe more)
code = code.replace("for variant in range(25)", "for variant in range(28)")

# Add wrist caution
cautions_patch = """
    if variant == 20:
        training_cautions = (TrainingCaution.LOWER_BACK,)
    elif variant == 21:
        training_cautions = (TrainingCaution.SHOULDER,)
    elif variant == 22:
        training_cautions = (TrainingCaution.KNEE,)
    elif variant == 25:
        training_cautions = (TrainingCaution.WRIST,)
"""
code = re.sub(
    r'    if variant == 20:\n        training_cautions = \(TrainingCaution\.LOWER_BACK,\)\n    elif variant == 21:\n        training_cautions = \(TrainingCaution\.SHOULDER,\)\n    elif variant == 22:\n        training_cautions = \(TrainingCaution\.KNEE,\)',
    cautions_patch.strip('\n'),
    code
)

# Add priority muscle variation
priorities_patch = """
    pm_choices = (
        (),
        (MuscleGroup.CHEST,),
        (MuscleGroup.GLUTES,),
        (MuscleGroup.BACK,),
        (MuscleGroup.SHOULDERS,),
        (MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES),
    )
    priority_muscles = pm_choices[variant % len(pm_choices)]
"""
code = code.replace(
    'priority_muscles=() if variant % 2 == 0 else (MuscleGroup.CHEST,),',
    'priority_muscles=priority_muscles,'
)
code = re.sub(
    r'    return BenchmarkProfile\(',
    priorities_patch.lstrip('\n') + '\n    return BenchmarkProfile(',
    code
)

with open("tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(code)
