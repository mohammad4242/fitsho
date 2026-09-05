import re

with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

content = content.replace("with ProcessPoolExecutor() as executor:", "with ProcessPoolExecutor(max_workers=4) as executor:")

with open("tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content)
