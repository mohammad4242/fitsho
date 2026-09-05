from pathlib import Path
p = Path("app/workouts/program_engine/engine.py")
content = p.read_text()
content = content.replace("rejected_splits.append(rejected_attempt)", "print(f'Rejected exact {split.split_type}: {result.errors}'); rejected_splits.append(rejected_attempt)")
content = content.replace("rejected_splits.append(\n            {", "print(f'Rejected fallback {fallback_split.split_type}: {result.errors}'); rejected_splits.append(\n            {")
p.write_text(content)
