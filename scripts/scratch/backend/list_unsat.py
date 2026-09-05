import json
from collections import Counter

with open("backend/var/benchmarks/prompt5/phase11-benchmark.json", "r") as f:
    data = json.load(f)

unsat = [r for r in data["profiles"] if str(r.get("category")) == "UNSATISFIED"]
reasons = Counter()
for r in unsat:
    error = str(r['result']['error_code'])
    eq = r['input']['equipment_label']
    days = str(r['input']['resistance_days'])
    exp = str(r['input']['experience_level'])
    reasons[(error, eq, days, exp)] += 1

print("UNSAT Classifications:")
for k, v in reasons.most_common(20):
    print(f"{v}x: Error={k[0]}, Eq={k[1]}, Days={k[2]}, Exp={k[3]}")
