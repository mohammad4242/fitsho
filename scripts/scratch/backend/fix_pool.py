import re

with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

pool_code = """
    from multiprocessing import Pool
    
    global _GLOBAL_CATALOG_BY_SEX, _GLOBAL_REFERENCES, _GLOBAL_DETERMINISM_REPEATS
    _GLOBAL_CATALOG_BY_SEX = catalog_by_sex
    _GLOBAL_REFERENCES = references
    _GLOBAL_DETERMINISM_REPEATS = determinism_repeats

    with Pool(processes=2, maxtasksperchild=10) as pool:
        records = pool.map(_run_single, enumerate(profiles))
"""

content = re.sub(
    r'    global _GLOBAL_CATALOG_BY_SEX, _GLOBAL_REFERENCES, _GLOBAL_DETERMINISM_REPEATS\n    _GLOBAL_CATALOG_BY_SEX = catalog_by_sex\n    _GLOBAL_REFERENCES = references\n    _GLOBAL_DETERMINISM_REPEATS = determinism_repeats\n\n    with ProcessPoolExecutor\(max_workers=2\) as executor:\n        records = list\(executor\.map\(_run_single, enumerate\(profiles\)\)\)',
    pool_code.strip('\n'),
    content
)

with open("tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content)
