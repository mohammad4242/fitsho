from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from tests.workouts.program_engine.golden_fixtures import full_catalog
from audit_phase11_benchmark import benchmark_profiles, profile_to_request
from app.training_templates.engine_reference import load_template_references
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import sys

engine = create_engine("postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test")
with Session(engine) as db:
    templates = load_template_references(db)
catalog = full_catalog()

def trace_calls(frame, event, arg):
    if event == "return" and isinstance(arg, str) and arg == "DAY_COUNT_MISMATCH":
        print(f"STRING RETURNED: {frame.f_code.co_name} at {frame.f_code.co_filename}:{frame.f_lineno}")
        import traceback
        traceback.print_stack(frame)
    return trace_calls

for p in benchmark_profiles():
    req = profile_to_request(p, enforce_matrix=False)
    sys.settrace(trace_calls)
    try:
        res = generate_program(req, catalog, RULESET, reference_templates=templates)
    finally:
        sys.settrace(None)
        
    if not res.is_success and "DAY_COUNT_MISMATCH" in res.errors:
        break
