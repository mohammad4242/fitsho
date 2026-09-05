import json
with open("backend/var/benchmarks/prompt5/phase11-benchmark.json", "r") as f:
    data = json.load(f)

unsat = [r for r in data["profiles"] if str(r.get("category")) == "UNSATISFIED" and r['input']['equipment_label'] == "full_gym"]
if unsat:
    print(json.dumps(unsat[0], indent=2))
