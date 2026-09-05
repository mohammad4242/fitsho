import re

with open("backend/tests/admin/test_training_template_api.py", "r") as f:
    content = f.read()

content = content.replace(
    'assert "Superset cannot use the exact same exercise twice" in response.json()["detail"][0]["msg"]',
    'assert "Superset exercises must be different" in response.json()["detail"][0]["msg"]'
)
content = content.replace(
    'def test_admin_rejects_unsafe_superset_pair(',
    'def test_admin_rejects_identical_superset_pair('
)

with open("backend/tests/admin/test_training_template_api.py", "w") as f:
    f.write(content)
