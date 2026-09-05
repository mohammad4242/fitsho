from pathlib import Path

path = Path("app/workouts/program_engine/session_duration.py")
content = path.read_text()
content = content.replace(
    "if direct_sets + 1 > sess_max:\n                break",
    "if direct_sets + 1 > sess_max:\n                print(f'DEBUG_BREAK: sets {direct_sets} > {sess_max} for {exercise.primary_muscle}')\n                break"
)
path.write_text(content)
