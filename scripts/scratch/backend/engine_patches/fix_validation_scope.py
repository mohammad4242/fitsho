from pathlib import Path

vp = Path("validation.py")
content = vp.read_text()
content = content.replace(
    "from app.workouts.program_engine.volume_policy import session_direct_volume_range\n        from app.exercises.enums import MuscleGroup\n",
    "",
)
content = content.replace(
    "from app.workouts.program_engine.volume_policy import weekly_direct_volume_range\n    for muscle_str, value in effective.items():",
    "for muscle_str, value in effective.items():",
)

# Add imports at the top
content = (
    "from app.workouts.program_engine.volume_policy import session_direct_volume_range, weekly_direct_volume_range\n"
    + content
)
vp.write_text(content)
