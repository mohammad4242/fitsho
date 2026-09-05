import re

with open("backend/tests/admin/test_training_template_api.py", "r") as f:
    content = f.read()

old_slot_payload = """def _slot_payload(slot: dict[str, object], **overrides: object) -> dict[str, object]:
    return {
        "exercise_id": slot["exercise"]["id"],
        "display_name_en": slot["placeholder_name_en"],
        "display_name_fa": slot["placeholder_name_fa"],
        "target_muscles": slot["target_muscles"],
        "movement_pattern": slot["movement_pattern"],
        "intensity_method": slot["intensity_method"],
        "adaptation_priority": "core",
        "superset_group": None,
        "sets": slot["sets"],
        "rep_min": slot["rep_min"],
        "rep_max": slot["rep_max"],
        "target_rir": slot["target_rir"],
        "rest_seconds": slot["rest_seconds"],
        **overrides,
    }"""

new_slot_payload = """def _slot_payload(slot: dict[str, object], **overrides: object) -> dict[str, object]:
    return {
        "exercise_id": slot["exercise"]["id"],
        "display_name_en": slot["placeholder_name_en"],
        "display_name_fa": slot["placeholder_name_fa"],
        "target_muscles": slot["target_muscles"],
        "movement_pattern": slot["movement_pattern"],
        "intensity_method": slot["intensity_method"],
        "adaptation_priority": "core",
        "superset_group": slot.get("superset_group"),
        "superset_exercise_id": slot.get("superset_exercise", {}).get("id") if slot.get("superset_exercise") else None,
        "sets": slot["sets"],
        "rep_min": slot["rep_min"],
        "rep_max": slot["rep_max"],
        "target_rir": slot["target_rir"],
        "rest_seconds": slot["rest_seconds"],
        **overrides,
    }"""

content = content.replace(old_slot_payload, new_slot_payload)

with open("backend/tests/admin/test_training_template_api.py", "w") as f:
    f.write(content)
