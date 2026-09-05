import re

with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

sequential_loop = """
    records = []
    print(f"Running benchmark for {len(profiles)} profiles...")
    for i, profile in enumerate(profiles):
        request = profile_to_request(profile)
        case_catalog = catalog_by_sex[profile.sex]
        request = apply_catalog_constraints(request, profile, case_catalog)
        result = generate_program(request, case_catalog, RULESET, reference_templates=references)
        repeated = [
            generate_program(request, case_catalog, RULESET, reference_templates=references)
            for _ in range(max(1, determinism_repeats))
        ]
        fingerprints = tuple(canonical_fingerprint(item) for item in [result] + repeated)
        records.append(_case_record(profile, request, result, case_catalog, fingerprints))
        if (i + 1) % 10 == 0:
            print(f"Processed {i + 1}/{len(profiles)} profiles", flush=True)
"""

# Replace the multiprocessing logic
content = re.sub(
    r'    global _GLOBAL_CATALOG_BY_SEX, _GLOBAL_REFERENCES\n    _GLOBAL_CATALOG_BY_SEX = catalog_by_sex\n    _GLOBAL_REFERENCES = references\n\n    args_list = \[\n        \(profile, determinism_repeats\)\n        for profile in profiles\n    \]\n    with ProcessPoolExecutor\(max_workers=4\) as executor:\n        records = list\(executor\.map\(_worker, args_list\)\)',
    sequential_loop.strip('\n'),
    content
)

with open("tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content)
