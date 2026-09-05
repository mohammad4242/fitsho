with open("backend/stage3_benchmark.py", "r") as f:
    content = f.read()

content = content.replace("sex=rng.choice(tuple(Sex))", "sex=rng.choice((Sex.MALE, Sex.FEMALE))")

with open("backend/stage3_benchmark.py", "w") as f:
    f.write(content)
