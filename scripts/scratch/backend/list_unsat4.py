import json
with open("backend/var/benchmarks/prompt5/phase11-benchmark.json", "r") as f:
    data = json.load(f)

unsat = [r for r in data["profiles"] if str(r.get("category")) == "UNSATISFIED"]
for r in unsat:
    if not r['input']['allowed_range_of_motion']:
        print(f"Error: {r['result']['error_code']} Eq: {r['input']['equipment_label']} Goal: {r['input']['goal']}")
