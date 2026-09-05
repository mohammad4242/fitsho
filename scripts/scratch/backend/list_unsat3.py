import json
with open("backend/var/benchmarks/prompt5/phase11-benchmark.json", "r") as f:
    data = json.load(f)

unsat = [r for r in data["profiles"] if r.get("category") == "UNSATISFIED" and r['result']['error_code'] == "UNSATISFIED_CONSTRAINT"]
if unsat:
    print(json.dumps(unsat[0]['input'], indent=2))
    print(unsat[0]['result'])
