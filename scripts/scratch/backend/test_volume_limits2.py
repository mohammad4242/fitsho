from app.workouts.program_engine.volume_policy import session_direct_volume_range, weekly_direct_volume_range
from app.exercises.enums import MuscleGroup
print(weekly_direct_volume_range(MuscleGroup.TRAPS, 24))
