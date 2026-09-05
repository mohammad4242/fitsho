import re
with open("tests/workouts/program_engine/test_template_structure_propagation.py", "r") as f:
    text = f.read()

# Replace 2 days with 4 days for the upper/lower reference
text = text.replace('days_per_week=2,', 'days_per_week=4,')
text = text.replace('req = request(training_experience=TrainingExperience.INTERMEDIATE, available_training_days=2', 'req = request(training_experience=TrainingExperience.INTERMEDIATE, available_training_days=4')

# Add Day 3 and Day 4 by duplicating Day 1 and Day 2
days_code = """
            TemplateReferenceDay(
                day_number=3,
                title="Upper 2",
                focus=(MuscleGroup.CHEST,),
                structure_focus="upper",
                slots=(),
            ),
            TemplateReferenceDay(
                day_number=4,
                title="Lower 2",
                focus=(MuscleGroup.QUADRICEPS,),
                structure_focus="lower",
                slots=(),
            ),
        )
"""

text = re.sub(r'(\s+)TemplateReferenceSlot\(\s+exercise_id=uuid4\(\),\s+exercise_slug_hint="curl",.*?rest_seconds=90,\s+\),\s+\)\s+\),\s+\)', r'\g<0>' + days_code, text, flags=re.DOTALL)

with open("tests/workouts/program_engine/test_template_structure_propagation.py", "w") as f:
    f.write(text)

