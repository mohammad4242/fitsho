import re
with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

content = content.replace("    else:\n        allowed_rom = frozenset()\n    else:\n        allowed_rom = frozenset()", "    else:\n        allowed_rom = frozenset()")

with open("tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content)
