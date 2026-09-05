import re

with open("backend/tests/training_templates/test_engine_reference.py", "r") as f:
    content = f.read()

new_linked = """        linked_ids = {
            slot.exercise_id
            for day in reference.days
            for slot in day.slots
            if slot.exercise_id is not None
        } | {
            slot.superset_exercise_id
            for day in reference.days
            for slot in day.slots
            if getattr(slot, 'superset_exercise_id', None) is not None
        }"""

content = re.sub(
    r'        linked_ids = \{\n\s*slot\.exercise_id\n\s*for day in reference\.days\n\s*for slot in day\.slots\n\s*if slot\.exercise_id is not None\n\s*\}',
    new_linked,
    content
)

with open("backend/tests/training_templates/test_engine_reference.py", "w") as f:
    f.write(content)
