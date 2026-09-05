from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from tests.workouts.program_engine.golden_fixtures import request, full_catalog
import json

source = request(
    available_training_days=5,
    training_experience="intermediate",
    training_age_months=24,
)
catalog = full_catalog()
res = generate_program(source, catalog, RULESET)
print(json.dumps(res.trace["rejected_splits"], indent=2))
