with open("tests/workouts/program_engine/test_phase11_benchmark.py", "r") as f:
    content = f.read()

content = content.replace("    category = benchmark._category(\n        result,", "    category = benchmark._category(\n        cast(ProgramGenerationResult, result),")

with open("tests/workouts/program_engine/test_phase11_benchmark.py", "w") as f:
    f.write(content)
