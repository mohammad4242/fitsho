from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from tests.workouts.program_engine.phase11_benchmark import (
    EXPECTED_PROFILE_COUNT,
    EXPECTED_TEMPLATE_COUNT,
    EXPECTED_TEMPLATE_SEED_HASH,
    EXPECTED_TEMPLATE_SLUGS,
    verify_closeout,
)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[object]:
    return value if isinstance(value, (list, tuple)) else ()


def _integer(value: object) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _float(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _coverage(records: Sequence[Mapping[str, object]]) -> tuple[Counter[str], Counter[str]]:
    limitations: Counter[str] = Counter()
    priorities: Counter[str] = Counter()
    for record in records:
        profile = _mapping(record.get("input"))
        if _sequence(profile.get("allowed_range_of_motion")):
            limitations["ROM"] += 1
        for field, label in (
            ("impact_limit", "impact"),
            ("axial_load_limit", "axial-load"),
            ("overhead_limit", "overhead"),
            ("balance_requirement", "balance"),
        ):
            if profile.get(field) is not None:
                limitations[label] += 1
        for caution in _sequence(profile.get("training_cautions")):
            limitations[str(caution)] += 1
        for muscle in _sequence(profile.get("priority_muscles")):
            priorities[str(muscle)] += 1
    return limitations, priorities


def render_report(
    payload: Mapping[str, object],
    *,
    verification_summary: Sequence[str] = (),
) -> str:
    aggregate = _mapping(payload.get("aggregate"))
    categories = _mapping(aggregate.get("category_counts"))
    fallback = _mapping(aggregate.get("fallback"))
    quality = _mapping(aggregate.get("quality"))
    catalog = _mapping(payload.get("catalog"))
    determinism = _mapping(payload.get("determinism"))
    records = tuple(_mapping(item) for item in _sequence(payload.get("profiles")))
    total = _integer(aggregate.get("profiles_tested"))
    category_sum = sum(_integer(value) for value in categories.values())
    unsat_count = _integer(categories.get("UNSATISFIED"))
    unsat_classifications = _mapping(fallback.get("unsat_classifications"))
    unsat_sum = sum(_integer(value) for value in unsat_classifications.values())
    limitations, priorities = _coverage(records)
    blockers = verify_closeout(payload)
    verdict = "READY FOR PROMPT 6" if not blockers else "NOT READY FOR PROMPT 6"
    generation_rate = _float(fallback.get("overall_generation_success_rate")) * 100
    determinism_identical = _integer(quality.get("determinism_identical"))
    determinism_cases = _integer(determinism.get("cases"))
    equipment_violations = _integer(quality.get("equipment_violations_custom"))
    safety_violations = _integer(quality.get("safety_violations_custom"))
    redundancy_violations = _integer(quality.get("redundancy_violations_custom"))
    substitution_reconciles = _integer(quality.get("substitutions_requests")) == (
        _integer(quality.get("substitutions_total"))
        + _integer(quality.get("no_valid_replacements"))
    )

    lines = [
        "# Prompt 5 Final Closeout",
        "",
        "## Benchmark population",
        "",
        f"- Profiles: {total}",
        f"- Canonical expected profiles: {EXPECTED_PROFILE_COUNT}",
        f"- Supported matrix cells: {len(_sequence(payload.get('supported_matrix')))}/15",
        f"- Generation rate: {generation_rate:.2f}%",
        f"- Determinism: {determinism_identical}/{determinism_cases}",
        "",
        "## Active template library",
        "",
        f"- Active templates: {_integer(catalog.get('template_count'))}",
        f"- Expected active templates: {EXPECTED_TEMPLATE_COUNT}",
        f"- Catalog hash: {catalog.get('catalog_hash', '')}",
        f"- Template hash: {catalog.get('template_hash', '')}",
        f"- Template seed hash: {catalog.get('template_seed_hash', '')}",
        f"- Expected template seed hash: {EXPECTED_TEMPLATE_SEED_HASH}",
        "",
        "Exact active slugs:",
        "",
    ]
    lines.extend(
        f"- {slug}" for slug in _sequence(catalog.get("template_slugs", EXPECTED_TEMPLATE_SLUGS))
    )
    lines.extend(["", "## Categories", ""])
    for category in (
        "PASS",
        "PASS_WITH_CONSTRAINTS",
        "QUALITY_ISSUE",
        "UNSATISFIED",
        "ENGINE_BUG",
    ):
        lines.append(f"- {category}: {_integer(categories.get(category))}")

    lines.extend(
        [
            "",
            "## Hard acceptance metrics",
            "",
            f"- Equipment violations: {equipment_violations}",
            f"- Safety/constraint hard violations: {safety_violations}",
            f"- Redundancy violations: {redundancy_violations}",
            "",
            "## Quality-code audit",
            "",
        ]
    )
    quality_audit = _mapping(quality.get("quality_code_audit"))
    if not quality_audit:
        lines.append("- No final audit findings.")
    for code, raw_values in sorted(quality_audit.items()):
        values = _mapping(raw_values)
        classifications = _mapping(values.get("classifications"))
        classification_text = ", ".join(
            f"{name}={_integer(count)}" for name, count in sorted(classifications.items())
        )
        lines.append(f"- {code}: {_integer(values.get('count'))} ({classification_text})")
        lines.extend(f"  - {reason}" for reason in _sequence(values.get("explanations")))

    semantic = _mapping(quality.get("semantic_substitution"))
    raw_no_valid = _integer(quality.get("no_valid_replacements"))
    legitimate_no_valid = _integer(semantic.get("legitimate_no_valid_replacements"))
    failed_intermediate_no_valid = raw_no_valid - legitimate_no_valid
    recovered_intermediate = _integer(semantic.get("recovered_intermediate_attempts"))
    recovered_template_rejections = recovered_intermediate - failed_intermediate_no_valid
    lines.extend(["", "## Semantic substitution audit", ""])
    for key in (
        "successful_valid_substitutions",
        "recovered_intermediate_attempts",
        "legitimate_no_valid_replacements",
        "final_semantic_degradations",
        "explained_final_semantic_degradations",
        "unexplained_final_semantic_failures",
    ):
        lines.append(f"- {key}: {_integer(semantic.get(key))}")
    lines.extend(
        [
            f"- raw substitution requests: {_integer(quality.get('substitutions_requests'))}",
            f"- raw substitution successes: {_integer(quality.get('substitutions_total'))}",
            f"- exact group: {_integer(quality.get('substitutions_exact_group'))}",
            f"- exact semantic role: {_integer(quality.get('substitutions_exact_role'))}",
            f"- movement-family fallback: {_integer(quality.get('movement_family_fallbacks'))}",
            f"- raw no-valid-replacement: {raw_no_valid}",
            (
                "- no-valid partition: "
                f"{legitimate_no_valid} legitimate display cases + "
                f"{failed_intermediate_no_valid} failed repair attempts later recovered"
            ),
            (
                "- recovered intermediate partition: "
                f"{failed_intermediate_no_valid} repair attempts + "
                f"{recovered_template_rejections} rejected template attempts"
            ),
            "",
            "## Limitation and priority coverage",
            "",
        ]
    )
    lines.extend(f"- limitation {name}: {count}" for name, count in sorted(limitations.items()))
    lines.extend(f"- priority {name}: {count}" for name, count in sorted(priorities.items()))

    lines.extend(["", "## Exact UNSAT classification", ""])
    unsat_records = tuple(record for record in records if record.get("category") == "UNSATISFIED")
    if not unsat_records:
        lines.append("- None.")
    for record in unsat_records:
        profile = _mapping(record.get("input"))
        classification = _mapping(record.get("unsat_classification"))
        evidence = ", ".join(str(item) for item in _sequence(classification.get("evidence")))
        lines.append(f"- {profile.get('profile_id')}: {classification.get('cause')} | {evidence}")

    template_matches = (
        _integer(catalog.get("template_count")) == EXPECTED_TEMPLATE_COUNT
        and tuple(sorted(str(item) for item in _sequence(catalog.get("template_slugs"))))
        == EXPECTED_TEMPLATE_SLUGS
    )
    lines.extend(
        [
            "",
            "## Consistency checks",
            "",
            f"- Profile records equal aggregate: {len(records) == total}",
            f"- Category totals equal profiles: {category_sum == total}",
            f"- UNSAT classifications equal UNSAT: {unsat_sum == unsat_count}",
            f"- Determinism denominator equals profiles: {determinism_cases == total}",
            f"- Template count and slugs match seed intent: {template_matches}",
            f"- Substitution requests equal successes plus no-valid: {substitution_reconciles}",
            "",
            "## Test verification",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in verification_summary)
    if not verification_summary:
        lines.append("- Not recorded in this report generation run.")

    lines.extend(["", "## Final verdict", "", verdict])
    if blockers:
        lines.extend(["", "Blockers:"])
        lines.extend(f"- {blocker}" for blocker in blockers)
    return "\n".join(lines) + "\n"


def format_report(
    benchmark_json_path: str | Path,
    output_md_path: str | Path,
    *,
    verification_summary: Sequence[str] = (),
) -> None:
    payload = json.loads(Path(benchmark_json_path).read_text(encoding="utf-8"))
    Path(output_md_path).write_text(
        render_report(payload, verification_summary=verification_summary), encoding="utf-8"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render and verify the Prompt 5 closeout report")
    parser.add_argument(
        "--benchmark-json",
        default="var/benchmarks/phase11/phase11-benchmark.json",
    )
    parser.add_argument("--output", default="../PROMPT5_PROGRESS.md")
    parser.add_argument("--verification-result", action="append", default=[])
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.benchmark_json).read_text(encoding="utf-8"))
    blockers = verify_closeout(payload)
    Path(args.output).write_text(
        render_report(payload, verification_summary=tuple(args.verification_result)),
        encoding="utf-8",
    )
    print("READY" if not blockers else "NOT READY")
    for blocker in blockers:
        print(f"- {blocker}")
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
