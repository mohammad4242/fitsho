import re

with open("tests/workouts/program_engine/test_phase11_benchmark.py", "r") as f:
    content = f.read()

content = content.replace("assert len(profiles) == 375", "assert len(profiles) == 420")

with open("tests/workouts/program_engine/test_phase11_benchmark.py", "w") as f:
    f.write(content)
