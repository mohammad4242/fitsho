from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from tests.workouts.program_engine.golden_fixtures import full_catalog
from audit_phase11_benchmark import benchmark_profiles, profile_to_request
from app.training_templates.engine_reference import load_template_references
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import json

engine = create_engine("postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test")
with Session(engine) as db:
    templates = load_template_references(db)
catalog = full_catalog()

print(f"Loaded {len(templates)} templates")

for p in benchmark_profiles():
    req = profile_to_request(p, enforce_matrix=False)
    if req.available_training_days == 4 and req.training_experience.value == "beginner":
        print(f"Calling generate_program with {len(templates)} templates")
        res = generate_program(req, catalog, RULESET, reference_templates=templates)
        entries = res.program.decision_trace if res.program else res.decision_trace
        selection = next((e for e in entries if e.get("stage") == "template_selection"), {})
        
        if len(selection.get("candidates", [])) == 0:
            print(json.dumps(selection, indent=2))
            break
