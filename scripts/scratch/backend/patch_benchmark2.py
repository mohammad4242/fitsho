import re

with open("backend/tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

old_quality_dict = """        "quality": {
            "validation_success_rate": round(validation_success / total, 4) if total else 0.0,
            "metrics": quality_rates,
            "top_findings": findings.most_common(),
        },"""

new_quality_dict = """        "quality": {
            "validation_success_rate": round(validation_success / total, 4) if total else 0.0,
            "metrics": quality_rates,
            "top_findings": findings.most_common(),
            "determinism_identical": determinism,
            "determinism_runs": determinism_runs,
            "substitutions_total": substitutions_total,
            "movement_family_fallbacks": movement_family_fallbacks,
            "equipment_violations_custom": equipment_violations,
            "safety_violations_custom": safety_violations,
            "redundancy_violations_custom": redundancy_violations,
        },"""

content = content.replace(old_quality_dict, new_quality_dict)

with open("backend/tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content)
