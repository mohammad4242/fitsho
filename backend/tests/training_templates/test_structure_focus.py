from app.exercises.enums import MuscleGroup
from app.training_templates.seed_data import TRAINING_PROGRAM_TEMPLATE_SEEDS

VALID_FOCUSES = {
    "full_body",
    "upper",
    "lower",
    "push",
    "pull",
    "chest",
    "back",
    "shoulders",
    "arms",
    "chest_triceps",
    "back_biceps",
    "shoulders_traps",
    "quadriceps_calves",
    "posterior_chain_core",
    "other",
}


STRICT_FOCUS_MUSCLES = {
    "chest_triceps": {MuscleGroup.CHEST, MuscleGroup.TRICEPS},
    "back_biceps": {MuscleGroup.BACK, MuscleGroup.BICEPS},
    "shoulders_traps": {MuscleGroup.SHOULDERS, MuscleGroup.TRAPS},
    "quadriceps_calves": {MuscleGroup.QUADRICEPS, MuscleGroup.CALVES},
    "posterior_chain_core": {
        MuscleGroup.HAMSTRINGS,
        MuscleGroup.GLUTES,
        MuscleGroup.CALVES,
        MuscleGroup.ABS,
    },
    "push": {MuscleGroup.CHEST, MuscleGroup.SHOULDERS, MuscleGroup.TRICEPS},
    "pull": {MuscleGroup.BACK, MuscleGroup.BICEPS, MuscleGroup.SHOULDERS, MuscleGroup.TRAPS},
}


def test_all_seeded_days_have_explicit_valid_structure_focus() -> None:
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        for day in template.days:
            assert day.structure_focus in VALID_FOCUSES
            assert day.structure_focus


def test_strict_structure_focus_only_contains_compatible_direct_muscles() -> None:
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        for day in template.days:
            allowed = STRICT_FOCUS_MUSCLES.get(day.structure_focus)
            if allowed is not None:
                assert set(day.direct_target_muscles) <= allowed


def test_full_body_days_preserve_full_body_focus() -> None:
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        for day in template.days:
            if "Full Body" in day.title_en:
                assert day.structure_focus == "full_body"


def test_structure_focus_is_explicit_and_independent_of_localized_title() -> None:
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        for day in template.days:
            assert day.structure_focus in VALID_FOCUSES
            assert day.title_en
            assert day.title_fa
