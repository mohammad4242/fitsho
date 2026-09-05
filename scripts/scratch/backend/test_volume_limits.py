from app.workouts.program_engine.volume_policy import session_direct_volume_range, weekly_direct_volume_range
from app.exercises.enums import MuscleGroup

print("LARGE, 24 mo")
print(weekly_direct_volume_range(MuscleGroup.CHEST, 24))
print(session_direct_volume_range(MuscleGroup.CHEST, 24))

print("SMALL, 24 mo")
print(weekly_direct_volume_range(MuscleGroup.BICEPS, 24))
print(session_direct_volume_range(MuscleGroup.BICEPS, 24))
