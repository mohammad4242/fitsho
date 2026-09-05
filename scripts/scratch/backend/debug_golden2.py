import pytest
from app.workouts.program_engine.engine import _program_for_split
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.splits import split_strategies_for
from tests.workouts.program_engine.golden_fixtures import golden_scenarios, request, full_catalog

source = request(
    available_training_days=5,
    training_experience="intermediate",
    training_age_months=24,
)
catalog = full_catalog()
norm = normalize_request(source, RULESET)
splits = split_strategies_for(norm, catalog, RULESET)
for split in splits:
    print(f"Trying split: {split.split.split_type}")
    res = _program_for_split(norm, split.split, catalog, RULESET)
    if not res:
        print("  Failed to generate!")
    else:
        print("  Succeeded!")
        break
