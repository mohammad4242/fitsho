import re
with open("backend/tests/training_templates/test_engine_reference.py", "r") as f:
    content = f.read()

content = content.replace(
    'assert len(grouped) == 2, tuple(',
    '''for day in reference.days:
            for slot in day.slots:
                if slot.intensity_method == "superset":
                    print("REFERENCE SLOT:", slot.exercise_slug_hint, slot.superset_group, slot.superset_exercise_slug_hint)
        assert len(grouped) == 2, tuple('''
)
with open("backend/tests/training_templates/test_engine_reference.py", "w") as f:
    f.write(content)
