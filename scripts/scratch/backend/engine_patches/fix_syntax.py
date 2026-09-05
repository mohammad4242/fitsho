from pathlib import Path

sd = Path("session_duration.py")
content = sd.read_text()
content = content.replace(
    "has_near_equivalent\\nfrom app.workouts.program_engine.volume_policy import session_direct_volume_range(item, exercises)",
    "has_near_equivalent(item, exercises)",
)
content = content.replace(
    "from app.workouts.program_engine.exercise_semantics import has_near_equivalent\\nfrom app.workouts.program_engine.volume_policy import session_direct_volume_range",
    "from app.workouts.program_engine.exercise_semantics import has_near_equivalent",
)

content = content.replace(
    "from app.workouts.program_engine.exercise_semantics import has_near_equivalent",
    "from app.workouts.program_engine.exercise_semantics import has_near_equivalent\\nfrom app.workouts.program_engine.volume_policy import session_direct_volume_range",
)

sd.write_text(content)
