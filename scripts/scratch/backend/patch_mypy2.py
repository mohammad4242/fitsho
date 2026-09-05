with open("backend/tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

content = content.replace("eq_override = cast(frozenset[Equipment] | None, eq_override_raw)", "eq_override = eq_override_raw")
content = content.replace("available_equipment_override=eq_override,", "available_equipment_override=cast(frozenset[Equipment] | None, eq_override),")

with open("backend/tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content)
