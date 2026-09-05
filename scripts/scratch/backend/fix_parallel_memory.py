import re

with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

# Make catalog and references global so they aren't pickled
global_setup = """
_GLOBAL_CATALOG_BY_SEX = {}
_GLOBAL_REFERENCES = None

def _worker(args):
    profile, determinism_repeats = args
    from app.workouts.program_engine.engine import generate_program
    from tests.workouts.program_engine.phase11_benchmark import profile_to_request, apply_catalog_constraints, RULESET, canonical_fingerprint, _case_record, _GLOBAL_CATALOG_BY_SEX, _GLOBAL_REFERENCES
    
    references = _GLOBAL_REFERENCES
    case_catalog = _GLOBAL_CATALOG_BY_SEX[profile.sex]
"""

content = re.sub(
    r'def _worker\(args\):\n    profile, references, case_catalog, determinism_repeats = args\n    from app\.workouts\.program_engine\.engine import generate_program\n    from tests\.workouts\.program_engine\.phase11_benchmark import \(\n        RULESET,\n        _case_record,\n        apply_catalog_constraints,\n        canonical_fingerprint,\n        profile_to_request,\n    \)',
    global_setup.strip('\n'),
    content
)

run_setup = """
    global _GLOBAL_CATALOG_BY_SEX, _GLOBAL_REFERENCES
    _GLOBAL_CATALOG_BY_SEX = catalog_by_sex
    _GLOBAL_REFERENCES = references

    args_list = [
        (profile, determinism_repeats)
        for profile in profiles
    ]"""

content = re.sub(
    r'    args_list = \[\n        \(profile, references, catalog_by_sex\[profile\.sex\], determinism_repeats\)\n        for profile in profiles\n    \]',
    run_setup.strip('\n'),
    content
)

with open("tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content)
