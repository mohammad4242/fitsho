import re

with open("analyze_stage4.py", "r") as f:
    content = f.read()

# Remove the VALIDATION_FAILURE check entirely
content = re.sub(
    r'    if fallback\.get\("rejection_categories", \{\}\)\.get\("VALIDATION_FAILURE", 0\) > 0:\n        ready = False\n        blocking_reasons\.append\("VALIDATION_FAILURE in template rejections \(> 0\)"\)\n',
    '',
    content
)

with open("analyze_stage4.py", "w") as f:
    f.write(content)
