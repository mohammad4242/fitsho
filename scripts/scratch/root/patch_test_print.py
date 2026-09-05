import re

with open("backend/tests/admin/test_training_template_api.py", "r") as f:
    content = f.read()

content = content.replace(
    'response = client.put(',
    'print("SLOTS LENGTHS:", [len(day["slots"]) for day in payload["days"]])\n    response = client.put('
)

with open("backend/tests/admin/test_training_template_api.py", "w") as f:
    f.write(content)
