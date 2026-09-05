with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

# I will find the sequential loop and replace it with pool code!
import re

pool_code = """
    records: list[dict[str, object]] = []
    
    # Multiprocessing setup
    from multiprocessing import Pool
    global _GLOBAL_CATALOG_BY_SEX, _GLOBAL_REFERENCES, _GLOBAL_DETERMINISM_REPEATS
    _GLOBAL_CATALOG_BY_SEX = catalog_by_sex
    _GLOBAL_REFERENCES = references
    _GLOBAL_DETERMINISM_REPEATS = determinism_repeats

    print(f"Running benchmark for {len(profiles)} profiles with Pool(2, chunksize=1, maxtasksperchild=5)...", flush=True)
    with Pool(processes=2, maxtasksperchild=5) as pool:
        for record in pool.imap(_run_single, enumerate(profiles), chunksize=1):
            records.append(record)
"""

content = re.sub(
    r'    records: list\[dict\[str, object\]\] = \[\]\n    for i, profile in enumerate\(profiles\):.*?print\(f"Processed {i \+ 1}/\{len\(profiles\)}", flush=True\)',
    pool_code.strip('\n'),
    content,
    flags=re.DOTALL
)

with open("tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content)
