import json
from collections import defaultdict
from pathlib import Path

def analyze_subgroups(benchmark_json_path: str, output_md_path: str):
    with open(benchmark_json_path, 'r') as f:
        data = json.load(f)
        
    records = data.get("profiles", [])
    
    # Subgroups:
    # experience, days/week, goal, session duration, equipment setup, home vs gym, limitation type, priority-muscle state, template
    subgroups = defaultdict(lambda: defaultdict(lambda: {"total": 0, "success": 0}))
    
    for record in records:
        profile = record["input"]
        result = record["result"]
        success = record.get("category") in ("PASS", "PASS_WITH_CONSTRAINTS")
        
        experience = profile.get("experience_level")
        days = profile.get("resistance_days")
        goal = profile.get("goal")
        duration = profile.get("duration_minutes")
        equipment = profile.get("equipment_label")
        location = profile.get("training_location")
        
        # limitations
        limitations = []
        if profile.get("impact_limit"): limitations.append("impact")
        if profile.get("axial_load_limit"): limitations.append("axial")
        if profile.get("overhead_limit"): limitations.append("overhead")
        if profile.get("balance_requirement"): limitations.append("balance")
        limitations_str = ",".join(limitations) if limitations else "none"
        
        priority = "yes" if profile.get("priority_muscles") else "no"
        
        template = result["program_generation_metadata"].get("template_slug", "fallback") if result.get("program_generation_metadata") else "failed"
        
        def add(group, key):
            subgroups[group][key]["total"] += 1
            if success:
                subgroups[group][key]["success"] += 1
                
        add("Experience", experience)
        add("Days/Week", days)
        add("Goal", goal)
        add("Session Duration", duration)
        add("Equipment Setup", equipment)
        add("Location", location)
        add("Limitation Type", limitations_str)
        add("Priority Muscles", priority)
        add("Template", template)
        
    lines = ["\n## Subgroup Analysis\n"]
    for group, items in subgroups.items():
        lines.append(f"### {group}")
        for key, stats in sorted(items.items(), key=lambda x: str(x[0])):
            rate = stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
            lines.append(f"- **{key}**: {stats['success']}/{stats['total']} ({rate:.1f}%)")
        lines.append("")
        
    with open(output_md_path, 'a') as f:
        f.write("\n".join(lines))
        
if __name__ == "__main__":
    analyze_subgroups("var/stage3_benchmark_test/phase11-benchmark.json", "var/stage3_benchmark_test/phase11-summary.md")
    print("Done")
