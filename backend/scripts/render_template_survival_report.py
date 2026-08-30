# ruff: noqa: E501

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import cast

from weasyprint import HTML  # type: ignore[import-untyped]

UPPER_LOWER_SPLITS = {"upper_lower", "upper_lower_x3"}
SOURCE_MAP = {
    "RECOVERY": (
        "app/workouts/program_engine/recovery.py",
        "recovery_spacing_is_valid() / repair_recovery_weekdays()",
    ),
    "SESSION_DURATION": (
        "app/workouts/program_engine/session_duration.py",
        "repair_session_durations() / _repair_underfill()",
    ),
    "MAIN_EXERCISE_COUNT": (
        "app/workouts/program_engine/supplemental_policy.py",
        "main_exercise_count()",
    ),
    "SESSION_EXERCISE_COUNT": (
        "app/workouts/program_engine/validation.py",
        "validate_program()",
    ),
    "TEMPLATE_SESSION_EXERCISE_COUNT": (
        "app/workouts/program_engine/template_sessions.py",
        "build_template_sessions()",
    ),
    "REQUIRED_CORE_DURATION": (
        "app/workouts/program_engine/template_selector.py",
        "_template_duration_assessment()",
    ),
    "CORE_SLOT": (
        "app/workouts/program_engine/template_selector.py",
        "_core_slots_are_resolvable()",
    ),
    "WEEKLY_MUSCLE_VOLUME": (
        "app/workouts/program_engine/validation.py",
        "validate_program()",
    ),
    "PER_SESSION_MUSCLE_VOLUME": (
        "app/workouts/program_engine/validation.py",
        "validate_program()",
    ),
    "REQUIRED_MOVEMENT_PATTERN": (
        "app/workouts/program_engine/validation.py",
        "validate_program()",
    ),
    "SEMANTIC": (
        "app/workouts/program_engine/session_structure.py",
        "session_structure_errors()",
    ),
    "VALIDATION": (
        "app/workouts/program_engine/validation.py",
        "validate_program()",
    ),
}


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _code(value: object) -> str:
    return f'<span class="code" dir="ltr">{_escape(value)}</span>'


def _join_codes(values: Iterable[object]) -> str:
    items = [_code(item) for item in values]
    return "<br>".join(items) if items else "—"


def _source_for(code: object) -> tuple[str, str]:
    text = str(code or "")
    for fragment, source in SOURCE_MAP.items():
        if fragment in text:
            return source
    return (
        "app/workouts/program_engine/engine.py",
        "generate_program() / _finalize_program()",
    )


def _table(headers: Sequence[str], rows: Iterable[Sequence[object]], css: str = "") -> str:
    head = "".join(f"<th>{header}</th>" for header in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f'<table class="{css}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _status_badge(value: object) -> str:
    text = str(value)
    css = "pass" if text in {"PASS", "SUCCESS", "succeeded", "accepted"} else "fail"
    return f'<span class="badge {css}">{_escape(text)}</span>'


def _competition_is_upper_lower(
    case: Mapping[str, object], topology_by_slug: Mapping[str, str]
) -> bool:
    selected = case.get("final_selected_template")
    if selected is not None and topology_by_slug.get(str(selected)) == "Upper/Lower":
        return True
    return case.get("final_split_type") in UPPER_LOWER_SPLITS


def _stage_days(stage: Mapping[str, object], *, final: bool) -> Sequence[Mapping[str, object]]:
    key_order = ("days", "after", "before") if final else ("days", "before", "after")
    for key in key_order:
        value = stage.get(key)
        if isinstance(value, list):
            return cast(Sequence[Mapping[str, object]], value)
    return ()


def _initial_final_days(
    case: Mapping[str, object],
) -> tuple[Sequence[Mapping[str, object]], Sequence[Mapping[str, object]]]:
    diagnostic = case.get("diagnostics")
    if not isinstance(diagnostic, Mapping):
        return (), ()
    stages = cast(Sequence[Mapping[str, object]], diagnostic.get("stages", ()))
    initial: Sequence[Mapping[str, object]] = ()
    for stage in stages:
        if stage.get("stage") == "session_building":
            initial = _stage_days(stage, final=False)
            break
    final_days: Sequence[Mapping[str, object]] = ()
    for stage in reversed(stages):
        candidate = _stage_days(stage, final=True)
        if candidate:
            final_days = candidate
            break
    return initial, final_days


def _repair_summary(
    case: Mapping[str, object], day_index: int
) -> tuple[int, int, int, int, Counter[str]]:
    diagnostic = case.get("diagnostics")
    if not isinstance(diagnostic, Mapping):
        return 0, 0, 0, 0, Counter()
    set_ops = [
        item
        for item in cast(
            Sequence[Mapping[str, object]], diagnostic.get("set_addition_attempts", ())
        )
        if item.get("day_index") == day_index
    ]
    exercise_ops = [
        item
        for item in cast(
            Sequence[Mapping[str, object]], diagnostic.get("exercise_addition_attempts", ())
        )
        if item.get("day_index") == day_index
    ]
    categories: Counter[str] = Counter()
    for operation in (*set_ops, *exercise_ops):
        reasons = operation.get("rejection_categories", {})
        if isinstance(reasons, Mapping):
            categories.update({str(key): int(cast(int, value)) for key, value in reasons.items()})
    return (
        len(set_ops),
        sum(item.get("success") is True for item in set_ops),
        len(exercise_ops),
        sum(item.get("success") is True for item in exercise_ops),
        categories,
    )


def _case_day_rows(case: Mapping[str, object]) -> list[list[object]]:
    initial, final = _initial_final_days(case)
    initial_by_index = {int(cast(int, item["day_index"])): item for item in initial}
    final_by_index = {int(cast(int, item["day_index"])): item for item in final}
    indexes = sorted(set(initial_by_index) | set(final_by_index))
    policy = cast(Mapping[str, object], case["duration_policy"])
    minimum_minutes = int(cast(int, policy["minimum_main_training_minutes"]))
    maximum_minutes = int(cast(int, policy["maximum_main_training_minutes"]))
    minimum_exercises = int(cast(int, policy["minimum_main_exercises"]))
    maximum_exercises = int(cast(int, policy["maximum_main_exercises"]))
    rows: list[list[object]] = []
    for day_index in indexes:
        before = initial_by_index.get(day_index, {})
        after = final_by_index.get(day_index, before)
        set_calls, set_success, exercise_calls, exercise_success, categories = _repair_summary(
            case, day_index
        )
        minutes = int(cast(int, after.get("main_training_minutes", 0)))
        main_count = int(cast(int, after.get("main_exercise_count", 0)))
        outcomes: list[str] = []
        if minutes < minimum_minutes:
            outcomes.append("UNDER_TARGET")
        elif minutes > maximum_minutes:
            outcomes.append("OVER_TARGET")
        if not minimum_exercises <= main_count <= maximum_exercises:
            outcomes.append("COUNT_OUT_OF_RANGE")
        if not outcomes:
            outcomes.append("DAY_LIMITS_OK")
        rows.append(
            [
                day_index,
                _code(after.get("focus", before.get("focus", "—"))),
                before.get("main_exercise_count", "—"),
                before.get("main_working_sets", "—"),
                before.get("main_training_minutes", "—"),
                after.get("main_exercise_count", "—"),
                after.get("main_working_sets", "—"),
                after.get("main_training_minutes", "—"),
                f"{set_success}/{set_calls}",
                f"{exercise_success}/{exercise_calls}",
                _join_codes(f"{key}:{value}" for key, value in categories.most_common()),
                _join_codes(outcomes),
            ]
        )
    return rows


def _duration_operation_aggregate(
    cases: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    set_calls = set_success = exercise_calls = exercise_success = 0
    categories: Counter[str] = Counter()
    for case in cases:
        diagnostic = case.get("diagnostics")
        if not isinstance(diagnostic, Mapping):
            continue
        for key, call_counter, _success_counter in (
            ("set_addition_attempts", "set_calls", "set_success"),
            ("exercise_addition_attempts", "exercise_calls", "exercise_success"),
        ):
            operations = cast(Sequence[Mapping[str, object]], diagnostic.get(key, ()))
            if call_counter == "set_calls":
                set_calls += len(operations)
                set_success += sum(item.get("success") is True for item in operations)
            else:
                exercise_calls += len(operations)
                exercise_success += sum(item.get("success") is True for item in operations)
            for operation in operations:
                reasons = operation.get("rejection_categories")
                if isinstance(reasons, Mapping):
                    categories.update(
                        {str(name): int(cast(int, count)) for name, count in reasons.items()}
                    )
    return {
        "set_calls": set_calls,
        "set_success": set_success,
        "exercise_calls": exercise_calls,
        "exercise_success": exercise_success,
        "categories": categories,
    }


def _css() -> str:
    return """
@page { size: A4 landscape; margin: 12mm 10mm 13mm; @bottom-left { content: "Fitsho Template Survival Audit"; font-size: 7pt; color: #64748b; } @bottom-right { content: "صفحه " counter(page) " از " counter(pages); font-size: 7pt; color: #64748b; } }
@font-face { font-family: Noto; src: url(file:///usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf); }
@font-face { font-family: Noto; src: url(file:///usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf); font-weight: 700; }
* { box-sizing: border-box; }
body { direction: rtl; font-family: Noto, sans-serif; color: #172033; font-size: 8.2pt; line-height: 1.55; }
h1 { color: #0f172a; font-size: 24pt; margin: 0 0 8mm; }
h2 { color: #0f4c5c; font-size: 15pt; border-bottom: 2px solid #0f766e; padding-bottom: 2mm; margin: 9mm 0 4mm; break-after: avoid; }
h3 { color: #334155; font-size: 10.5pt; margin: 5mm 0 2mm; break-after: avoid; }
p { margin: 1.5mm 0; }
.cover { min-height: 170mm; padding: 15mm; background: linear-gradient(135deg,#ecfeff,#f8fafc 55%,#f0fdf4); border: 1px solid #99f6e4; border-radius: 5mm; page-break-after: always; }
.cover .kicker { color: #0f766e; font-weight: 700; letter-spacing: .5px; }
.cards { display: flex; gap: 3mm; margin: 4mm 0; }
.card { flex: 1; border: 1px solid #cbd5e1; border-radius: 2mm; padding: 3mm; background: #fff; }
.metric { font-size: 18pt; font-weight: 700; color: #0f766e; direction: ltr; }
.callout { border-right: 4px solid #0f766e; background: #f0fdfa; padding: 3mm; margin: 3mm 0; }
.warning { border-right-color: #dc2626; background: #fef2f2; }
.code { direction: ltr; unicode-bidi: isolate; font-family: DejaVu Sans Mono, monospace; font-size: 7.1pt; overflow-wrap: anywhere; }
.badge { display: inline-block; direction: ltr; padding: .5mm 2mm; border-radius: 3mm; font-weight: 700; }
.pass { background: #dcfce7; color: #166534; }
.fail { background: #fee2e2; color: #991b1b; }
table { width: 100%; border-collapse: collapse; margin: 2mm 0 5mm; break-inside: auto; table-layout: fixed; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th { background: #0f4c5c; color: white; font-weight: 700; padding: 1.5mm; border: .2mm solid #cbd5e1; }
td { vertical-align: top; padding: 1.2mm; border: .2mm solid #cbd5e1; overflow-wrap: anywhere; }
tbody tr:nth-child(even) { background: #f8fafc; }
.compact { font-size: 6.7pt; line-height: 1.35; }
.tiny { font-size: 5.9pt; line-height: 1.3; }
.failure-card { border: .3mm solid #fca5a5; border-radius: 2mm; padding: 3mm; margin: 4mm 0; break-before: auto; }
.template-card { border: .3mm solid #99f6e4; border-radius: 2mm; padding: 3mm; margin: 4mm 0; }
.meta { color: #475569; }
.page-break { page-break-before: always; }
.keep { break-inside: avoid; }
"""


def _render(payload: Mapping[str, object], raw_path: Path) -> str:
    inventory = cast(Sequence[Mapping[str, object]], payload["template_inventory"])
    forced = cast(Sequence[Mapping[str, object]], payload["forced_cases"])
    competitions = cast(Sequence[Mapping[str, object]], payload["competition_cases"])
    aggregates = cast(Mapping[str, object], payload["aggregates"])
    overall = cast(Mapping[str, object], aggregates["overall"])
    coverage = cast(Mapping[str, object], payload["coverage"])
    provenance = cast(Mapping[str, object], payload["provenance"])
    topology_by_slug = {str(item["slug"]): str(item["topology"]) for item in inventory}
    inventory_by_slug = {str(item["slug"]): item for item in inventory}
    competition_by_key = {
        (int(cast(int, item["days"])), str(item["level"]), int(cast(int, item["duration"]))): item
        for item in competitions
    }
    root_causes = cast(Sequence[Mapping[str, object]], aggregates["root_causes"])
    upper_output_cases = [
        item for item in competitions if _competition_is_upper_lower(item, topology_by_slug)
    ]
    failed = [item for item in forced if item["forced_template_result"] == "FAIL"]
    duration_failures = [
        item
        for item in failed
        if any(
            "DURATION" in str(code) or "EXERCISE_COUNT" in str(code)
            for code in cast(Sequence[object], item.get("reason_codes", ()))
        )
    ]
    duration_operations = _duration_operation_aggregate(duration_failures)

    parts = [
        "<!doctype html><html lang='fa' dir='rtl'><head><meta charset='utf-8'>",
        f"<style>{_css()}</style></head><body>",
        "<section class='cover'>",
        "<div class='kicker'>AUDIT DIAGNOSTIC — CURRENT ENGINE</div>",
        "<h1>گزارش عیب‌یابی بقای Templateهای تمرینی ۴، ۵ و ۶ روزه Fitsho</h1>",
        "<p>Forced Template Survival + Production Competition Trace</p>",
        "<div class='cards'>",
        f"<div class='card'><div class='metric'>{len(inventory)}</div><div>Template فعال واقعی</div></div>",
        f"<div class='card'><div class='metric'>{overall['tests']}</div><div>Forced case</div></div>",
        f"<div class='card'><div class='metric'>{overall['success_rate']}%</div><div>Survival کلی</div></div>",
        f"<div class='card'><div class='metric'>{overall['competition_upper_lower_outputs']}/30</div><div>خروجی Competition از خانواده Upper/Lower</div></div>",
        "</div>",
        "<div class='callout warning'><b>نتیجه‌ی اصلی:</b> Professional Topology Preference ترتیب تلاش را تغییر می‌دهد، اما survival را تضمین نمی‌کند. "
        f"در اجرای واقعی این snapshot، Upper/Lower survival برابر <b>{overall['upper_lower_survival_rate']}%</b> و "
        f"سایر topologyهای دارای امتیاز حرفه‌ای برابر <b>{overall['professional_topology_survival_rate']}%</b> بود.</div>",
        f"<p class='meta'>Generated: {_code(payload['generated_at_utc'])}<br>HEAD: {_code(provenance['head'])}<br>worktree diff SHA-256: {_code(provenance['worktree_diff_sha256'])}<br>raw SHA-256: {_code(_sha256(raw_path))}</p>",
        "</section>",
    ]

    parts.extend(
        [
            "<h2>1. Executive Summary</h2>",
            _table(
                ("شاخص", "مقدار"),
                (
                    ("Templateهای بررسی‌شده", len(inventory)),
                    ("Forced tests", overall["tests"]),
                    ("PASS", overall["passed"]),
                    ("FAIL", overall["failed"]),
                    ("Success rate", f"{overall['success_rate']}%"),
                    ("Upper/Lower survival", f"{overall['upper_lower_survival_rate']}%"),
                    (
                        "Professional topology survival",
                        f"{overall['professional_topology_survival_rate']}%",
                    ),
                    ("Competition scenarios", overall["competition_scenarios"]),
                    ("Upper/Lower competition outputs", overall["competition_upper_lower_outputs"]),
                ),
            ),
            "<p><b>پنج علت اصلی:</b> "
            + "، ".join(
                f"{_code(item['code'])} ({item['count']})" for item in root_causes[:5]
            )
            + ".</p>",
            "<h3>پوشش و provenance</h3>",
            _table(
                ("کنترل", "مقدار"),
                (
                    ("Expected Template × Level × Duration", coverage["expected_template_level_duration_cases"]),
                    ("Executed Forced", coverage["executed_forced_cases"]),
                    ("Expected Competition", coverage["expected_competition_scenarios"]),
                    ("Executed Competition", coverage["executed_competition_scenarios"]),
                    ("Missing keys", _join_codes(cast(Sequence[object], coverage["missing_forced_keys"]))),
                    ("Coverage complete", _status_badge("PASS" if coverage["complete"] else "FAIL")),
                    ("Active template references — all", provenance["template_reference_count_all_active"]),
                    ("Audited references", provenance["template_reference_count_audited"]),
                    ("Production exercise catalog", provenance["exercise_catalog_count"]),
                    ("Template reference SHA-256", _code(provenance["template_reference_sha256"])),
                ),
            ),
            "<p>Catalog از مسیر واقعی "
            + _code("training_templates.engine_reference.load_template_references()")
            + " و Exerciseها از مسیر واقعی "
            + _code("WorkoutGenerationService._load_catalog()")
            + " خوانده شدند. هیچ Template مصنوعی و هیچ seed/migration در Audit اجرا نشد.</p>",
            "<h3>Baseline کنترل‌شده</h3>",
            "<p>Gym، همه‌ی Equipment enumها، بدون injury/caution/priority/body-analysis، "
            "sleep=good، stress=average، recovery context مطلوب، goal=hypertrophy. "
            "تمام 30 baseline normalization check دقیقاً به INTERMEDIATE یا ADVANCED مورد انتظار رسیدند.</p>",
        ]
    )

    parts.append("<h2>Catalog واقعی و مشخصات Templateها</h2>")
    for template in inventory:
        days = cast(Sequence[Mapping[str, object]], template["days"])
        parts.extend(
            [
                "<section class='template-card'>",
                f"<h3>{_code(template['slug'])} — {_escape(template['name_fa'])}</h3>",
                "<p class='meta'>"
                f"name={_code(template['name_en'])} | days={template['days_per_week']} | "
                f"levels={_join_codes(cast(Sequence[object], template['supported_levels']))} | "
                f"topology={_code(template['topology'])} | split_type={_code(template['split_type'])}<br>"
                f"focus_tags={_join_codes(cast(Sequence[object], template['focus_tags']))} | "
                f"intensity_methods={_join_codes(cast(Sequence[object], template['intensity_methods']))} | "
                f"specialization_tags={_join_codes(cast(Sequence[object], template['specialization_tags']))}</p>",
                _table(
                    (
                        "روز",
                        "عنوان",
                        "structure_focus",
                        "Initial exercises",
                        "Core slots",
                        "Accessory",
                        "Optional",
                        "Target muscles",
                        "Methods",
                    ),
                    (
                        (
                            day["day_number"],
                            f"{_escape(day['title_fa'])}<br>{_code(day['title_en'])}",
                            _code(day["structure_focus"]),
                            day["initial_exercise_count_including_superset_companions"],
                            day["core_slots"],
                            day["accessory_slots"],
                            day["optional_slots"],
                            _join_codes(cast(Sequence[object], day["target_muscles"])),
                            _join_codes(cast(Sequence[object], day["intensity_methods"])),
                        )
                        for day in days
                    ),
                    "compact",
                ),
                "</section>",
            ]
        )

    parts.append("<h2 class='page-break'>2. Test Matrix</h2>")
    matrix_rows: list[list[object]] = []
    for case in forced:
        key = (
            int(cast(int, case["days"])),
            str(case["level"]),
            int(cast(int, case["duration"])),
        )
        competition = competition_by_key[key]
        selected = competition.get("final_selected_template") or (
            f"dynamic:{competition.get('final_split_type')}"
        )
        matrix_rows.append(
            [
                _code(case["template_slug"]),
                _code(topology_by_slug[str(case["template_slug"])]),
                _code(case["level"]),
                case["days"],
                case["duration"],
                _status_badge(case["forced_template_result"]),
                _status_badge(competition["overall_engine_result"]),
                _code(selected),
                _code(case.get("primary_failure_cause") or "—"),
            ]
        )
    parts.append(
        _table(
            (
                "Template",
                "Topology",
                "Level",
                "Days",
                "Duration",
                "Forced",
                "Competition",
                "Final selected",
                "Primary failure",
            ),
            matrix_rows,
            "tiny",
        )
    )

    parts.append("<h2 class='page-break'>3. Template Survival Summary</h2>")
    by_template = cast(Mapping[str, Mapping[str, object]], aggregates["by_template"])
    parts.append(
        _table(
            ("Template", "Topology", "Tests", "PASS", "FAIL", "Success rate"),
            (
                (
                    _code(slug),
                    _code(topology_by_slug[slug]),
                    row["tests"],
                    row["passed"],
                    row["failed"],
                    f"{row['success_rate']}%",
                )
                for slug, row in by_template.items()
            ),
            "compact",
        )
    )

    parts.append("<h2 class='page-break'>4. Detailed Failures</h2>")
    parts.append(
        "<p>هر بلوک یک Forced failure واقعی است. جدول روزانه، وضعیت بعد از "
        "session building و آخرین state پیش از reject را مقایسه می‌کند. نسبت Repair به‌شکل "
        "success/call نمایش داده شده است.</p>"
    )
    for index, case in enumerate(failed, start=1):
        source_file, source_function = _source_for(case.get("primary_failure_cause"))
        diagnostic = case.get("diagnostics")
        stages = (
            cast(Sequence[Mapping[str, object]], diagnostic.get("stages", ()))
            if isinstance(diagnostic, Mapping)
            else ()
        )
        chain = []
        for stage in stages:
            reasons = stage.get("reason_codes", stage.get("errors", ()))
            chain.append(
                f"{stage.get('stage')}:{stage.get('status', 'observed')}"
                + (f"[{','.join(str(item) for item in cast(Sequence[object], reasons))}]" if reasons else "")
            )
        day_rows = _case_day_rows(case)
        parts.extend(
            [
                "<section class='failure-card'>",
                f"<h3>{index}. {_code(case['template_slug'])} — {_code(case['level'])} — {case['duration']} min</h3>",
                f"<p><b>Failure stage:</b> {_code(case['failure_stage'])} | "
                f"<b>Root cause:</b> {_code(case['primary_failure_cause'])}<br>"
                f"<b>Reason codes:</b> {_join_codes(cast(Sequence[object], case['reason_codes']))}<br>"
                f"<b>Relevant:</b> {_code(source_file)} :: {_code(source_function)}<br>"
                f"<b>Stage chain:</b> {_join_codes(chain or ['template rejected before runtime stages'])}</p>",
            ]
        )
        if day_rows:
            parts.append(
                _table(
                    (
                        "Day",
                        "Focus",
                        "Initial count",
                        "Initial sets",
                        "Initial min",
                        "Final count",
                        "Final sets",
                        "Final min",
                        "+Set",
                        "+Exercise",
                        "Candidate rejection categories",
                        "Day result",
                    ),
                    day_rows,
                    "tiny",
                )
            )
        else:
            template = inventory_by_slug[str(case["template_slug"])]
            parts.append(
                "<p>Session ساخته نشد؛ failure در construction/hard eligibility رخ داد. "
                f"Catalog day slot counts: {_join_codes(day['initial_slot_count'] for day in cast(Sequence[Mapping[str, object]], template['days']))}</p>"
            )
        parts.append("</section>")

    parts.append("<h2 class='page-break'>5. Competition Trace — Upper/Lower outputs</h2>")
    for case in upper_output_cases:
        selected = case.get("final_selected_template") or f"dynamic:{case.get('final_split_type')}"
        attempts = cast(Sequence[Mapping[str, object]], case.get("attempt_sequence", ()))
        parts.extend(
            [
                "<section class='failure-card'>",
                f"<h3>{_code(case['case_id'])} → {_code(selected)}</h3>",
                f"<p>Professional candidates before first Upper/Lower rank: {case['professional_templates_before_first_upper_lower']}</p>",
                _table(
                    (
                        "Rank",
                        "Template",
                        "priority",
                        "body",
                        "goal",
                        "sex",
                        "fallback",
                        "professional",
                        "total",
                        "Result",
                        "Reasons",
                    ),
                    (
                        (
                            attempt.get("rank", "—"),
                            _code(attempt.get("slug", "—")),
                            cast(Mapping[str, object], attempt.get("score", {})).get("priority", 0),
                            cast(Mapping[str, object], attempt.get("score", {})).get("body_analysis", 0),
                            cast(Mapping[str, object], attempt.get("score", {})).get("goal", 0),
                            cast(Mapping[str, object], attempt.get("score", {})).get("sex", 0),
                            cast(Mapping[str, object], attempt.get("score", {})).get("fallback", 0),
                            cast(Mapping[str, object], attempt.get("score", {})).get("professional_structure", 0),
                            cast(Mapping[str, object], attempt.get("score", {})).get("total", 0),
                            _status_badge(attempt.get("status", "—")),
                            _join_codes(cast(Sequence[object], attempt.get("reason_codes", ()))),
                        )
                        for attempt in attempts
                    ),
                    "tiny",
                ),
                "</section>",
            ]
        )

    parts.append("<h2 class='page-break'>6. Duration Deep Dive</h2>")
    by_duration = cast(Mapping[str, Mapping[str, object]], aggregates["by_duration"])
    parts.append(
        _table(
            ("Duration", "Tests", "PASS", "FAIL", "Success", "Duration failures"),
            (
                (
                    f"{duration} min",
                    row["tests"],
                    row["passed"],
                    row["failed"],
                    f"{row['success_rate']}%",
                    row["duration_failures"],
                )
                for duration, row in sorted(by_duration.items(), key=lambda item: int(item[0]))
            ),
        )
    )
    parts.append(
        _table(
            ("Repair diagnostic", "Count"),
            (
                ("Duration/count failure cases", len(duration_failures)),
                ("Set Addition success/calls", f"{duration_operations['set_success']}/{duration_operations['set_calls']}"),
                ("Exercise Addition success/calls", f"{duration_operations['exercise_success']}/{duration_operations['exercise_calls']}"),
                (
                    "Rejected candidate categories",
                    _join_codes(
                        f"{name}:{count}"
                        for name, count in cast(
                            Counter[str], duration_operations["categories"]
                        ).most_common()
                    ),
                ),
            ),
        )
    )
    parts.append(
        "<div class='callout'>در این snapshot، Duration failure در 30 و 45 دقیقه علت اصلی نبود؛ "
        "از 60 دقیقه شروع شد و در 90 دقیقه به 26 مورد رسید. Repair فقط می‌تواند work امن و مفید "
        "را تا سقف‌های count، session volume، weekly hard volume، semantic equivalence و target muscle اضافه کند.</div>"
    )

    parts.append("<h2>7. Topology Comparison</h2>")
    by_topology = cast(Mapping[str, Mapping[str, object]], aggregates["by_topology"])
    parts.append(
        _table(
            (
                "Topology",
                "Tests",
                "PASS",
                "FAIL",
                "Success",
                "Duration",
                "Volume",
                "Recovery",
                "Construction",
                "Validation/Gate",
            ),
            (
                (
                    _code(name.replace("PPLx2", "PPL×2")),
                    row["tests"],
                    row["passed"],
                    row["failed"],
                    f"{row['success_rate']}%",
                    row["duration_failures"],
                    row["volume_failures"],
                    row["recovery_failures"],
                    row["construction_failures"],
                    row["validation_failures"],
                )
                for name, row in by_topology.items()
            ),
            "compact",
        )
    )

    parts.append("<h2>8. Root Cause Ranking</h2>")
    parts.append(
        _table(
            ("Rank", "Root cause", "Cases", "Relevant file", "Function"),
            (
                (
                    index,
                    _code(item["code"]),
                    item["count"],
                    _code(_source_for(item["code"])[0]),
                    _code(_source_for(item["code"])[1]),
                )
                for index, item in enumerate(root_causes, start=1)
            ),
        )
    )

    parts.append("<h2>9. Architectural Diagnosis — بدون پیشنهاد Fix</h2>")
    body_part = by_topology.get("Body-Part", {})
    specialization = by_topology.get("Specialization", {})
    pplx2 = by_topology.get("PPLx2", {})
    parts.extend(
        [
            "<h3>1) Professional preference یک ordering preference است، نه survival contract</h3>",
            "<p><b>رفتار منطقی؟</b> بله؛ preference نباید hard safety/quality gates را دور بزند. "
            "<b>False negative؟</b> خود score نه، اما feasibility آن فقط slot/capacity اولیه را می‌سنجد و نتیجه‌ی "
            "post-prescription recovery/volume/validation را پیش‌بینی نمی‌کند. <b>Topology impact:</b> "
            "Template حرفه‌ای rank بالا می‌گیرد، fail می‌شود و Upper/Lower کم‌امتیاز بعدی زنده می‌ماند. "
            f"شاهد: {len(upper_output_cases)} Competition output از 30.</p>",
            "<h3>2) Recovery spacing بزرگ‌ترین survival filter است</h3>",
            "<p><b>رفتار منطقی؟</b> حفاظت از دو exposure متوسط/سنگین مجاور منطقی است. "
            "<b>False negative risk:</b> بالا؛ validator تمام secondary setها را با ضریب ثابت 0.5 در exposure load "
            "حساب می‌کند و برای 5/6 روز، تعداد weekday arrangement ممکن محدود است. "
            "<b>Topology impact:</b> Body-Part و PPL/Arnold روزهای هم‌پوشان push/pull/arms را جدا می‌کنند؛ "
            "Upper/Lower هم‌پوشانی را داخل همان session جمع می‌کند و از pairهای مجاور کمتری عبور می‌کند. "
            f"شاهد: Body-Part recovery failures={body_part.get('recovery_failures', 0)} و Upper/Lower recovery failures={by_topology.get('Upper/Lower', {}).get('recovery_failures', 0)}.</p>",
            "<h3>3) Duration underfill با افزایش duration تشدید می‌شود</h3>",
            "<p><b>رفتار منطقی؟</b> قرارداد requested±10 و count حداقل 5 برای 45+ سخت و صریح است. "
            "<b>False negative risk:</b> متوسط تا بالا برای body-part/specialization؛ یک روز عضله‌ای باریک ممکن است "
            "Candidate مفید و غیرتکراری کافی برای 80 دقیقه main training نداشته باشد. "
            "<b>Structural advantage:</b> Upper/Lower target-muscle pool بزرگ‌تری دارد و repair گزینه‌های بیشتری می‌بیند. "
            f"شاهد: 90min duration failures={by_duration['90']['duration_failures']}.</p>",
            "<h3>4) 30-minute count/construction failures محدود اما قطعی‌اند</h3>",
            "<p><b>رفتار منطقی؟</b> بله، سقف 3–4 MAIN برای 30 دقیقه hard invariant است. "
            "<b>False negative risk:</b> وقتی core template slots پس از trim هنوز از سقف عبور کنند. "
            "این failure قبل از volume/duration repair رخ می‌دهد و در چهار case دیده شد.</p>",
            "<h3>5) برخی topologyها عملاً survival بسیار پایین دارند</h3>",
            f"<p>Specialization survival={specialization.get('success_rate', 0)}% و PPL×2 survival={pplx2.get('success_rate', 0)}%. "
            "این نتیجه از Baseline بدون priority است؛ بنابراین specialization bonus تطبیقی فعال نبود. این Audit "
            "ثابت نمی‌کند Templateها برای profile اولویت‌دار نیز همین نرخ را دارند، اما mechanics پایه را نشان می‌دهد.</p>",
            "<div class='callout warning'><b>Diagnosis نهایی:</b> Upper/Lower به‌خاطر score برنده نمی‌شود؛ "
            "به‌خاطر survival advantage پس از fail شدن topologyهای حرفه‌ای برنده می‌شود. در این snapshot، "
            "عامل غالب recovery spacing و سپس duration underfill است. این گزارش هیچ Implementation change پیشنهاد یا اعمال نمی‌کند.</div>",
            "<h3>محدودیت Audit</h3>",
            "<p>این ماتریس mechanics را با دو Baseline کنترل‌شده می‌سنجد، نه distribution واقعی کاربران. "
            "Equipment و injury عمداً حذف شدند. Candidate rejection categoryهای duration از wrapper تشخیصی همان run "
            "گرفته شده‌اند؛ آن‌ها تعداد ارزیابی/رد را نشان می‌دهند و می‌توانند برای یک Candidate بیش از یک constraint ثبت کنند.</p>",
            "</body></html>",
        ]
    )
    return "".join(parts)


def render_report(raw_path: Path, html_path: Path, pdf_path: Path, summary_path: Path) -> None:
    payload = cast(dict[str, object], json.loads(raw_path.read_text(encoding="utf-8")))
    report_html = _render(payload, raw_path)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(report_html, encoding="utf-8")
    HTML(string=report_html, base_url=str(html_path.parent)).write_pdf(pdf_path)
    summary = {
        "schema_version": payload["schema_version"],
        "generated_at_utc": payload["generated_at_utc"],
        "raw_sha256": _sha256(raw_path),
        "pdf_sha256": _sha256(pdf_path),
        "coverage": payload["coverage"],
        "provenance": payload["provenance"],
        "aggregates": payload["aggregates"],
        "competition_cases": [
            {
                "case_id": item["case_id"],
                "final_selected_template": item["final_selected_template"],
                "final_split_type": item["final_split_type"],
                "attempt_sequence": item["attempt_sequence"],
            }
            for item in cast(Sequence[Mapping[str, object]], payload["competition_cases"])
        ],
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    compressed_path = raw_path.with_suffix(raw_path.suffix + ".gz")
    with raw_path.open("rb") as source, gzip.open(compressed_path, "wb", compresslevel=9) as target:
        while chunk := source.read(1024 * 1024):
            target.write(chunk)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the Persian template survival PDF.")
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path("../reports/fitsho_4_5_6_day_template_survival_raw.json"),
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=Path("../reports/fitsho_4_5_6_day_template_survival_debug_report.html"),
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path("../reports/fitsho_4_5_6_day_template_survival_debug_report.pdf"),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("../reports/fitsho_4_5_6_day_template_survival_summary.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    render_report(
        args.raw.resolve(),
        args.html.resolve(),
        args.pdf.resolve(),
        args.summary.resolve(),
    )
    print(str(args.pdf.resolve()))


if __name__ == "__main__":
    main()
