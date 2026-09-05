from random import Random
import uuid
from typing import Iterator

from app.profile.enums import ExperienceLevel, Goal, Sex, TrainingLocation, HomeTrainingSetup, TrainingCaution, FitnessGoal
from app.workouts.program_engine.enums import ImpactLimit, LoadLimit, BalanceAbility
from app.exercises.enums import MuscleGroup, MovementPattern, ExerciseCautionTag
from tests.workouts.program_engine.phase11_benchmark import BenchmarkProfile, SUPPORTED_MATRIX

def _uuid(seed_str: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://fitsho.test/stage3/{seed_str}"))

def generate_stage3_profiles(count_per_cell: int = 25) -> list[BenchmarkProfile]:
    profiles = []
    
    goals = list(Goal)
    durations = [30, 45, 60, 75, 90, 120]
    locations = [TrainingLocation.GYM, TrainingLocation.HOME]
    home_setups = list(HomeTrainingSetup)
    cautions = list(TrainingCaution)
    muscles = list(MuscleGroup)
    impact_limits = list(ImpactLimit)
    load_limits = list(LoadLimit)
    balance_abilities = list(BalanceAbility)
    
    for experience, days in SUPPORTED_MATRIX:
        for variant in range(count_per_cell):
            rng = Random(f"fitsho:stage3:{experience}:{days}:{variant}")
            
            goal = rng.choice(goals)
            if experience == ExperienceLevel.FIRST_MONTH.value:
                # Force realistic goal for first month? Or leave it open?
                pass
                
            location = rng.choice(locations)
            home_setup = None
            equipment_label = "full_gym"
            if location == TrainingLocation.HOME:
                home_setup = rng.choice(home_setups)
                equipment_label = f"home_{home_setup.value}"
            
            # Cautions & Limits
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
                profile_id=_uuid(f"{experience}:{days}:{variant}"),
                variant=variant,
                experience_level=ExperienceLevel(experience),
                resistance_days=days,
                goal=goal,
                priority_muscles=tuple(priority_muscles),
                body_analysis_priorities=(),
                sex=rng.choice(list(Sex)),
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
            
    return profiles

if __name__ == "__main__":
    p = generate_stage3_profiles()
    print(f"Generated {len(p)} profiles.")
