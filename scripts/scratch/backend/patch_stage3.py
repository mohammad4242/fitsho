with open("stage3_benchmark.py", "r") as f:
    lines = f.readlines()

new_profiles_code = """
from random import Random

def benchmark_profiles() -> tuple[BenchmarkProfile, ...]:
    goals = (
        Goal.STRENGTH,
        Goal.HYPERTROPHY,
        Goal.BODY_RECOMPOSITION,
        Goal.FAT_LOSS,
        Goal.GENERAL_FITNESS,
    )
    durations = (30, 45, 60, 75, 90, 120)
    locations = (TrainingLocation.GYM, TrainingLocation.HOME)
    home_setups = tuple(HomeTrainingSetup)
    cautions = tuple(TrainingCaution)
    muscles = tuple(MuscleGroup)
    impact_limits = tuple(ImpactLimit)
    load_limits = tuple(LoadLimit)
    balance_abilities = tuple(BalanceAbility)
    
    profiles = []
    
    count_per_cell = 25
    
    for experience, days in SUPPORTED_MATRIX:
        for variant in range(count_per_cell):
            rng = Random(f"fitsho:stage3:{experience}:{days}:{variant}")
            
            goal = rng.choice(goals)
            if experience == ExperienceLevel.FIRST_MONTH.value:
                goal = Goal.GENERAL_FITNESS
                
            location = rng.choice(locations)
            home_setup = None
            equipment_label = "full_gym"
            if location == TrainingLocation.HOME:
                home_setup = rng.choice(home_setups)
                equipment_label = f"home_{home_setup.value}"
                
            training_cautions = []
            impact_limit = None
            axial_load = None
            overhead = None
            balance = None
            
            if rng.random() < 0.2:
                training_cautions = [rng.choice(cautions)]
            
            if rng.random() < 0.1:
                impact_limit = rng.choice(impact_limits)
            if rng.random() < 0.1:
                axial_load = rng.choice(load_limits)
            if rng.random() < 0.1:
                overhead = rng.choice(load_limits)
            if rng.random() < 0.1:
                balance = rng.choice(balance_abilities)
                
            priority_muscles = []
            if rng.random() < 0.3:
                priority_muscles = [rng.choice(muscles)]
                
            profiles.append(BenchmarkProfile(
                profile_id=str(uuid5(NAMESPACE_URL, f"https://fitsho.test/stage3/{experience}/{days}/{variant}")) if 'uuid5' in globals() else str(variant),
                variant=variant,
                experience_level=ExperienceLevel(experience),
                resistance_days=days,
                goal=goal,
                priority_muscles=tuple(priority_muscles),
                body_analysis_priorities=(),
                sex=rng.choice(tuple(Sex)),
                duration_minutes=rng.choice(durations),
                equipment_label=equipment_label,
                training_location=location,
                home_setup=home_setup,
                available_equipment_override=None,
                training_cautions=tuple(training_cautions),
                impact_limit=impact_limit,
                axial_load_limit=axial_load,
                overhead_limit=overhead,
                balance_requirement=balance,
            ))
            
    return tuple(profiles)

NEGATIVE_PROFILES: tuple[BenchmarkProfile, ...] = ()

"""

# lines 125 to 258 are indices 124 to 258 (exclusive)
new_lines = lines[:124] + [new_profiles_code] + lines[258:]

with open("stage3_benchmark.py", "w") as f:
    f.writelines(new_lines)
