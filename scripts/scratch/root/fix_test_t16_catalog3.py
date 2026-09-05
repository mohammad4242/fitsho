with open("backend/tests/training_templates/test_engine_reference.py", "r") as f:
    content = f.read()

old_str = """    linked_ids = {
        slot.exercise_id
        for day in reference.days
        for slot in day.slots
        if slot.exercise_id is not None
    }"""
new_str = """    linked_ids = {
        slot.exercise_id
        for day in reference.days
        for slot in day.slots
        if slot.exercise_id is not None
    } | {
        getattr(slot, 'superset_exercise_id', None)
        for day in reference.days
        for slot in day.slots
        if getattr(slot, 'superset_exercise_id', None) is not None
    }"""
content = content.replace(old_str, new_str)
with open("backend/tests/training_templates/test_engine_reference.py", "w") as f:
    f.write(content)
