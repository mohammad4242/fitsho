import re

with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

# Add import
if "ProcessPoolExecutor" not in content:
    content = content.replace("import argparse", "import argparse\nfrom concurrent.futures import ProcessPoolExecutor")

worker = """
def _worker(args):
    profile, references, case_catalog, determinism_repeats = args
    from app.workouts.program_engine.engine import generate_program
    from tests.workouts.program_engine.phase11_benchmark import profile_to_request, apply_catalog_constraints, RULESET, canonical_fingerprint, _case_record
    
    request = profile_to_request(profile)
    request = apply_catalog_constraints(request, profile, case_catalog)
    result = generate_program(request, case_catalog, RULESET, reference_templates=references)
    repeated = [
        generate_program(request, case_catalog, RULESET, reference_templates=references)
        for _ in range(max(1, determinism_repeats))
    ]
    fingerprints = tuple(canonical_fingerprint(item) for item in [result] + repeated)
    return _case_record(profile, request, result, case_catalog, fingerprints)

"""
if "def _worker" not in content:
    # insert before run_benchmark
    content = content.replace("def run_benchmark(", worker + "def run_benchmark(")

loop = """    args_list = [
        (profile, references, catalog_by_sex[profile.sex], determinism_repeats)
        for profile in profiles
    ]
    with ProcessPoolExecutor() as executor:
        records = list(executor.map(_worker, args_list))"""
        
content = re.sub(
    r'    for profile in profiles:\n        request = profile_to_request\(profile\)\n        case_catalog = catalog_by_sex\[profile\.sex\]\n        request = apply_catalog_constraints\(request, profile, case_catalog\)\n        result = generate_program\(request, case_catalog, RULESET, reference_templates=references\)\n        repeated = \[\n            generate_program\(request, case_catalog, RULESET, reference_templates=references\)\n            for _ in range\(max\(1, determinism_repeats\)\)\n        \]\n        fingerprints = tuple\(canonical_fingerprint\(item\) for item in \[result\] \+ repeated\)\n        records\.append\(_case_record\(profile, request, result, case_catalog, fingerprints\)\)',
    loop,
    content
)

with open("tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content)
