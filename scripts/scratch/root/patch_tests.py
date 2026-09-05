import re

with open("backend/tests/admin/test_training_template_api.py", "r") as f:
    content = f.read()

# Fix test_admin_rejects_unsafe_superset_pair
old_unsafe = """    for slot in payload["days"][0]["slots"][:2]:
        slot["intensity_method"] = "superset"
        slot["superset_group"] = "unsafe-compounds" """

new_unsafe = """    slot1 = payload["days"][0]["slots"][0]
    slot2 = payload["days"][0]["slots"][1]
    slot1["intensity_method"] = "superset"
    slot1["superset_exercise_id"] = slot2["exercise_id"]
    slot1["superset_exercise_slug"] = slot2["exercise_slug"]
    slot1["superset_exercise_name_en"] = slot2["exercise_name_en"]
    slot1["superset_exercise_name_fa"] = slot2["exercise_name_fa"]
    payload["days"][0]["slots"].pop(1)"""
content = content.replace(old_unsafe, new_unsafe)

# Fix test_admin_accepts_safe_advanced_methods
old_safe = """    first, second, third = payload["days"][0]["slots"][:3]
    first.update(
        exercise_id=str(curl_id),
        target_muscles=["biceps"],
        movement_pattern="elbow_flexion",
        intensity_method="superset",
        adaptation_priority="accessory",
        superset_group="arms-pair",
    )
    second.update(
        exercise_id=str(pushdown_id),
        target_muscles=["triceps"],
        movement_pattern="elbow_extension",
        intensity_method="superset",
        adaptation_priority="accessory",
        superset_group="arms-pair",
    )
    third.update(
        exercise_id=str(lateral_raise_id),
        target_muscles=["shoulders"],
        movement_pattern="shoulder_abduction",
        intensity_method="drop_set",
        adaptation_priority="accessory",
    )"""

new_safe = """    first, second, third = payload["days"][0]["slots"][:3]
    first.update(
        exercise_id=str(curl_id),
        target_muscles=["biceps"],
        movement_pattern="elbow_flexion",
        intensity_method="superset",
        adaptation_priority="accessory",
        superset_exercise_id=str(pushdown_id),
        superset_exercise_slug="fedb-1723-cable-triceps-pushdown",
        superset_exercise_name_en="Cable Triceps Pushdown",
        superset_exercise_name_fa="پشت بازو سیم‌کش",
    )
    payload["days"][0]["slots"].pop(1)  # Remove second slot, since it's merged into first
    
    third.update(
        exercise_id=str(lateral_raise_id),
        target_muscles=["shoulders"],
        movement_pattern="shoulder_abduction",
        intensity_method="drop_set",
        adaptation_priority="accessory",
    )"""
content = content.replace(old_safe, new_safe)


with open("backend/tests/admin/test_training_template_api.py", "w") as f:
    f.write(content)
