import pytest
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from tests.workouts.program_engine.golden_fixtures import golden_scenarios, request, full_catalog

source = request(
    available_training_days=5,
    training_experience="intermediate",
    training_age_months=24,
)
catalog = full_catalog()
result = generate_program(source, catalog, RULESET)
print("Errors:", result.errors)
if result.program:
    print("Program generated successfully")
else:
    print("Program generation failed")
