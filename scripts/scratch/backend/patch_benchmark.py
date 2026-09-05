import re

with open("backend/tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

# 1. Add fields to BenchmarkProfile
old_dataclass = """    physical_limitation_note: str | None = None"""
new_dataclass = """    physical_limitation_note: str | None = None
    training_age_months: int | None = None
    allowed_range_of_motion: frozenset[str] = frozenset()"""
content = content.replace(old_dataclass, new_dataclass)

# 2. Replace _variant_profile
old_variant_profile = content[content.find("def _variant_profile"):content.find("def benchmark_profiles()")]

new_variant_profile = """def _variant_profile(experience: ExperienceLevel, days: int, variant: int) -> BenchmarkProfile:
    goals = (Goal.STRENGTH, Goal.HYPERTROPHY, Goal.BODY_RECOMPOSITION, Goal.FAT_LOSS, Goal.GENERAL_FITNESS)
    goal = goals[variant % len(goals)]
    if experience is ExperienceLevel.FIRST_MONTH:
        goal = Goal.GENERAL_FITNESS
        
    locations = (TrainingLocation.GYM, TrainingLocation.HOME)
    location = locations[variant % 2]
    
    home_setups = (
        ("home_bw", HomeTrainingSetup.BODYWEIGHT_ONLY, frozenset({Equipment.BODYWEIGHT})),
        ("home_db", HomeTrainingSetup.DUMBBELLS_AVAILABLE, frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL})),
        ("home_band", HomeTrainingSetup.BODYWEIGHT_ONLY, frozenset({Equipment.BODYWEIGHT, Equipment.RESISTANCE_BAND})),
        ("home_db_bench", HomeTrainingSetup.DUMBBELLS_AVAILABLE, frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.BENCH})),
        ("home_db_pullup", HomeTrainingSetup.DUMBBELLS_AVAILABLE, frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.PULL_UP_BAR})),
        ("home_band_pullup", HomeTrainingSetup.BODYWEIGHT_ONLY, frozenset({Equipment.BODYWEIGHT, Equipment.RESISTANCE_BAND, Equipment.PULL_UP_BAR})),
        ("home_all", HomeTrainingSetup.DUMBBELLS_AVAILABLE, frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.RESISTANCE_BAND, Equipment.BENCH, Equipment.PULL_UP_BAR})),
    )
    gym_setups = (
        ("full_gym", None, None),
        ("limited_gym", None, frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL, Equipment.BENCH, Equipment.BARBELL, Equipment.CABLE})),
    )
    
    if location == TrainingLocation.HOME:
        label, home_setup, eq_override = home_setups[variant % len(home_setups)]
    else:
        label, home_setup, eq_override = gym_setups[variant % len(gym_setups)]
        
    training_ages = {
        ExperienceLevel.FIRST_MONTH: (0, 1),
        ExperienceLevel.BEGINNER: (2, 6, 12),
        ExperienceLevel.INTERMEDIATE: (18, 24, 36, 48),
        ExperienceLevel.ADVANCED: (60, 84, 120),
    }
    age_options = training_ages[experience]
    training_age = age_options[variant % len(age_options)]
    
    duration = 45 if variant % 3 == 0 else (90 if variant % 3 == 1 else 60)
    sexes = (Sex.MALE, Sex.FEMALE, None)
    sex = sexes[variant % len(sexes)]
    
    rom_option = (variant // 5) % 3
    if rom_option == 1:
        allowed_rom = frozenset({"spinal_flexion"})
    elif rom_option == 2:
        allowed_rom = frozenset({"deep_knee_flexion"})
    else:
        allowed_rom = frozenset()
        
    return BenchmarkProfile(
        profile_id=_profile_id(experience, days, variant),
        variant=variant,
        experience_level=experience,
        resistance_days=days,
        goal=goal,
        priority_muscles=() if variant % 2 == 0 else (MuscleGroup.CHEST,),
        body_analysis_priorities=(),
        sex=sex,
        duration_minutes=duration,
        equipment_label=label,
        training_location=location,
        home_setup=home_setup,
        available_equipment_override=eq_override,
        training_age_months=training_age,
        allowed_range_of_motion=allowed_rom,
    )

"""
content = content.replace(old_variant_profile, new_variant_profile)

# 3. Increase variant range in benchmark_profiles
content = content.replace("for variant in range(5)", "for variant in range(25)")

# 4. Modify profile_to_request to pass training_age_months and allowed_range_of_motion
old_training_age = """        training_age_months={
            ExperienceLevel.FIRST_MONTH: 0,
            ExperienceLevel.BEGINNER: 6,
            ExperienceLevel.INTERMEDIATE: 24,
            ExperienceLevel.ADVANCED: 60,
        }[profile.experience_level],"""
new_training_age = """        training_age_months=profile.training_age_months if profile.training_age_months is not None else {
            ExperienceLevel.FIRST_MONTH: 0,
            ExperienceLevel.BEGINNER: 6,
            ExperienceLevel.INTERMEDIATE: 24,
            ExperienceLevel.ADVANCED: 60,
        }[profile.experience_level],"""
content = content.replace(old_training_age, new_training_age)

old_override = """    if profile.available_equipment_override is not None:
        override_values["available_equipment"] = profile.available_equipment_override"""
new_override = """    if profile.available_equipment_override is not None:
        override_values["available_equipment"] = profile.available_equipment_override
    if profile.allowed_range_of_motion:
        override_values["allowed_range_of_motion"] = profile.allowed_range_of_motion"""
content = content.replace(old_override, new_override)

with open("backend/tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content)
