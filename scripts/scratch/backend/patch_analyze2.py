with open("analyze_stage4.py", "r") as f:
    content = f.read()

bad = """    if determinism_identical < determinism_runs or determinism_runs == 0:
    if fallback.get("rejection_categories", {}).get("VALIDATION_FAILURE", 0) > 0: ready = False
        ready = False"""
good = """    if determinism_identical < determinism_runs or determinism_runs == 0:
        ready = False
    if fallback.get("rejection_categories", {}).get("VALIDATION_FAILURE", 0) > 0:
        ready = False"""
        
content = content.replace(bad, good)
with open("analyze_stage4.py", "w") as f:
    f.write(content)
