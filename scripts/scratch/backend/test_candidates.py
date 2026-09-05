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

profiles = list(benchmark_profiles())
zero_candidates = 0
for p in profiles:
    req = profile_to_request(p, enforce_matrix=False)
    res = generate_program(req, catalog, RULESET, reference_templates=templates)
    
    entries = res.program.decision_trace if res.program else res.decision_trace
    selection = next((e for e in entries if e.get("stage") == "template_selection"), {})
    
    if len(selection.get("candidates", [])) == 0 and selection.get("rejection_category") != "NO_DAYS_LEVEL_CANDIDATE":
        print(f"ZERO CANDIDATES BUT HAD TEMPLATES IN CELL: days={req.available_training_days}, level={req.training_experience}")
        print("Hard rejections summary:")
        for r in selection.get("hard_rejections", []):
            if "DAYS_MISMATCH" not in r["reason_codes"] and "EXPERIENCE_LEVEL_MISMATCH" not in r["reason_codes"]:
                print(f"  {r['slug']}: {r['reason_codes']}")
        zero_candidates += 1

print(f"Total zero candidates: {zero_candidates}")
