from app.exercises.enums import Equipment, ExerciseCautionTag, ExerciseType, PrescriptionMode
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, TrainingExperience
from app.workouts.program_engine.validation import validate_program
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def test_regression_profiles() -> None:
    profiles = [
        # 1. Beginner, Home Bodyweight, 3 days, 45 min
        {
            "training_experience": TrainingExperience.BEGINNER,
            "training_location": TrainingLocation.HOME,
            "available_equipment": [Equipment.BODYWEIGHT],
            "available_training_days": 3,
            "session_duration_minutes": 45,
            "primary_goal": Goal.GENERAL_FITNESS,
        },
        # 2. Intermediate, Gym, 4 days, 60 min, Hypertrophy
        {
            "training_experience": TrainingExperience.INTERMEDIATE,
            "training_location": TrainingLocation.GYM,
            "available_equipment": list(Equipment),
            "available_training_days": 4,
            "session_duration_minutes": 60,
            "primary_goal": Goal.HYPERTROPHY,
        },
        # 3. Advanced, Gym, 6 days, 90 min, Strength
        {
            "training_experience": TrainingExperience.ADVANCED,
            "training_location": TrainingLocation.GYM,
            "available_equipment": list(Equipment),
            "available_training_days": 6,
            "session_duration_minutes": 60,
            "primary_goal": Goal.STRENGTH,
        },
        # 4. Beginner, Home Dumbbells, 2 days, 30 min, Fat loss
        {
            "training_experience": TrainingExperience.BEGINNER,
            "training_location": TrainingLocation.HOME,
            "available_equipment": [Equipment.BODYWEIGHT, Equipment.DUMBBELL],
            "available_training_days": 2,
            "session_duration_minutes": 30,
            "primary_goal": Goal.FAT_LOSS,
        },
        # 5. Intermediate, Home, 4 days, 60 min, Muscle Gain, Single Caution
        {
            "training_experience": TrainingExperience.INTERMEDIATE,
            "training_location": TrainingLocation.HOME,
            "available_equipment": [
                Equipment.BODYWEIGHT,
                Equipment.DUMBBELL,
                Equipment.RESISTANCE_BAND,
            ],
            "available_training_days": 4,
            "session_duration_minutes": 60,
            "primary_goal": Goal.MUSCLE_GAIN,
            "blocked_caution_tags": [ExerciseCautionTag.LOWER_BACK_LOADING],
        },
        # 6. Advanced, Gym, 3 days, 60 min, Body Recomposition, Multiple Cautions
        {
            "training_experience": TrainingExperience.ADVANCED,
            "training_location": TrainingLocation.GYM,
            "available_equipment": list(Equipment),
            "available_training_days": 3,
            "session_duration_minutes": 60,
            "primary_goal": Goal.BODY_RECOMPOSITION,
            "blocked_caution_tags": [
                ExerciseCautionTag.SHOULDER_INTERNAL_ROTATION,
                ExerciseCautionTag.DEEP_KNEE_FLEXION,
            ],
        },
        # 7. Beginner, Gym, 4 days, 45 min, General Fitness
        {
            "training_experience": TrainingExperience.BEGINNER,
            "training_location": TrainingLocation.GYM,
            "available_equipment": list(Equipment),
            "available_training_days": 4,
            "session_duration_minutes": 45,
            "primary_goal": Goal.GENERAL_FITNESS,
        },
        # 8. Intermediate, Home Bodyweight, 6 days, 30 min (high frequency short)
        {
            "training_experience": TrainingExperience.INTERMEDIATE,
            "training_location": TrainingLocation.HOME,
            "available_equipment": [Equipment.BODYWEIGHT],
            "available_training_days": 6,
            "session_duration_minutes": 30,
            "primary_goal": Goal.GENERAL_FITNESS,
        },
        # 9. Advanced, Home Dumbbells, 4 days, 60 min, Strength
        {
            "training_experience": TrainingExperience.ADVANCED,
            "training_location": TrainingLocation.HOME,
            "available_equipment": [Equipment.BODYWEIGHT, Equipment.DUMBBELL],
            "available_training_days": 4,
            "session_duration_minutes": 60,
            "primary_goal": Goal.STRENGTH,
        },
        # 10. Beginner, Gym, 5 days, 60 min, Hypertrophy
        {
            "training_experience": TrainingExperience.BEGINNER,
            "training_location": TrainingLocation.GYM,
            "available_equipment": list(Equipment),
            "available_training_days": 5,
            "session_duration_minutes": 60,
            "primary_goal": Goal.HYPERTROPHY,
        },
    ]

    impossible_profile = {
        "training_experience": TrainingExperience.ADVANCED,
        "training_location": TrainingLocation.HOME,
        "available_equipment": [Equipment.BODYWEIGHT],
        "available_training_days": 7,
        "session_duration_minutes": 120,  # Very long bodyweight sessions, 7 days
        "primary_goal": Goal.MUSCLE_GAIN,
    }

    from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET

    catalog = full_catalog()
    for profile in profiles:
        req = request(**profile)
        result = generate_program(req, catalog, RULESET)
        assert result.is_success, f"Profile {profile} failed to generate: {result.errors}"
        program = result.program
        assert program is not None
        
        # Verify final validator has zero errors
        validation_report = validate_program(program, req, RULESET)
        assert not validation_report.errors, f"Validation errors found: {validation_report.errors}"

        # Verify exact requested days
        assert len(program.weekly_schedule) == req.available_training_days

        for day in program.weekly_schedule:
            # Verify no empty days
            assert len(day.exercises) > 0

            # Verify session duration strictly within +-10 of requested duration
            target_min = req.session_duration_minutes - 10
            target_max = req.session_duration_minutes + 10
            assert target_min <= day.estimated_duration_minutes <= target_max, (
                f"Duration {day.estimated_duration_minutes} OOB [{target_min}, {target_max}]"
            )

            for ex in day.exercises:
                # No unavailable equipment
                for eq in ex.equipment:
                    if eq != Equipment.BODYWEIGHT:
                        assert eq in req.available_equipment, f"Unavailable eq {eq}"
                
                # No blocked caution tags
                if req.blocked_caution_tags:
                    for tag in ex.caution_tags:
                        assert tag not in req.blocked_caution_tags, f"Blocked tag {tag}"
                        
                # No HARD_INCOMPATIBLE selected
                assert "RECOVERED_INCOMPATIBLE_SEMANTICS" not in ex.reason_codes
                assert "HARD_INCOMPATIBLE" not in ex.reason_codes
                
                # No inactive/non-programmable exercise
                assert ex.is_active is True
                assert ex.is_programmable is True
                
                # Valid reps-vs-duration prescription
                if ex.prescription_mode == PrescriptionMode.REPS:
                    assert ex.rep_min is not None and ex.rep_max is not None
                    assert 1 <= ex.rep_min <= ex.rep_max <= 100
                    assert ex.duration_min_seconds is None and ex.duration_max_seconds is None
                elif ex.prescription_mode == PrescriptionMode.DURATION:
                    assert ex.duration_min_seconds is not None and ex.duration_max_seconds is not None
                    assert 1 <= ex.duration_min_seconds <= ex.duration_max_seconds <= 3600
                    assert ex.rep_min is None and ex.rep_max is None
                
                # Verify that we don't dump 5 sets (unless explicitly strength and compound)
                if ex.sets >= 5:
                    assert req.primary_goal == Goal.STRENGTH, f"5 sets dumped on non-strength profile for exercise {ex.exercise_name}"
                    assert ex.exercise_type == ExerciseType.COMPOUND, f"5 sets dumped on non-compound exercise {ex.exercise_name}"
                    assert "STRENGTH_PRIMARY_COMPOUND" in ex.reason_codes, f"5 sets dumped on non-primary strength work {ex.exercise_name} (reasons: {ex.reason_codes})"

    req_imp = request(**impossible_profile)
    res_imp = generate_program(req_imp, catalog, RULESET)
    assert not res_imp.is_success, "Impossible profile generated a program"
