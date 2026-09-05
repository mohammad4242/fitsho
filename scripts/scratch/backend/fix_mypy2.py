with open("tests/workouts/program_engine/test_phase11_benchmark.py", "r") as f:
    content = f.read()

content = content.replace("benchmark._category(result", "benchmark._category(cast(ProgramGenerationResult, result)")
content = content.replace("benchmark._construction_path(result", "benchmark._construction_path(cast(ProgramGenerationResult, result)")

with open("tests/workouts/program_engine/test_phase11_benchmark.py", "w") as f:
    f.write(content)
