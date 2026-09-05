with open("backend/analyze_stage4.py", "r") as f:
    content = f.read()

content = content.replace("def analyze_subgroups(benchmark_json_path: str, output_md_path: str):", "def analyze_subgroups(benchmark_json_path: str, output_md_path: str) -> None:")
content = content.replace("subgroups = defaultdict(lambda: defaultdict(lambda: {\"total\": 0, \"success\": 0}))", "subgroups: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: {\"total\": 0, \"success\": 0}))")
content = content.replace("def add(group, key):", "def add(group: str, key: object) -> None:\n            key = str(key)")

with open("backend/analyze_stage4.py", "w") as f:
    f.write(content)

with open("backend/tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content2 = f.read()

content2 = content2.replace('        label, home_setup, eq_override = gym_setups[variant % len(gym_setups)]', '        label, home_setup_raw, eq_override_raw = gym_setups[variant % len(gym_setups)]\n        home_setup = None\n        eq_override = eq_override_raw')
content2 = content2.replace('int(cast(Mapping[str, object], r.get("quality", {})).get("substitution_count", 0))', 'int(str(cast(Mapping[str, object], r.get("quality", {})).get("substitution_count", 0)))')

with open("backend/tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content2)

