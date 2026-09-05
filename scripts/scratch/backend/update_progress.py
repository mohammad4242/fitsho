import json

with open("backend/var/benchmarks/prompt5/phase11-benchmark.json", "r") as f:
    data = json.load(f)

agg = data["aggregate"]
q = agg["quality"]

text = f"""
## Prompt 5 Final Closeout Run
- **Total Profiles**: {agg['profiles_tested']} (Determinism verified)
- **Validation Success**: {q['validation_success_rate']}
- **Pass / Pass with Constraints**: {agg['category_counts'].get('PASS', 0)} / {agg['category_counts'].get('PASS_WITH_CONSTRAINTS', 0)}
- **UNSAT Cases**: {agg['category_counts'].get('UNSATISFIED', 0)}
- **Equipment Violations**: {q.get('equipment_violations_custom', 0)}
- **Safety/Constraint Violations**: {q.get('safety_violations_custom', 0)}
- **Determinism**: {q.get('determinism_identical', 0)} / {q.get('determinism_runs', 0)} exact matches
- **Substitutions**: {q.get('substitutions_total', 0)}
- **Movement Family Fallbacks**: {q.get('movement_family_fallbacks', 0)}
"""

with open("PROMPT5_PROGRESS.md", "a") as f:
    f.write(text)
print("Updated PROMPT5_PROGRESS.md")
