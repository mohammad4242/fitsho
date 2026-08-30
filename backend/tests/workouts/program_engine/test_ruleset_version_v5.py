from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET


def test_material_survival_semantics_use_ruleset_v5() -> None:
    assert RULESET.version == "resistance_training_v5"
