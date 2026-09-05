import re

with open("backend/tests/training_templates/test_engine_reference.py", "r") as f:
    content = f.read()

old_linked = """        linked_ids = {
            slot.exercise_id
            for day in reference.days
            for slot in day.slots
            if slot.exercise_id is not None
        }"""
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

content = content.replace(old_linked, new_linked)

with open("backend/tests/training_templates/test_engine_reference.py", "w") as f:
    f.write(content)
