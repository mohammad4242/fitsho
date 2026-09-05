import re

with open("backend/tests/admin/test_training_template_api.py", "r") as f:
    content = f.read()

old_rejects = """    payload = _template_payload_for_catalog(db)
    payload["supported_levels"] = ["advanced"]
    payload["intensity_methods"] = ["standard", "superset"]
    slot = payload["days"][0]["slots"][0]
    slot["intensity_method"] = "superset"
    slot["superset_exercise_id"] = payload["days"][0]["slots"][1]["exercise_id"]
    del payload["days"][0]["slots"][1]

    response = client.post(
        "/api/v1/admin/training-program-templates",
        headers=ORIGIN,
        json=payload,
    )

    assert response.status_code == 422
    assert "Superset pair is unsafe" in response.json()["detail"][0]["msg"]"""

new_rejects = """    payload = _template_payload_for_catalog(db)
    payload["supported_levels"] = ["advanced"]
    payload["intensity_methods"] = ["standard", "superset"]
    slot = payload["days"][0]["slots"][0]
    slot["intensity_method"] = "superset"
    # Try to superset the exact same exercise twice!
    slot["superset_exercise_id"] = slot["exercise_id"]
    del payload["days"][0]["slots"][1]

    response = client.post(
        "/api/v1/admin/training-program-templates",
        headers=ORIGIN,
        json=payload,
    )

    assert response.status_code == 422
    assert "Superset cannot use the exact same exercise twice" in response.json()["detail"][0]["msg"]"""

content = content.replace(old_rejects, new_rejects)

with open("backend/tests/admin/test_training_template_api.py", "w") as f:
    f.write(content)
