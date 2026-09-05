import re

with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

# I will move variants 20, 21, 22, 23, 24, 25 to be inside 10..19 where some variants are just redundant or have other things.
# Let's check what 16..19 currently are.

