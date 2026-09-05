import re

with open("tests/workouts/program_engine/test_phase11_benchmark.py", "r") as f:
    content = f.read()

content = content.replace("cell: 25 for cell in SUPPORTED_MATRIX", "cell: 28 for cell in SUPPORTED_MATRIX")

with open("tests/workouts/program_engine/test_phase11_benchmark.py", "w") as f:
    f.write(content)
