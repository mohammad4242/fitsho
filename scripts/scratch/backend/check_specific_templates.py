from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from tests.workouts.program_engine.golden_fixtures import full_catalog
from audit_phase11_benchmark import _variant_profile, profile_to_request
from app.profile.enums import ExperienceLevel
from app.training_templates.engine_reference import load_template_references
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import json

engine = create_engine("postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test")
with Session(engine) as db:
    templates = load_template_references(db)
catalog = full_catalog()

p = _variant_profile(ExperienceLevel.ADVANCED, 3, 1)
req = profile_to_request(p, enforce_matrix=False)
res = generate_program(req, catalog, RULESET, reference_templates=templates)

entries = res.program.decision_trace if res.program else res.decision_trace
selection = next((e for e in entries if e.get("stage") == "template_selection"), {})
print(f"selected: {selection.get('selected')}")
print("candidates:", [c["slug"] for c in selection.get("candidates", [])])
