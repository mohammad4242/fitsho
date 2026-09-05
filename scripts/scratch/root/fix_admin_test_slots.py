import re

with open("backend/tests/admin/test_training_template_api.py", "r") as f:
    content = f.read()

# assert len(first_day["slots"]) == 5
content = content.replace(
    'assert len(first_day["slots"]) == 5',
    'assert len(first_day["slots"]) == len(payload["days"][0]["slots"])'
)

with open("backend/tests/admin/test_training_template_api.py", "w") as f:
    f.write(content)
