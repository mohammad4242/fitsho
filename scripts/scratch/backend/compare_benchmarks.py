import json
import os
from collections import defaultdict


def analyze_file(filepath):
    if not os.path.exists(filepath):
        return None
    with open(filepath) as f:
        data = json.load(f)

    records = data.get("profiles", [])
    if not records:
        return None

    by_goal = defaultdict(list)
    by_experience = defaultdict(list)
    by_days = defaultdict(list)
    by_priority = defaultdict(list)
    by_ba = defaultdict(list)

    for r in records:
        inp = r.get("input", {})
        req = r.get("request", {})
        status = r.get("quality_outcome", "UNKNOWN")

        goal = inp.get("goal")
        by_goal[goal].append(status)

        exp = inp.get("experience_level")
        by_experience[exp].append(status)

        days = inp.get("resistance_days")
        by_days[days].append(status)

        prios = inp.get("priority_muscles", [])
        prio_key = "None" if not prios else "HasPriority"
        by_priority[prio_key].append(status)

        bas = inp.get("body_analysis_priorities", [])
        ba_key = "None"
        if bas:
            has_clear = any(x[1] == "clear_lag" for x in bas)
            has_mild = any(x[1] == "mild_lag" for x in bas)
            if has_clear:
                ba_key = "ClearLag"
            elif has_mild:
                ba_key = "MildLag"
        by_ba[ba_key].append(status)

    return {
        "goal": by_goal,
        "experience": by_experience,
        "days": by_days,
        "priority": by_priority,
        "ba": by_ba,
        "total": len(records),
    }


def print_stats(name, stats_before, stats_after):
    print("\n--- Comparison ---")
    if not stats_before or not stats_after:
        return

    for category in stats_before.keys():
        if category == "total":
            continue
        print(f"\n{category.upper()}:")
        for k in sorted(stats_before[category].keys(), key=lambda x: str(x)):
            b_list = stats_before[category].get(k, [])
            a_list = stats_after[category].get(k, [])

            b_passes = sum(1 for x in b_list if x in ["PASS", "PASS_WITH_CONSTRAINTS"])
            b_total = len(b_list)
            b_rate = b_passes / b_total * 100 if b_total else 0

            a_passes = sum(1 for x in a_list if x in ["PASS", "PASS_WITH_CONSTRAINTS"])
            a_total = len(a_list)
            a_rate = a_passes / a_total * 100 if a_total else 0

            diff = a_rate - b_rate
            diff_str = f"+{diff:.1f}%" if diff >= 0 else f"{diff:.1f}%"
            print(
                f"  {k}: Before {b_passes}/{b_total} ({b_rate:.1f}%) -> After {a_passes}/{a_total} ({a_rate:.1f}%) [Diff: {diff_str}]"
            )


def main():
    before = analyze_file(
        "backend/var/benchmarks/phase11-7-verification-phase11-6-repeat/phase11-6-benchmark.json"
    )
    after = analyze_file("backend/var/benchmarks/phase11-6-holdout-after/phase11-6-benchmark.json")
    print_stats("Comparison", before, after)


if __name__ == "__main__":
    main()
