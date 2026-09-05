import re

with open("backend/tests/admin/test_training_template_api.py", "r") as f:
    content = f.read()

old_rejects = """    for slot in payload["days"][0]["slots"][:2]:
        slot["intensity_method"] = "superset"
        slot["superset_group"] = "unsafe-compounds"
"""
new_rejects = """    slot = payload["days"][0]["slots"][0]
    slot["intensity_method"] = "superset"
    slot["superset_exercise_id"] = payload["days"][0]["slots"][1]["exercise_id"]
    del payload["days"][0]["slots"][1]
"""
content = content.replace(old_rejects, new_rejects)

old_accepts = """    first, second, third = payload["days"][0]["slots"][:3]
    first.update(
        exercise_id=str(curl_id),
        intensity_method="superset",
        superset_group="safe-isolation",
    )
    second.update(
        exercise_id=str(pushdown_id),
        intensity_method="superset",
        superset_group="safe-isolation",
    )"""
new_accepts = """    first, second, third = payload["days"][0]["slots"][:3]
    first.update(
        exercise_id=str(curl_id),
        intensity_method="superset",
        superset_exercise_id=str(pushdown_id),
    )
    # The second slot is the drop set slot!
    second.update(
        exercise_id=str(lateral_raise_id),
        intensity_method="drop_set",
    )
    # Delete the third slot since the first slot now counts as 2, and second is drop_set.
    del payload["days"][0]["slots"][2]
"""
content = content.replace(old_accepts, new_accepts)

old_accepts_drop = """    third.update(
        exercise_id=str(lateral_raise_id),
        intensity_method="drop_set",
    )"""
content = content.replace(old_accepts_drop, "")

with open("backend/tests/admin/test_training_template_api.py", "w") as f:
    f.write(content)
