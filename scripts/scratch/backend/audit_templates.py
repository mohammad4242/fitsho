import sys
import json
import random
from collections import defaultdict

from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from tests.workouts.program_engine.golden_fixtures import full_catalog
from audit_phase11_benchmark import benchmark_profiles, profile_to_request, BenchmarkProfile
from app.exercises.enums import MuscleGroup
from app.training_templates.seed_data import TRAINING_PROGRAM_TEMPLATE_SEEDS
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.training_templates.engine_reference import load_template_references
from dataclasses import replace

def _trace_entry(result, stage):
    entries = result.program.decision_trace if result.program is not None else result.decision_trace
    for entry in entries:
        if entry.get("stage") == stage:
            return entry
    return None

def run_audit():
    engine = create_engine("postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test")
    with Session(engine) as db:
        templates = load_template_references(db)
        
    catalog = full_catalog()
    
    profiles = list(benchmark_profiles())
    
    # Let's add variants with priority muscles and intensity methods
    extra_profiles = []
    
    muscles = [
        (MuscleGroup.CHEST,),
        (MuscleGroup.BACK,),
        (MuscleGroup.QUADRICEPS,),
        (MuscleGroup.HAMSTRINGS,),
        (MuscleGroup.SHOULDERS,),
        (MuscleGroup.BICEPS, MuscleGroup.TRICEPS),
        (MuscleGroup.GLUTES,)
    ]
    
    for i, p in enumerate(profiles):
        # We replace priority muscles randomly for some profiles
        pm = muscles[i % len(muscles)]
        extra_profiles.append(replace(p, priority_muscles=pm, variant=p.variant + 100))
        
    profiles.extend(extra_profiles)
    
    print(f"Generated {len(profiles)} profiles for audit.")
    
    template_counts = defaultdict(int)
    
    for p in profiles:
        req = profile_to_request(p, enforce_matrix=False)
        res = generate_program(req, catalog, RULESET, reference_templates=templates)
        
        selection = _trace_entry(res, "template_selection") or {}
        selected = selection.get("selected")
        
        if selected:
            template_counts[selected] += 1
        else:
            template_counts["NO_TEMPLATE_OR_FALLBACK"] += 1
            
    all_slugs = {t.slug for t in TRAINING_PROGRAM_TEMPLATE_SEEDS}
    never_selected = all_slugs - set(template_counts.keys())
    
    audit = {
        "selected_counts": dict(template_counts),
        "never_selected": list(never_selected),
    }
    
    with open("audit_results.json", "w") as f:
        json.dump(audit, f, indent=2)
        
    print("\nTemplate Selection Frequencies:")
    for t, c in sorted(template_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {t}: {c}")
        
    print("\nNever Selected:")
    for t in sorted(never_selected):
        print(f"  {t}")
        
if __name__ == "__main__":
    run_audit()
