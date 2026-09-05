import re

with open("backend/tests/admin/test_training_template_api.py", "r") as f:
    content = f.read()

content = content.replace(
    'template = template_response.json()["items"][0]',
    'template = template_response.json()["items"][0]\n    print("SLUG IS:", template["slug"])'
)

with open("backend/tests/admin/test_training_template_api.py", "w") as f:
    f.write(content)
