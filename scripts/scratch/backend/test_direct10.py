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
    if p.resistance_days == 5 and p.experience == "first_month":
        req = profile_to_request(p, enforce_matrix=False)
        res = generate_program(req, catalog, RULESET, reference_templates=templates)
        print("UNCONDITIONAL ERRORS:", res.errors)
        break
