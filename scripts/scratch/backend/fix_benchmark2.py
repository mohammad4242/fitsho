import re

with open('tests/workouts/program_engine/phase11_benchmark.py', 'r') as f:
    content = f.read()

# 1. Modify _aggregate function to add unsat_classifications
agg_idx = content.find("def _aggregate(records:")
if agg_idx == -1:
    print("Cannot find _aggregate")
    exit(1)

# Add logic for unsat_classifications
insert_pos = content.find("unsatisfied = sum(str(item[\"category\"]) == \"UNSATISFIED\" for item in records)", agg_idx)
if insert_pos == -1:
    print("Cannot find unsatisfied = sum...")
    exit(1)

new_code = """unsatisfied = sum(str(item["category"]) == "UNSATISFIED" for item in records)
    unsat_classifications: Counter[str] = Counter()
    for item in records:
        if str(item["category"]) == "UNSATISFIED":
            template_info = item.get("template", {})
            rejections = set(template_info.get("rejection_categories", ()))
            
            if "VALIDATION_FAILURE" in rejections:
                unsat_classifications["engine bug"] += 1
            elif "SAFETY_EQUIPMENT_INCOMPATIBILITY" in rejections:
                unsat_classifications["legitimate catalog limitation"] += 1
            elif rejections.intersection({"CORE_SLOT_UNRESOLVED", "HARD_PRIORITY_MINIMUM_FAILURE", "DURATION_RECOVERY_HARD_IMPOSSIBILITY", "NO_DAYS_LEVEL_CANDIDATE"}):
                unsat_classifications["legitimate constraint limitation"] += 1
            else:
                unsat_classifications["quality issue"] += 1"""

content = content[:insert_pos] + new_code + content[insert_pos + len("unsatisfied = sum(str(item[\"category\"]) == \"UNSATISFIED\" for item in records)"):]

# 2. Add unsat_classifications to the fallback dict
fallback_pos = content.find("\"fallback\": {")
if fallback_pos == -1:
    print("Cannot find fallback dict")
    exit(1)

insert_pos2 = content.find("\"rejection_categories\": dict(sorted(rejection_categories.items())),", fallback_pos)
if insert_pos2 == -1:
    print("Cannot find rejection_categories in fallback")
    exit(1)

new_code2 = """"rejection_categories": dict(sorted(rejection_categories.items())),
            "unsat_classifications": dict(sorted(unsat_classifications.items())),"""

content = content[:insert_pos2] + new_code2 + content[insert_pos2 + len("\"rejection_categories\": dict(sorted(rejection_categories.items())),"):]


# 3. Add QUALITY_ISSUE to _category function return value check?
# Wait, _category already returns QUALITY_ISSUE:
# if any(item.get("severity") == "quality" for item in issues): return "QUALITY_ISSUE"
# We just need to make sure `categories` has it when missing? `Counter` defaults to 0, so it's fine. Wait, `category_counts` has `sorted(categories.items())`. But if a category count is 0, it won't be in the Counter.
# We should initialize the Counter with all 5 categories.

init_pos = content.find("categories = Counter(str(item[\"category\"]) for item in records)", agg_idx)
new_init = """categories = Counter(str(item["category"]) for item in records)
    for cat in ("PASS", "PASS_WITH_CONSTRAINTS", "QUALITY_ISSUE", "UNSATISFIED", "ENGINE_BUG"):
        categories[cat] += 0"""

content = content[:init_pos] + new_init + content[init_pos + len("categories = Counter(str(item[\"category\"]) for item in records)"):]

with open('tests/workouts/program_engine/phase11_benchmark.py', 'w') as f:
    f.write(content)

print("Patched phase11_benchmark.py successfully")
