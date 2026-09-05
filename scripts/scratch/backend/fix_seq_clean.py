import re

with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

start_marker = "    reference_hash = service._template_reference_hash(references)"
end_marker = "    negative_cases: list[dict[str, object]] = []"

before = content.split(start_marker)[0]
after = content.split(end_marker)[1]

middle = """
    records: list[dict[str, object]] = []
    profiles = benchmark_profiles()
    print(f"Running benchmark for {len(profiles)} profiles sequentially...", flush=True)
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
        if (i + 1) % 20 == 0:
            print(f"Processed {i + 1}/{len(profiles)}", flush=True)

"""

new_content = before + start_marker + middle + end_marker + after
with open("tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(new_content)
