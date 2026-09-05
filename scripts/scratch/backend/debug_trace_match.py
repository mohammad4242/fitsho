from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from tests.workouts.program_engine.golden_fixtures import full_catalog
from audit_phase11_benchmark import benchmark_profiles, profile_to_request
from app.training_templates.engine_reference import load_template_references
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

engine = create_engine("postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test")
with Session(engine) as db:
    templates = load_template_references(db)
catalog = full_catalog()

for p in benchmark_profiles():
    req = profile_to_request(p, enforce_matrix=False)
    res = generate_program(req, catalog, RULESET, reference_templates=templates)
    if not res.is_success and "DAY_COUNT_MISMATCH" in res.errors:
        print(f"FOUND DAY_COUNT_MISMATCH for days={req.available_training_days}, level={req.training_experience}")
        break
    # also check if DAY_COUNT_INVARIANT_FAILED is in errors
    if not res.is_success and any("DAY_COUNT_INVARIANT_FAILED" in str(e) for e in res.errors):
        print(f"FOUND DAY_COUNT_INVARIANT_FAILED for days={req.available_training_days}, level={req.training_experience}")
