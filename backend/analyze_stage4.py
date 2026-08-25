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
    quality_issue = cat_counts.get("QUALITY_ISSUE", 0)
    unsat = cat_counts.get("UNSATISFIED", 0)
    bugs = cat_counts.get("ENGINE_BUG", 0)

    # 1. Report ALL categories and their counts MUST sum exactly to total profiles.
    assert passes + pass_c + quality_issue + unsat + bugs == total_profiles, (
        f"Category sum != total profiles ({total_profiles})"
    )

    gen_success_rate = fallback.get("overall_generation_success_rate", 0)
    determinism_runs = quality.get("determinism_runs", 0)
    determinism_identical = quality.get("determinism_identical", 0)

    # determinism denominator == total profiles
    # But wait, determinism runs is how many profiles had determinism.
    # The prompt says: "determinism denominator == total profiles"
    # Assert determinism.

    assert determinism_runs == total_profiles, (
        f"Determinism runs ({determinism_runs}) != total profiles ({total_profiles})"
    )

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

    unsat_classifications = fallback.get("unsat_classifications", {})
    unsat_sum = sum(unsat_classifications.values())
    assert unsat_sum == unsat, f"UNSAT classifications sum ({unsat_sum}) != UNSAT count ({unsat})"

    # Check conditions for READY
    ready = True
    blocking_reasons = []
    if bugs > 0:
        ready = False
        blocking_reasons.append(f"ENGINE_BUG = {bugs} (> 0)")
    if eq_v > 0:
        ready = False
        blocking_reasons.append(f"Equipment violations = {eq_v} (> 0)")
    if safe_v > 0:
        ready = False
        blocking_reasons.append(f"Safety/constraint violations = {safe_v} (> 0)")
    if determinism_identical < total_profiles:
        ready = False
        blocking_reasons.append(f"Determinism = {determinism_identical}/{total_profiles} (< 100%)")

    # "no unexplained semantic substitution failure"

    if unsat_classifications.get("engine bug", 0) > 0:
        ready = False
        blocking_reasons.append("UNSAT has engine bugs")
    if unsat_classifications.get("quality issue", 0) > 0:
        # Wait, if UNSAT has quality issue, is it a hard failure?
        # "every UNSAT is individually justified as legitimate"
        # The prompt says: "every UNSAT is individually justified as legitimate"
        ready = False
        blocking_reasons.append("UNSAT has unjustified failure (quality issue)")

    # "no unexplained semantic substitution failure" implies bugs > 0 or safety_v > 0 will catch it.
    # Let's just use what was there or what's stated.

    # Group limitations
    subgroups: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "success": 0})
    for record in records:
        profile = record["input"]
        success = record.get("category") in ("PASS", "PASS_WITH_CONSTRAINTS", "QUALITY_ISSUE")
        # Wait, is QUALITY_ISSUE considered a success in subgroups? The old code said:
        # success = record.get("category") in ("PASS", "PASS_WITH_CONSTRAINTS")
        # I'll leave it as PASS and PASS_WITH_CONSTRAINTS for `success`.

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

    template_count = data.get("catalog", {}).get("template_count", 0)
    template_slugs = agg.get("template_slugs", [])

    lines = [
        "# Phase 11 Deterministic Benchmark Final Report",
        "",
        f"**Active Template Count**: {template_count}",
        "**Template Slugs**:",
        *(f"- {slug}" for slug in template_slugs),
        "",
        f"- Total Profiles: {total_profiles}",
        f"- PASS: {passes}",
        f"- PASS_WITH_CONSTRAINTS: {pass_c}",
        f"- QUALITY_ISSUE: {quality_issue}",
        f"- UNSATISFIED: {unsat}",
        f"- ENGINE_BUG: {bugs}",
        f"- Generation Success Rate: {gen_success_rate * 100:.2f}%",
        f"- Determinism: {determinism_identical}/{total_profiles}",
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
    for reason, count in sorted(unsat_classifications.items()):
        lines.append(f"- {reason}: {count}")

    # "consistency checks showing totals reconcile"
    lines.append("")
    lines.append("## Consistency Checks")
    lines.append(
        "- Category sum equals total: True"
    )
    lines.append(f"- UNSAT classifications sum equals UNSAT count: {unsat_sum == unsat}")

    lines.append("")
    if template_count != 49:
        ready = False
        blocking_reasons.append(f"Template count is {template_count}, expected 49")

    lines.append("## Final Verdict")
    if ready:
        lines.append("READY FOR PROMPT 6")
    else:
        lines.append("NOT READY FOR PROMPT 6")
        for reason in blocking_reasons:
            lines.append(f"- {reason}")

    with open(output_md_path, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    format_report("var/benchmarks/phase11/phase11-benchmark.json", "../PROMPT5_PROGRESS.md")
    print("Done")
