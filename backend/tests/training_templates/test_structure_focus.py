from app.exercises.enums import MuscleGroup as M
from app.training_templates.seed_data import TRAINING_PROGRAM_TEMPLATE_SEEDS


def test_all_seeded_template_days_have_explicit_valid_structure_focus():
    valid_focuses = {
        "full_body",
        "upper",
        "lower",
        "push",
        "pull",
        "chest_triceps",
        "back_biceps",
        "shoulders_traps",
        "quadriceps_calves",
        "posterior_chain_core",
        "other",
    }
    
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        for day in template.days:
            assert day.structure_focus in valid_focuses, f"Invalid focus {day.structure_focus} for {day.title_en}"

def test_legs_day_with_quads_hams_glutes_is_lower():
    # Legs A/B with quads + hamstrings + glutes => lower
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        for day in template.days:
            if "Legs" in day.title_en:
                muscles = set(day.direct_target_muscles)
                if {M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES}.issubset(muscles):
                    # It should be lower, except if it explicitly says Quadriceps
                    if "Quadriceps" not in day.title_en and "Posterior" not in day.title_en:
                        assert day.structure_focus == "lower", f"{day.title_en} should be lower, got {day.structure_focus}"

def test_true_quadriceps_calves_is_quadriceps_calves():
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        for day in template.days:
            if "Quadriceps" in day.title_en or "Squat" in day.title_en:
                assert day.structure_focus == "quadriceps_calves", f"{day.title_en} should be quadriceps_calves"

def test_true_posterior_chain_core_is_posterior_chain():
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        for day in template.days:
            if "Posterior" in day.title_en or "Deadlift" in day.title_en or "Hamstrings + Glutes" in day.title_en:
                assert day.structure_focus == "posterior_chain_core", f"{day.title_en} should be posterior_chain_core"

def test_full_body_is_full_body():
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        for day in template.days:
            if "Full Body" in day.title_en:
                assert day.structure_focus == "full_body"
