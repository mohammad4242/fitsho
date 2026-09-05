from pathlib import Path
path = Path("app/workouts/program_engine/volume_planner.py")
content = path.read_text()
content = content.replace(
    "sess_max * frequency,\n            )",
    "sess_max * frequency,\n            )\n            #print(f'muscle {muscle}, baseline {baseline_sets.get(muscle)}, split_max {split_maximum}, sess_max {sess_max}')"
)
path.write_text(content)
