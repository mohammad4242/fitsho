import json
from collections import defaultdict


def format_report(benchmark_json_path: str, output_md_path: str) -> None:
    with open(benchmark_json_path) as f:
        data = json.load(f)

    records = data.get("profiles", [])
    agg = data.get("aggregate", {})
    quality = agg.get("quality", {})
    fallback = agg.get("fallback", {})

    total_profiles = agg.get("profiles_tested", 0)
    cat_counts = agg.get("category_counts", {})
    passes = cat_counts.get("PASS", 0)
    pass_c = cat_counts.get("PASS_WITH_CONSTRAINTS", 0)
    unsat = cat_counts.get("UNSATISFIED", 0)
    bugs = agg.get("engine_bugs", 0)

    gen_success_rate = fallback.get("overall_generation_success_rate", 0)
    determinism_runs = quality.get("determinism_runs", 0)
    determinism_identical = quality.get("determinism_identical", 0)

    eq_v = quality.get("equipment_violations_custom", 0)
    safe_v = quality.get("safety_violations_custom", 0)
    red_v = quality.get("redundancy_violations_custom", 0)

    sub_req = quality.get("substitutions_requests", 0)
    sub_suc = quality.get("substitutions_total", 0)
    sub_exact_grp = quality.get("substitutions_exact_group", 0)
    sub_exact_role = quality.get("substitutions_exact_role", 0)
    sub_fallback = quality.get("movement_family_fallbacks", 0)
    sub_no_valid = quality.get("no_valid_replacements", 0)

    tpl_successes = fallback.get("template_path_successes", 0)
    fb_successes = fallback.get("fallback_successes", 0)

    # Check conditions for READY
    ready = True
    if bugs > 0:
        ready = False
    if eq_v > 0:
        ready = False
    if safe_v > 0:
        ready = False
    if determinism_identical < determinism_runs or determinism_runs == 0:
        ready = False
    if fallback.get("rejection_categories", {}).get("VALIDATION_FAILURE", 0) > 0:
        ready = False
    # semantic substitution failures: rely on bugs/safety

    # Group limitations
    subgroups: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "success": 0})
    for record in records:
        profile = record["input"]
        success = record.get("category") in ("PASS", "PASS_WITH_CONSTRAINTS")

        limitations = []
        if profile.get("allowed_range_of_motion"):
            limitations.append("ROM")
        if profile.get("impact_limit"):
            limitations.append("impact")
        if profile.get("axial_load_limit"):
            limitations.append("axial_load")
        if profile.get("overhead_limit"):
            limitations.append("overhead")
        if profile.get("balance_requirement"):
            limitations.append("balance")
        if profile.get("training_cautions"):
            limitations.append("training_cautions")

        lim_str = ",".join(limitations) if len(limitations) < 2 else "combinations"
        if not limitations:
            lim_str = "none"

        subgroups[lim_str]["total"] += 1
        if success:
            subgroups[lim_str]["success"] += 1

    lines = [
        "# Phase 11 Deterministic Benchmark Final Report",
        "",
        f"- Total Profiles: {total_profiles}",
        f"- PASS: {passes}",
        f"- PASS_WITH_CONSTRAINTS: {pass_c}",
        f"- UNSATISFIED: {unsat}",
        f"- ENGINE_BUG: {bugs}",
        f"- Generation Success Rate: {gen_success_rate * 100:.2f}%",
        f"- Determinism: {determinism_identical}/{determinism_runs}",
        "",
        "## Violations",
        f"- Equipment Violations: {eq_v}",
        f"- Safety/Constraint Violations: {safe_v}",
        f"- Redundancy Violations: {red_v}",
        "",
        "## Substitution Metrics",
        f"- Requests: {sub_req}",
        f"- Successes: {sub_suc}",
        f"- Exact Group: {sub_exact_grp}",
        f"- Exact Role: {sub_exact_role}",
        f"- Family Fallback: {sub_fallback}",
        f"- No Valid Replacement: {sub_no_valid}",
        "",
        "## Paths",
        f"- Template Successes: {tpl_successes}",
        f"- Fallback Successes: {fb_successes}",
        "",
        "## Limitation Subgroup Results",
    ]

    for key, stats in sorted(subgroups.items()):
        rate = stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
        lines.append(f"- **{key}**: {stats['success']}/{stats['total']} ({rate:.1f}%)")

    lines.append("")
    lines.append("## UNSAT Classification")
    unsat_reasons = fallback.get("rejection_categories", {})
    for reason, count in sorted(unsat_reasons.items()):
        lines.append(f"- {reason}: {count}")

    lines.append("")
    lines.append("## Final Verdict")
    if ready:
        lines.append("READY FOR PROMPT 6")
    else:
        lines.append("NOT READY FOR PROMPT 6")

    with open(output_md_path, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    format_report("var/benchmarks/phase11/phase11-benchmark.json", "../PROMPT5_PROGRESS.md")
    print("Done")
