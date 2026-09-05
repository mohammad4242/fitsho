import re
import os

fpath = "tests/workouts/program_engine/test_template_selector_baseline.py"
with open(fpath, "r") as f:
    text = f.read()

# Remove fitness_goal argument from _template
text = re.sub(r'\s*fitness_goal:\s*str\s*=\s*"[^"]*",', '', text)
text = re.sub(r'\s*fitness_goal=fitness_goal,', '', text)
text = re.sub(r',\s*fitness_goal="[^"]*"', '', text)

with open(fpath, "w") as f:
    f.write(text)
