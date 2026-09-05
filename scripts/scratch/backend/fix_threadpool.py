import re

with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

# I will replace the sequential loop back to ThreadPoolExecutor
# Let's just find the loop and replace it.

start_marker = "    reference_hash = service._template_reference_hash(references)"
end_marker = "    negative_cases: list[dict[str, object]] = []"

before = content.split(start_marker)[0]
after = content.split(end_marker)[1]

middle = """
    records: list[dict[str, object]] = []
    profiles = benchmark_profiles()
    print(f"Running benchmark for {len(profiles)} profiles with ThreadPoolExecutor...", flush=True)
    
    from concurrent.futures import ThreadPoolExecutor
    def _run_single(args):
        i, profile = args
        req = profile_to_request(profile)
        c_catalog = catalog_by_sex[profile.sex]
        req = apply_catalog_constraints(req, profile, c_catalog)
        res = generate_program(req, c_catalog, RULESET, reference_templates=references)
        rep = [
            generate_program(req, c_catalog, RULESET, reference_templates=references)
            for _ in range(max(1, determinism_repeats))
        ]
        fgps = tuple(canonical_fingerprint(item) for item in [res] + rep)
        record = _case_record(profile, req, res, c_catalog, fgps)
        if (i + 1) % 20 == 0:
            print(f"Processed {i + 1}/{len(profiles)}", flush=True)
        return record

    with ThreadPoolExecutor(max_workers=4) as executor:
        records = list(executor.map(_run_single, enumerate(profiles)))
"""

new_content = before + start_marker + middle + end_marker + after
with open("tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(new_content)
