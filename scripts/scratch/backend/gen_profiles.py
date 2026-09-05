from app.workouts.program_engine.enums import Goal, ImpactLimit, LoadLimit, BalanceAbility, PhysicalJobDemand, RecoveryRating
from app.exercises.enums import Equipment, MovementPattern, MuscleGroup, ExerciseCautionTag
from app.profile.enums import HomeTrainingSetup, TrainingLocation, Sex, TrainingCaution, ExperienceLevel
from app.workouts.program_engine.schemas import ProgramGenerationRequest

HOME_COMBINATIONS = (
    ("home_bw", HomeTrainingSetup.BODYWEIGHT_ONLY, frozenset({Equipment.BODYWEIGHT})),
    ("home_db", HomeTrainingSetup.DUMBBELLS_AVAILABLE, frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL})),
    ("home_band", HomeTrainingSetup.BODYWEIGHT_ONLY, frozenset({Equipment.BODYWEIGHT, Equipment.RESISTANCE_BAND})),
    ("home_db_bench", HomeTrainingSetup.DUMBBELLS_AVAILABLE, frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.BENCH})),
    ("home_db_pullup", HomeTrainingSetup.DUMBBELLS_AVAILABLE, frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.PULL_UP_BAR})),
    ("home_band_pullup", HomeTrainingSetup.BODYWEIGHT_ONLY, frozenset({Equipment.BODYWEIGHT, Equipment.RESISTANCE_BAND, Equipment.PULL_UP_BAR})),
    ("home_all", HomeTrainingSetup.DUMBBELLS_AVAILABLE, frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.RESISTANCE_BAND, Equipment.BENCH, Equipment.PULL_UP_BAR})),
)

GYM_COMBINATIONS = (
    ("full_gym", None, None),
    ("limited_gym", None, frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.BENCH, Equipment.BARBELL, Equipment.CABLE})),
)

print(len(HOME_COMBINATIONS))
