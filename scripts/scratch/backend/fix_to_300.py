import re

with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

# Change range(28) to range(20)
content = content.replace("for variant in range(28)", "for variant in range(20)")

# Ensure wrist and priorities are in range(20)
# variant 16 = impact
# variant 17 = axial
# variant 18 = overhead
# variant 19 = balance
# We can map wrist to variant 19, knee to 18, shoulder to 17, lower_back to 16
# because cautions are separate from limits.
# Actually, just change the if block:

replacement_cautions = """    if variant == 10:
        training_cautions = (TrainingCaution.LOWER_BACK,)
    elif variant == 11:
        training_cautions = (TrainingCaution.SHOULDER,)
    elif variant == 12:
        training_cautions = (TrainingCaution.KNEE,)
    elif variant == 13:
        training_cautions = (TrainingCaution.WRIST,)
    elif variant == 14:
        allowed_rom = frozenset({"spinal_flexion"})
    elif variant == 15:
        allowed_rom = frozenset({"deep_knee_flexion"})"""

content = re.sub(r'    if variant == 20:\n        training_cautions = \(TrainingCaution\.LOWER_BACK,\)\n    elif variant == 21:\n        training_cautions = \(TrainingCaution\.SHOULDER,\)\n    elif variant == 22:\n        training_cautions = \(TrainingCaution\.KNEE,\)\n    elif variant == 25:\n        training_cautions = \(TrainingCaution\.WRIST,\)\n\n    if variant == 23:\n        allowed_rom = frozenset\(\{"spinal_flexion"\}\)\n    elif variant == 24:\n        allowed_rom = frozenset\(\{"deep_knee_flexion"\}\)', replacement_cautions, content)

# Replace ThreadPoolExecutor with ProcessPoolExecutor(max_workers=2)
# But wait, earlier I used ThreadPoolExecutor. I need to change back to ProcessPool.
# Let's just do a string replace for ThreadPoolExecutor.

process_pool = """
    from concurrent.futures import ProcessPoolExecutor
    def _run_single(args):
        i, profile = args
        from app.workouts.program_engine.engine import generate_program
        from tests.workouts.program_engine.phase11_benchmark import profile_to_request, apply_catalog_constraints, RULESET, canonical_fingerprint, _case_record, _GLOBAL_CATALOG_BY_SEX, _GLOBAL_REFERENCES
        req = profile_to_request(profile)
        c_catalog = _GLOBAL_CATALOG_BY_SEX[profile.sex]
        req = apply_catalog_constraints(req, profile, c_catalog)
        res = generate_program(req, c_catalog, RULESET, reference_templates=_GLOBAL_REFERENCES)
        rep = [
            generate_program(req, c_catalog, RULESET, reference_templates=_GLOBAL_REFERENCES)
            for _ in range(max(1, determinism_repeats))
        ]
        fgps = tuple(canonical_fingerprint(item) for item in [res] + rep)
        record = _case_record(profile, req, res, c_catalog, fgps)
        if (i + 1) % 20 == 0:
            print(f"Processed {i + 1}/{len(profiles)}", flush=True)
        return record

    global _GLOBAL_CATALOG_BY_SEX, _GLOBAL_REFERENCES
    _GLOBAL_CATALOG_BY_SEX = catalog_by_sex
    _GLOBAL_REFERENCES = references

    with ProcessPoolExecutor(max_workers=2) as executor:
        records = list(executor.map(_run_single, enumerate(profiles)))
"""

content = re.sub(r'    from concurrent\.futures import ThreadPoolExecutor.*    with ThreadPoolExecutor\(max_workers=4\) as executor:\n        records = list\(executor\.map\(_run_single, enumerate\(profiles\)\)\)', process_pool.strip('\n'), content, flags=re.DOTALL)

with open("tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content)
