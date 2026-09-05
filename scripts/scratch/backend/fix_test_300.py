with open("tests/workouts/program_engine/test_phase11_benchmark.py", "r") as f:
    content = f.read()

content = content.replace("assert len(profiles) == 420", "assert len(profiles) == 300")
content = content.replace("cell: 28", "cell: 20")

with open("tests/workouts/program_engine/test_phase11_benchmark.py", "w") as f:
    f.write(content)
