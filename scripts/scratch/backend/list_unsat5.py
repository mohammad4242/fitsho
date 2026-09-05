import json
with open("backend/var/benchmarks/prompt5/phase11-benchmark.json", "r") as f:
    data = json.load(f)

unsat = sum(1 for r in data["profiles"] if str(r.get("category")) == "UNSATISFIED")
rom_unsat = sum(1 for r in data["profiles"] if str(r.get("category")) == "UNSATISFIED" and r['input']['allowed_range_of_motion'])
print(f"Total UNSAT: {unsat}, ROM UNSAT: {rom_unsat}")

total_rom = sum(1 for r in data["profiles"] if r['input']['allowed_range_of_motion'])
print(f"Total ROM Profiles: {total_rom}")

