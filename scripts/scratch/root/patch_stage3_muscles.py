with open("backend/stage3_benchmark.py", "r") as f:
    content = f.read()

content = content.replace("muscles = tuple(MuscleGroup)", "muscles = tuple(MAJOR_MUSCLES)")

with open("backend/stage3_benchmark.py", "w") as f:
    f.write(content)
