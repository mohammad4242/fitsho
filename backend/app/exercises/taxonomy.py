from app.exercises.enums import BodyRegion, MuscleGroup

MUSCLES_BY_REGION: dict[BodyRegion, frozenset[MuscleGroup]] = {
    BodyRegion.UPPER_BODY: frozenset(
        {
            MuscleGroup.CHEST,
            MuscleGroup.BACK,
            MuscleGroup.SHOULDERS,
            MuscleGroup.BICEPS,
            MuscleGroup.TRICEPS,
            MuscleGroup.TRAPS,
        }
    ),
    BodyRegion.LOWER_BODY: frozenset(
        {
            MuscleGroup.GLUTES,
            MuscleGroup.QUADRICEPS,
            MuscleGroup.HAMSTRINGS,
            MuscleGroup.ADDUCTORS,
            MuscleGroup.CALVES,
        }
    ),
    BodyRegion.CORE: frozenset(
        {
            MuscleGroup.ABS,
            MuscleGroup.OBLIQUES,
            MuscleGroup.LOWER_BACK,
        }
    ),
}
