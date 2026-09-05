import re

with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

content = content.replace(
    'volume_range.get("minimum_effective_sets")',
    'volume_range.get("acceptable_minimum", volume_range.get("minimum_effective_sets"))'
)

with open("tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content)
