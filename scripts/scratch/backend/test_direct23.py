import sys
import traceback
from app.workouts.program_engine.schemas import ProgramGenerationResult

original_init = ProgramGenerationResult.__init__
def new_init(self, program=None, error_code=None, errors=(), **kwargs):
    if "DAY_COUNT_MISMATCH" in errors:
        print("BINGO! STACK TRACE:")
        traceback.print_stack()
    original_init(self, program=program, error_code=error_code, errors=errors, **kwargs)

ProgramGenerationResult.__init__ = new_init

from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from tests.workouts.program_engine.golden_fixtures import full_catalog
from audit_phase11_benchmark import benchmark_profiles, profile_to_request
from app.training_templates.engine_reference import load_template_references
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import dataclasses

engine = create_engine("postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test")
with Session(engine) as db:
    templates = load_template_references(db)
catalog = full_catalog()

for p in benchmark_profiles():
    req = profile_to_request(p, enforce_matrix=False)
    generate_program(req, catalog, RULESET, reference_templates=templates)
