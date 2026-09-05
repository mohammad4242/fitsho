with open("backend/tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

content = content.replace("label, home_setup_raw, cast(frozenset[Equipment] | None, eq_override_raw) = gym_setups[variant % len(gym_setups)]", "label, home_setup_raw, eq_override_raw = gym_setups[variant % len(gym_setups)]")

with open("backend/tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content)
