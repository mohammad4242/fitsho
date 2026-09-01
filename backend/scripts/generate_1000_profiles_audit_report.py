from __future__ import annotations

import json
import os
import shutil
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from typing import Any
from uuid import UUID

import weasyprint
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.main  # Ensure all SQLAlchemy models and relationships are registered
from app.workout_reviews.models import WorkoutPlanReview  # Ensure models loaded
from app.config import get_settings
from app.exercises.models import Exercise
from app.workouts.benchmarks.cohort_generator import (
    BENCHMARK_SEED,
    FA_TRANSLATIONS,
    ProfileSpec,
    generate_1000_profiles,
    validate_dataset_sanity,
)
from app.workouts.benchmarks.benchmark_evaluator import (
    evaluate_single_profile,
    format_program_days,
)
from app.training_templates.engine_reference import load_template_references
from app.workouts.service import WorkoutGenerationService
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET


# Global worker context for multiprocessing
_worker_catalog = None
_worker_refs = None
_worker_ex_map = None


def _init_worker(catalog, refs, ex_map):
    global _worker_catalog, _worker_refs, _worker_ex_map
    _worker_catalog = catalog
    _worker_refs = refs
    _worker_ex_map = ex_map


def _eval_worker(profile: ProfileSpec) -> dict[str, Any]:
    global _worker_catalog, _worker_refs, _worker_ex_map
    return evaluate_single_profile(
        profile,
        _worker_catalog,
        _worker_refs,
        _worker_ex_map,
        ruleset=RULESET,
    )


def run_benchmark(max_workers: int = 16) -> tuple[list[ProfileSpec], list[dict[str, Any]], dict[str, Any]]:
    print(f"1. Generating 1000 profiles with deterministic seed={BENCHMARK_SEED}...")
    profiles = generate_1000_profiles(BENCHMARK_SEED)

    print("2. Validating dataset sanity and checking for artificial correlation/bias...")
    sanity_report = validate_dataset_sanity(profiles)
    print(
        f"   Sanity check passed: {sanity_report['zero_caution_count']} healthy ({sanity_report['zero_caution_pct']:.1f}%), "
        f"{sanity_report['one_caution_count']} 1-caution ({sanity_report['one_caution_pct']:.1f}%), "
        f"{sanity_report['two_caution_count']} 2-cautions ({sanity_report['two_caution_pct']:.1f}%)."
    )

    # Save inputs before evaluation
    os.makedirs("/home/mohammad/project/fitsho/artifacts", exist_ok=True)
    inputs_path = f"/home/mohammad/project/fitsho/artifacts/fitsho_1000_profiles_seed_{BENCHMARK_SEED}.json"
    with open(inputs_path, "w", encoding="utf-8") as f:
        json.dump([p.to_dict() for p in profiles], f, ensure_ascii=False, indent=2)
    print(f"3. Saved 1000 input profiles BEFORE evaluation to {inputs_path}")

    # Load shared catalog, references, exercise names
    print("4. Loading catalog and template references from database...")
    settings = get_settings()
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        service = WorkoutGenerationService(session, settings=None)
        catalog = service._load_catalog()
        refs = load_template_references(session)
        ex_list = session.scalars(select(Exercise)).all()
        ex_map = {ex.id: {"name_fa": ex.name_fa, "name_en": ex.name_en} for ex in ex_list}
    print(f"   Loaded {len(catalog)} exercises and {len(refs)} reference templates.")

    # Run parallel evaluation
    print(f"5. Evaluating 1000 profiles using ProcessPoolExecutor with {max_workers} workers...")
    t0 = time.time()
    results = []
    with ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=_init_worker,
        initargs=(catalog, refs, ex_map),
    ) as executor:
        for idx, res in enumerate(executor.map(_eval_worker, profiles), start=1):
            results.append(res)
            if idx % 100 == 0:
                elapsed = time.time() - t0
                print(f"   Completed {idx}/1000 profiles ({elapsed:.1f}s, {elapsed/idx:.2f}s/profile)...")

    total_time = time.time() - t0
    print(f"   Evaluation complete in {total_time:.1f} seconds.")

    # Save results
    results_path = f"/home/mohammad/project/fitsho/artifacts/fitsho_1000_profiles_results_seed_{BENCHMARK_SEED}.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"6. Saved 1000 evaluation results to {results_path}")

    return profiles, results, sanity_report


def build_persian_pdf_html(
    profiles: list[ProfileSpec],
    results: list[dict[str, Any]],
    sanity_report: dict[str, Any],
) -> str:
    total = len(results)
    success_count = sum(1 for r in results if r["result_class"] == "SUCCESS")
    failed_count = sum(1 for r in results if r["result_class"] == "FAILED")
    unsupported_count = sum(1 for r in results if r["result_class"] == "UNSUPPORTED")

    assert success_count + failed_count + unsupported_count == total

    supported_profiles = success_count + failed_count
    coverage_rate = (supported_profiles / total) * 100
    success_rate_supported = (success_count / supported_profiles * 100) if supported_profiles > 0 else 0
    unsupported_rate = (unsupported_count / total) * 100

    # Path stats
    bw_succ = sum(1 for r in results if r["generation_path"] == "bodyweight_fixed_template" and r["result_class"] == "SUCCESS")
    bw_fail = sum(1 for r in results if r["generation_path"] == "bodyweight_fixed_template" and r["result_class"] == "FAILED")
    bw_total_supported = bw_succ + bw_fail
    bw_success_rate = (bw_succ / bw_total_supported * 100) if bw_total_supported > 0 else 0

    engine_succ = sum(1 for r in results if r["generation_path"] == "program_engine" and r["result_class"] == "SUCCESS")
    engine_fail = sum(1 for r in results if r["generation_path"] == "program_engine" and r["result_class"] == "FAILED")
    engine_total_supported = engine_succ + engine_fail
    engine_success_rate = (engine_succ / engine_total_supported * 100) if engine_total_supported > 0 else 0

    # Unsupported breakdown
    unsupported_bw_level = sum(1 for r in results if r.get("unsupported_subtype") == "BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED")
    unsupported_bw_days = sum(1 for r in results if r.get("unsupported_subtype") == "BODYWEIGHT_TEMPLATE_DAYS_NOT_SUPPORTED")
    unsupported_compat_days = sum(1 for r in results if r.get("unsupported_subtype") == "UNSUPPORTED_RESISTANCE_TRAINING_DAYS")
    unsupported_safety = sum(1 for r in results if r.get("unsupported_subtype") == "EXPECTED_SAFETY_REJECTION")

    # Failure causes count
    real_failure_causes: dict[str, int] = {}
    for r in results:
        if r["result_class"] == "FAILED":
            cause = r.get("root_cause") or r.get("final_error_code") or "UNKNOWN_FAILURE"
            real_failure_causes[cause] = real_failure_causes.get(cause, 0) + 1

    top_failure_causes = sorted(real_failure_causes.items(), key=lambda x: x[1], reverse=True)

    # Cohort breakdown: Location/Setup
    cohort_gym_succ = sum(1 for r in results if r["profile"]["training_location"] == "gym" and r["result_class"] == "SUCCESS")
    cohort_gym_fail = sum(1 for r in results if r["profile"]["training_location"] == "gym" and r["result_class"] == "FAILED")
    cohort_gym_total = cohort_gym_succ + cohort_gym_fail

    cohort_db_succ = sum(1 for r in results if r["profile"]["training_location"] == "home" and r["profile"]["home_training_setup"] == "dumbbells_available" and r["result_class"] == "SUCCESS")
    cohort_db_fail = sum(1 for r in results if r["profile"]["training_location"] == "home" and r["profile"]["home_training_setup"] == "dumbbells_available" and r["result_class"] == "FAILED")
    cohort_db_total = cohort_db_succ + cohort_db_fail

    # Cohort breakdown: Experience Level (supported only)
    level_stats: dict[str, dict[str, int]] = {}
    for lvl in ["first_month", "beginner", "intermediate", "advanced"]:
        s = sum(1 for r in results if r["profile"]["experience_level"] == lvl and r["result_class"] == "SUCCESS")
        f = sum(1 for r in results if r["profile"]["experience_level"] == lvl and r["result_class"] == "FAILED")
        level_stats[lvl] = {"success": s, "failed": f, "total": s + f}

    # Caution breakdown (supported only)
    c0_s = sum(1 for r in results if len(r["profile"]["training_cautions"]) == 0 and r["result_class"] == "SUCCESS")
    c0_f = sum(1 for r in results if len(r["profile"]["training_cautions"]) == 0 and r["result_class"] == "FAILED")
    c1_s = sum(1 for r in results if len(r["profile"]["training_cautions"]) == 1 and r["result_class"] == "SUCCESS")
    c1_f = sum(1 for r in results if len(r["profile"]["training_cautions"]) == 1 and r["result_class"] == "FAILED")
    c2_s = sum(1 for r in results if len(r["profile"]["training_cautions"]) >= 2 and r["result_class"] == "SUCCESS")
    c2_f = sum(1 for r in results if len(r["profile"]["training_cautions"]) >= 2 and r["result_class"] == "FAILED")

    # Fixed bodyweight breakdown:
    bw_days_stats: dict[str, dict[str, int]] = {}
    for lvl in ["first_month", "beginner"]:
        for d in [2, 3, 4]:
            key = f"{lvl}_{d}d"
            s = sum(
                1 for r in results
                if r["generation_path"] == "bodyweight_fixed_template"
                and r["profile"]["experience_level"] == lvl
                and r["profile"]["training_days_per_week"] == d
                and r["result_class"] == "SUCCESS"
            )
            f = sum(
                1 for r in results
                if r["generation_path"] == "bodyweight_fixed_template"
                and r["profile"]["experience_level"] == lvl
                and r["profile"]["training_days_per_week"] == d
                and r["result_class"] == "FAILED"
            )
            bw_days_stats[key] = {"success": s, "failed": f, "total": s + f}

    css = """
    @page {
        size: A4 portrait;
        margin: 10mm 10mm 12mm 10mm;
        @bottom-left {
            content: "بنچ‌مارک ۱۰۰۰ پروفایل سیستم تمرینی Fitsho (Seed: 20260902)";
            font-family: 'Vazirmatn', sans-serif;
            font-size: 7pt;
            color: #557069;
        }
        @bottom-right {
            content: "صفحه " counter(page) " از " counter(pages);
            font-family: 'Vazirmatn', sans-serif;
            font-size: 7pt;
            color: #557069;
        }
    }
    * { box-sizing: border-box; }
    body {
        font-family: 'Vazirmatn', 'DejaVu Sans', sans-serif;
        font-size: 7.5pt;
        line-height: 1.45;
        direction: rtl;
        text-align: right;
        color: #112824;
        background-color: #ffffff;
    }
    .header-box {
        background: linear-gradient(135deg, #074e43 0%, #0d6e5e 100%);
        color: #ffffff;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    .header-title {
        font-size: 14pt;
        font-weight: bold;
        margin: 0 0 3px 0;
    }
    .header-subtitle {
        font-size: 8pt;
        opacity: 0.92;
        margin: 0;
    }
    .summary-card {
        background: #f2f9f7;
        border: 1px solid #c2e2da;
        border-radius: 6px;
        padding: 10px 12px;
        margin-bottom: 12px;
        page-break-inside: avoid;
    }
    .summary-stats {
        display: flex;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 8px;
        border-bottom: 1px dashed #afd5cb;
        padding-bottom: 6px;
    }
    .stat-badge {
        display: inline-block;
        background: #ffffff;
        border: 1px solid #afd5cb;
        border-radius: 4px;
        padding: 3px 7px;
        font-size: 7.5pt;
    }
    .stat-badge strong {
        color: #0d6e5e;
    }
    .stat-badge.success strong {
        color: #097e44;
    }
    .stat-badge.error strong {
        color: #c92a2a;
    }
    .stat-badge.unsupported strong {
        color: #d97706;
    }
    .main-metrics-banner {
        background: #ffffff;
        border: 2px solid #0d6e5e;
        border-radius: 5px;
        padding: 8px 12px;
        margin: 8px 0;
        display: flex;
        justify-content: space-around;
        text-align: center;
    }
    .main-metric-item {
        flex: 1;
    }
    .main-metric-val {
        font-size: 13pt;
        font-weight: bold;
        color: #074e43;
    }
    .main-metric-lbl {
        font-size: 7.2pt;
        color: #475569;
    }
    table.data-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 7.2pt;
        margin: 8px 0;
    }
    table.data-table th {
        background: #0d6e5e;
        color: #ffffff;
        padding: 5px 8px;
        text-align: right;
        font-weight: bold;
        border: 1px solid #074e43;
    }
    table.data-table td {
        padding: 4px 8px;
        border: 1px solid #cbd5e1;
    }
    .audit-box {
        background: #ffffff;
        border-right: 4px solid #0d6e5e;
        border-radius: 4px;
        padding: 6px 10px;
        font-size: 7.2pt;
        line-height: 1.5;
        color: #203833;
        margin: 6px 0;
    }
    .user-section {
        page-break-inside: avoid;
        border: 1px solid #cee0dc;
        border-radius: 5px;
        margin-bottom: 10px;
        background: #ffffff;
        overflow: hidden;
    }
    .user-section.success-section {
        border-right: 5px solid #097e44;
    }
    .user-section.failed-section {
        border-right: 5px solid #c92a2a;
    }
    .user-section.unsupported-section {
        border-right: 5px solid #d97706;
    }
    .user-header {
        background: #eef6f4;
        border-bottom: 1px solid #cee0dc;
        padding: 5px 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .user-title {
        font-size: 8.8pt;
        font-weight: bold;
        color: #074e43;
        margin: 0;
    }
    .status-badge {
        padding: 2px 7px;
        border-radius: 3px;
        font-size: 7pt;
        font-weight: bold;
    }
    .status-badge.success {
        background: #dcfce7;
        color: #166534;
        border: 1px solid #86efac;
    }
    .status-badge.fail {
        background: #fee2e2;
        color: #991b1b;
        border: 1px solid #fca5a5;
    }
    .status-badge.unsupported {
        background: #fef3c7;
        color: #92400e;
        border: 1px solid #fcd34d;
    }
    .path-badge {
        background: #e0f2fe;
        color: #0369a1;
        border: 1px solid #bae6fd;
        padding: 1px 5px;
        border-radius: 3px;
        font-size: 6.8pt;
        margin-left: 5px;
    }
    .profile-grid {
        padding: 6px 10px;
        background: #fbfdfc;
        border-bottom: 1px solid #e2ece9;
        font-size: 7.2pt;
    }
    .profile-row {
        display: flex;
        flex-wrap: wrap;
        margin-bottom: 2px;
    }
    .profile-item {
        flex: 1;
        min-width: 140px;
    }
    .profile-label {
        color: #557069;
        font-weight: bold;
    }
    .profile-value {
        color: #112824;
    }
    .days-container {
        padding: 6px 10px;
        background: #ffffff;
    }
    .program-overview-bar {
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        padding: 4px 8px;
        border-radius: 4px;
        margin-bottom: 6px;
        color: #065f46;
        font-size: 7.2pt;
    }
    .day-block {
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        margin-bottom: 6px;
        overflow: hidden;
    }
    .day-title-bar {
        background: #f8fafc;
        border-bottom: 1px solid #e2e8f0;
        padding: 4px 8px;
        display: flex;
        justify-content: space-between;
        font-weight: bold;
        color: #1e293b;
        font-size: 7.2pt;
    }
    table.exercise-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 7pt;
    }
    table.exercise-table th {
        background: #f1f5f9;
        color: #475569;
        padding: 3px 6px;
        text-align: right;
        border-bottom: 1px solid #cbd5e1;
        font-weight: bold;
    }
    table.exercise-table td {
        padding: 3px 6px;
        border-bottom: 1px solid #f1f5f9;
    }
    td.ex-num {
        width: 20px;
        text-align: center;
        color: #64748b;
    }
    td.ex-name {
        font-weight: bold;
        color: #0f172a;
    }
    .fail-detail-box {
        padding: 8px 10px;
        background: #fffafa;
    }
    .fail-header-line {
        display: flex;
        justify-content: space-between;
        margin-bottom: 4px;
        font-weight: bold;
        color: #991b1b;
        font-size: 7.2pt;
    }
    .fail-desc {
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 4px;
        padding: 5px 8px;
        margin-bottom: 6px;
        color: #7f1d1d;
        line-height: 1.45;
        font-size: 7.2pt;
    }
    .fail-meta-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 3px 6px;
        font-size: 7pt;
        background: #ffffff;
        border: 1px solid #f3e8e8;
        padding: 5px 8px;
        border-radius: 4px;
        margin-bottom: 5px;
    }
    .fail-meta-item span.lbl {
        color: #7f1d1d;
        font-weight: bold;
    }
    .fail-meta-item span.val {
        color: #334155;
    }
    .repair-hint {
        background: #fffbeb;
        border: 1px dashed #fcd34d;
        border-radius: 4px;
        padding: 4px 7px;
        color: #92400e;
        font-size: 7pt;
    }
    .unsupported-box {
        padding: 8px 10px;
        background: #fffdf5;
    }
    .unsupported-desc {
        background: #fef3c7;
        border: 1px solid #fde68a;
        border-radius: 4px;
        padding: 5px 8px;
        color: #92400e;
        font-size: 7.2pt;
        line-height: 1.45;
    }
    code {
        font-family: monospace;
        background: #f1f5f9;
        padding: 1px 3px;
        border-radius: 2px;
        font-size: 6.8pt;
        color: #0f172a;
    }
    </style>
    """

    html = f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>گزارش علمی و عینی ارزیابی ۱۰۰۰ پروفایل سیستم تمرینی Fitsho</title>
<style>{css}</style>
</head>
<body>

<div class="header-box">
    <div class="header-title">گزارش علمی و تجدیدپذیر بنچ‌مارک ۱۰۰۰ پروفایل سیستم تمرین Fitsho</div>
    <div class="header-subtitle">ارزیابی عینی و بدون اریب موتور تمرین با تفکیک مسیرها و جداسازی کوهورت پشتیبانی‌نشده | Seed: {BENCHMARK_SEED} | تاریخ: ۱۴۰۵/۰۶/۱۲</div>
</div>

<div class="summary-card">
    <div class="summary-stats">
        <span class="stat-badge">کل پروفایل‌ها: <strong>{total}</strong></span>
        <span class="stat-badge success">موفق (SUCCESS): <strong>{success_count}</strong></span>
        <span class="stat-badge error">ناموفق واقعی (FAILED): <strong>{failed_count}</strong></span>
        <span class="stat-badge unsupported">پشتیبانی‌نشده عمدی (UNSUPPORTED): <strong>{unsupported_count} ({unsupported_rate:.1f}٪)</strong></span>
    </div>

    <div class="main-metrics-banner">
        <div class="main-metric-item">
            <div class="main-metric-val">{success_rate_supported:.2f}٪</div>
            <div class="main-metric-lbl">نرخ موفقیت کاربران پشتیبانی‌شده (Supported Success Rate)</div>
        </div>
        <div class="main-metric-item">
            <div class="main-metric-val">{engine_success_rate:.2f}٪</div>
            <div class="main-metric-lbl">نرخ موفقیت موتور تمرین نرمال (Normal Program Engine)</div>
        </div>
        <div class="main-metric-item">
            <div class="main-metric-val">{bw_success_rate:.2f}٪</div>
            <div class="main-metric-lbl">نرخ موفقیت تمپلیت‌های ثابت وزن بدن (Fixed Bodyweight)</div>
        </div>
        <div class="main-metric-item">
            <div class="main-metric-val">{coverage_rate:.2f}٪</div>
            <div class="main-metric-lbl">نرخ پوشش قرارداد محصول (Product Coverage Rate)</div>
        </div>
    </div>

    <div class="audit-box">
        <strong>قواعد تفکیک ریاضی ارزیابی (Ground-Truth Contract):</strong><br>
        • <strong>کاربران پشتیبانی‌شده ({supported_profiles} نفر):</strong> مجموعاً {success_count} نفر با موفقیت برنامه دریافت کردند ({success_rate_supported:.2f}٪) و {failed_count} نفر با خطای واقعی موتور مواجه شدند.<br>
        • <strong>جداسازی کوهورت پشتیبانی‌نشده ({unsupported_count} نفر):</strong> این {unsupported_count} پروفایل (شامل کاربران سطح متوسط/پیشرفته فقط وزن بدن، روزهای ناسازگار فیزیولوژیک و ارجاع‌های غربالگری ایمنی) طبق قرارداد مصوب فیتشو عمداً خارج از مخرج محاسبه موفقیت قرار گرفته‌اند تا نرخ موفقیت واقعی بدون اریب محاسبه شود.
    </div>

    <h3 style="font-size: 8.5pt; color: #074e43; margin: 8px 0 4px 0;">۱. تفکیک نتایج بر اساس مسیر تولید برنامه (Generation Route)</h3>
    <table class="data-table">
        <thead>
            <tr>
                <th>مسیر تولید برنامه</th>
                <th style="width: 80px; text-align: center;">موفق</th>
                <th style="width: 80px; text-align: center;">ناموفق واقعی</th>
                <th style="width: 80px; text-align: center;">مجموع پشتیبانی‌شده</th>
                <th style="width: 90px; text-align: center;">درصد موفقیت</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>تمپلیت‌های ثابت وزن بدن (Fixed Bodyweight Templates)</strong></td>
                <td style="text-align: center; color: #166534; font-weight: bold;">{bw_succ}</td>
                <td style="text-align: center; color: #991b1b; font-weight: bold;">{bw_fail}</td>
                <td style="text-align: center; font-weight: bold;">{bw_total_supported}</td>
                <td style="text-align: center; font-weight: bold;">{bw_success_rate:.2f}٪</td>
            </tr>
            <tr>
                <td><strong>موتور تمرینی هوشمند (Normal Program Engine)</strong></td>
                <td style="text-align: center; color: #166534; font-weight: bold;">{engine_succ}</td>
                <td style="text-align: center; color: #991b1b; font-weight: bold;">{engine_fail}</td>
                <td style="text-align: center; font-weight: bold;">{engine_total_supported}</td>
                <td style="text-align: center; font-weight: bold;">{engine_success_rate:.2f}٪</td>
            </tr>
            <tr style="background: #fffbeb;">
                <td><strong>کوهورت پشتیبانی‌نشده عمدی (خارج از مخرج نرخ موفقیت)</strong></td>
                <td style="text-align: center;">-</td>
                <td style="text-align: center;">-</td>
                <td style="text-align: center; font-weight: bold;">{unsupported_count}</td>
                <td style="text-align: center; color: #d97706; font-weight: bold;">رد عمدی ({unsupported_rate:.1f}٪)</td>
            </tr>
        </tbody>
    </table>

    <div style="display: flex; gap: 10px; margin-top: 6px;">
        <div style="flex: 1;">
            <h3 style="font-size: 8.5pt; color: #074e43; margin: 4px 0;">۲. علل اصلی شکست در موتور تمرینی (Top Failure Causes)</h3>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>علت ریشه‌ای خطا (Root Cause)</th>
                        <th style="width: 50px; text-align: center;">تعداد</th>
                        <th style="width: 60px; text-align: center;">سهم از شکست‌ها</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(f"<tr><td><code>{k}</code></td><td style='text-align: center; font-weight: bold;'>{v}</td><td style='text-align: center;'>{v/failed_count*100:.1f}٪</td></tr>" for k, v in top_failure_causes[:8]) if failed_count > 0 else "<tr><td colspan='3' style='text-align:center;'>بدون خطای شکست</td></tr>"}
                </tbody>
            </table>
        </div>
        <div style="flex: 1;">
            <h3 style="font-size: 8.5pt; color: #074e43; margin: 4px 0;">۳. تفکیک کوهورت پشتیبانی‌نشده (Unsupported Breakdown)</h3>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>دلیل عدم پشتیبانی طبق قرارداد محصول</th>
                        <th style="width: 50px; text-align: center;">تعداد</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td>وزن بدن خانگی + سطوح متوسط و پیشرفته</td><td style="text-align: center; font-weight: bold;">{unsupported_bw_level}</td></tr>
                    <tr><td>روزهای ناسازگار برای تمپلیت وزن بدن (غیر از ۲، ۳، ۴ روز)</td><td style="text-align: center; font-weight: bold;">{unsupported_bw_days}</td></tr>
                    <tr><td>روزهای ناسازگار با سابقه در ماتریس مقاومت</td><td style="text-align: center; font-weight: bold;">{unsupported_compat_days}</td></tr>
                    <tr><td>ارجاع پزشکی در غربالگری ایمنی (قرمزی علائم / بارداری / عدم کنترل)</td><td style="text-align: center; font-weight: bold;">{unsupported_safety}</td></tr>
                    <tr style="font-weight: bold; background: #f1f5f9;"><td>مجموع کاربران پشتیبانی‌نشده عمدی</td><td style="text-align: center;">{unsupported_count}</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <h3 style="font-size: 8.5pt; color: #074e43; margin: 8px 0 4px 0;">۴. تفکیک نرخ موفقیت بر اساس محیط تمرین، سطح تجربه و آسیب‌ها (Supported Cohorts)</h3>
    <table class="data-table">
        <thead>
            <tr>
                <th>متغیر کوهورت</th>
                <th style="width: 90px; text-align: center;">کل پشتیبانی‌شده</th>
                <th style="width: 80px; text-align: center;">موفق</th>
                <th style="width: 80px; text-align: center;">ناموفق</th>
                <th style="width: 90px; text-align: center;">درصد موفقیت</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>باشگاه ورزشی (GYM)</strong></td>
                <td style="text-align: center;">{cohort_gym_total}</td>
                <td style="text-align: center; color: #166534; font-weight: bold;">{cohort_gym_succ}</td>
                <td style="text-align: center; color: #991b1b;">{cohort_gym_fail}</td>
                <td style="text-align: center; font-weight: bold;">{(cohort_gym_succ / cohort_gym_total * 100) if cohort_gym_total > 0 else 0:.2f}٪</td>
            </tr>
            <tr>
                <td><strong>منزل + دمبل (HOME + DUMBBELLS)</strong></td>
                <td style="text-align: center;">{cohort_db_total}</td>
                <td style="text-align: center; color: #166534; font-weight: bold;">{cohort_db_succ}</td>
                <td style="text-align: center; color: #991b1b;">{cohort_db_fail}</td>
                <td style="text-align: center; font-weight: bold;">{(cohort_db_succ / cohort_db_total * 100) if cohort_db_total > 0 else 0:.2f}٪</td>
            </tr>
            <tr>
                <td><strong>منزل + فقط وزن بدن (HOME + BODYWEIGHT)</strong></td>
                <td style="text-align: center;">{bw_total_supported}</td>
                <td style="text-align: center; color: #166534; font-weight: bold;">{bw_succ}</td>
                <td style="text-align: center; color: #991b1b;">{bw_fail}</td>
                <td style="text-align: center; font-weight: bold;">{bw_success_rate:.2f}٪</td>
            </tr>
            <tr style="background: #f8fafc;">
                <td>سطح: ماه اول (First Month)</td>
                <td style="text-align: center;">{level_stats['first_month']['total']}</td>
                <td style="text-align: center;">{level_stats['first_month']['success']}</td>
                <td style="text-align: center;">{level_stats['first_month']['failed']}</td>
                <td style="text-align: center; font-weight: bold;">{(level_stats['first_month']['success'] / level_stats['first_month']['total'] * 100) if level_stats['first_month']['total'] > 0 else 0:.2f}٪</td>
            </tr>
            <tr style="background: #f8fafc;">
                <td>سطح: مبتدی (Beginner)</td>
                <td style="text-align: center;">{level_stats['beginner']['total']}</td>
                <td style="text-align: center;">{level_stats['beginner']['success']}</td>
                <td style="text-align: center;">{level_stats['beginner']['failed']}</td>
                <td style="text-align: center; font-weight: bold;">{(level_stats['beginner']['success'] / level_stats['beginner']['total'] * 100) if level_stats['beginner']['total'] > 0 else 0:.2f}٪</td>
            </tr>
            <tr style="background: #f8fafc;">
                <td>سطح: متوسط (Intermediate)</td>
                <td style="text-align: center;">{level_stats['intermediate']['total']}</td>
                <td style="text-align: center;">{level_stats['intermediate']['success']}</td>
                <td style="text-align: center;">{level_stats['intermediate']['failed']}</td>
                <td style="text-align: center; font-weight: bold;">{(level_stats['intermediate']['success'] / level_stats['intermediate']['total'] * 100) if level_stats['intermediate']['total'] > 0 else 0:.2f}٪</td>
            </tr>
            <tr style="background: #f8fafc;">
                <td>سطح: پیشرفته (Advanced)</td>
                <td style="text-align: center;">{level_stats['advanced']['total']}</td>
                <td style="text-align: center;">{level_stats['advanced']['success']}</td>
                <td style="text-align: center;">{level_stats['advanced']['failed']}</td>
                <td style="text-align: center; font-weight: bold;">{(level_stats['advanced']['success'] / level_stats['advanced']['total'] * 100) if level_stats['advanced']['total'] > 0 else 0:.2f}٪</td>
            </tr>
            <tr>
                <td>کاربران بدون آسیب (۰ محدودیت)</td>
                <td style="text-align: center;">{c0_s + c0_f}</td>
                <td style="text-align: center;">{c0_s}</td>
                <td style="text-align: center;">{c0_f}</td>
                <td style="text-align: center; font-weight: bold;">{(c0_s / (c0_s + c0_f) * 100) if (c0_s + c0_f) > 0 else 0:.2f}٪</td>
            </tr>
            <tr>
                <td>کاربران دارای ۱ آسیب فیزیکی</td>
                <td style="text-align: center;">{c1_s + c1_f}</td>
                <td style="text-align: center;">{c1_s}</td>
                <td style="text-align: center;">{c1_f}</td>
                <td style="text-align: center; font-weight: bold;">{(c1_s / (c1_s + c1_f) * 100) if (c1_s + c1_f) > 0 else 0:.2f}٪</td>
            </tr>
            <tr>
                <td>کاربران دارای ۲ آسیب همزمان</td>
                <td style="text-align: center;">{c2_s + c2_f}</td>
                <td style="text-align: center;">{c2_s}</td>
                <td style="text-align: center;">{c2_f}</td>
                <td style="text-align: center; font-weight: bold;">{(c2_s / (c2_s + c2_f) * 100) if (c2_s + c2_f) > 0 else 0:.2f}٪</td>
            </tr>
        </tbody>
    </table>
</div>

<h2 style="font-size: 10pt; color: #074e43; border-bottom: 2px solid #0d6e5e; padding-bottom: 4px; margin: 14px 0 10px 0;">
    کارنامه تفصیلی ۱۰۰۰ پروفایل کاربر (خلاصه پروفایل در ابتدا، سپس برنامه تمرینی یا تشخیص رد)
</h2>
"""

    for r in results:
        p_dict = r["profile"]
        res_class = r["result_class"]
        gen_path = r.get("generation_path", "program_engine")
        template_slug = r.get("template_slug")
        is_success = (res_class == "SUCCESS")
        is_unsupported = (res_class == "UNSUPPORTED")

        if is_success:
            section_class = "success-section"
            badge = '<span class="status-badge success">برنامه صادر شد (SUCCESS)</span>'
        elif is_unsupported:
            section_class = "unsupported-section"
            badge = '<span class="status-badge unsupported">پشتیبانی‌نشده عمدی (UNSUPPORTED)</span>'
        else:
            section_class = "failed-section"
            badge = '<span class="status-badge fail">خطای تولید برنامه (FAILED)</span>'

        path_label = FA_TRANSLATIONS.get(gen_path, gen_path)
        if template_slug:
            path_label += f" · <code>{template_slug}</code>"
        path_tag = f'<span class="path-badge">{path_label}</span>'

        sex_fa = FA_TRANSLATIONS.get(p_dict["sex"], p_dict["sex"])
        goal_fa = FA_TRANSLATIONS.get(p_dict["fitness_goal"], p_dict["fitness_goal"])
        level_fa = FA_TRANSLATIONS.get(p_dict["experience_level"], p_dict["experience_level"])
        loc_fa = FA_TRANSLATIONS.get(p_dict["training_location"], p_dict["training_location"])
        setup_fa = (
            FA_TRANSLATIONS.get(p_dict["home_training_setup"], p_dict["home_training_setup"])
            if p_dict.get("home_training_setup")
            else "تجهیزات کامل باشگاه"
        )
        pri_fa = (
            FA_TRANSLATIONS.get(p_dict["priority_muscle"], p_dict["priority_muscle"])
            if p_dict.get("priority_muscle")
            else "بدون اولویت اختصاصی"
        )
        cautions_fa = (
            "، ".join(FA_TRANSLATIONS.get(c, c) for c in p_dict["training_cautions"])
            if p_dict.get("training_cautions")
            else "بدون آسیب فیزیکی"
        )

        height_m = p_dict["height_cm"] / 100.0
        bmi = round(p_dict["weight_kg"] / (height_m * height_m), 1)

        html += f"""
<div class="user-section {section_class}">
    <div class="user-header">
        <div>
            <span class="user-title">پروفایل #{r['profile_id']:04d}: {p_dict['name']}</span>
            {path_tag}
        </div>
        {badge}
    </div>

    <div class="profile-grid">
        <div class="profile-row">
            <div class="profile-item"><span class="profile-label">سن و جنسیت:</span> <span class="profile-value">{p_dict['age']} سال · {sex_fa}</span></div>
            <div class="profile-item"><span class="profile-label">قد و وزن و BMI:</span> <span class="profile-value">{p_dict['height_cm']} cm · {p_dict['weight_kg']} kg (BMI: {bmi})</span></div>
            <div class="profile-item"><span class="profile-label">هدف تمرینی:</span> <span class="profile-value">{goal_fa}</span></div>
        </div>
        <div class="profile-row">
            <div class="profile-item"><span class="profile-label">سطح و سابقه:</span> <span class="profile-value">{level_fa} ({p_dict['training_age_months']} ماه)</span></div>
            <div class="profile-item"><span class="profile-label">برنامه هفتگی:</span> <span class="profile-value">{p_dict['training_days_per_week']} روز · {p_dict['session_duration_minutes']} دقیقه</span></div>
            <div class="profile-item"><span class="profile-label">محیط و وسایل:</span> <span class="profile-value">{loc_fa} · {setup_fa}</span></div>
        </div>
        <div class="profile-row">
            <div class="profile-item"><span class="profile-label">عضله اولویت:</span> <span class="profile-value">{pri_fa}</span></div>
            <div class="profile-item"><span class="profile-label">طول دوره:</span> <span class="profile-value">{p_dict['plan_duration_weeks']} هفته</span></div>
            <div class="profile-item"><span class="profile-label">آسیب‌ها و محدودیت‌ها:</span> <span class="profile-value">{cautions_fa}</span></div>
        </div>
    </div>
"""

        if is_success:
            split_fa = FA_TRANSLATIONS.get(r.get("split_type"), r.get("split_type") or "-")
            days_count = r.get("days_count", 0)
            html += f"""
    <div class="days-container">
        <div class="program-overview-bar">
            <strong>ساختار برنامه صادرشده:</strong> اسپلیت <strong>{split_fa}</strong> | تعداد جلسات: <strong>{days_count} جلسه در هفته</strong> | دوره: <strong>{p_dict['plan_duration_weeks']} هفته</strong>
        </div>
"""
            for day in r.get("program_days", []):
                d_idx = day.get("day_index")
                d_title = day.get("title")
                d_dur = day.get("estimated_duration_minutes") or p_dict["session_duration_minutes"]
                d_focus = day.get("focus") or "-"
                ex_list = day.get("exercises", [])

                html += f"""
        <div class="day-block">
            <div class="day-title-bar">
                <span>جلسه {d_idx}: {d_title} (تمرکز: {d_focus})</span>
                <span>زمان تخمینی: {d_dur} دقیقه · {len(ex_list)} حرکت تمرینی</span>
            </div>
            <table class="exercise-table">
                <thead>
                    <tr>
                        <th class="ex-num">#</th>
                        <th>نام تمرین (بانک حرکات فیتشو)</th>
                        <th style="width: 80px;">عضله هدف</th>
                        <th style="width: 100px;">ست × تکرار / زمان</th>
                        <th style="width: 60px; text-align: center;">استراحت</th>
                        <th style="width: 50px; text-align: center;">شدت (RIR)</th>
                    </tr>
                </thead>
                <tbody>
"""
                for it in ex_list:
                    if it["prescription_mode"] == "reps":
                        presc_str = f"{it['sets']} ست × {it['rep_min']}–{it['rep_max']} تکرار"
                    else:
                        d_min = it.get("duration_min_seconds") or 20
                        d_max = it.get("duration_max_seconds") or 40
                        presc_str = f"{it['sets']} ست × {d_min}–{d_max} ثانیه"

                    rir_str = f"RIR {it['rir']}" if it["rir"] is not None else "-"

                    html += f"""
                    <tr>
                        <td class="ex-num">{it['order']}</td>
                        <td class="ex-name">{it['name_fa']} <span style="color: #64748b; font-size: 6pt;">({it['name_en']})</span></td>
                        <td>{it['primary_muscle_fa']}</td>
                        <td>{presc_str}</td>
                        <td style="text-align: center;">{it['rest_seconds']} ثانیه</td>
                        <td style="text-align: center;">{rir_str}</td>
                    </tr>
"""
                html += """
                </tbody>
            </table>
        </div>
"""
            html += "    </div>"

        elif is_unsupported:
            subtype = r.get("unsupported_subtype") or "UNSUPPORTED"
            finfo = r.get("failure_info", {})
            html += f"""
    <div class="unsupported-box">
        <div class="unsupported-desc">
            <strong>علت عدم پشتیبانی و رد عمدی طبق قرارداد فیتشو:</strong><br>
            دسته: <code>{subtype}</code> — {finfo.get('exact_description_fa')}<br>
            <span style="font-size: 6.8pt; color: #78350f;">(این پروفایل طبق ضوابط محصول فیتشو خارج از محدوده تحت پوشش است و در مخرج نرخ موفقیت لحاظ نمی‌شود)</span>
        </div>
    </div>
"""

        else:
            finfo = r.get("failure_info", {})
            html += f"""
    <div class="fail-detail-box">
        <div class="fail-header-line">
            <span>کد خطای تخصصی: <code>{finfo.get('root_cause')}</code></span>
            <span>کد خطا در API: <code>{finfo.get('final_error_code')}</code></span>
        </div>
        <div class="fail-desc">
            <strong>علت دقیق عدم امکان تولید برنامه:</strong><br>
            {finfo.get('exact_description_fa')}
        </div>
        <div class="fail-meta-grid">
            <div class="fail-meta-item"><span class="lbl">فاز اجرایی بروز خطا:</span> <span class="val"><code>{finfo.get('failing_phase')}</code></span></div>
            <div class="fail-meta-item"><span class="lbl">فایل قانون ناظر:</span> <span class="val"><code>{finfo.get('rule_file')}</code></span></div>
            <div class="fail-meta-item"><span class="lbl">تابع ناظر در موتور:</span> <span class="val"><code>{finfo.get('rule_func')}</code></span></div>
            <div class="fail-meta-item"><span class="lbl">مقدار محاسبه‌شده:</span> <span class="val">{finfo.get('actual_val')} (حد مجاز: {finfo.get('limit_val')})</span></div>
        </div>
        <div class="repair-hint">
            🔧 <strong>راهنمای رفع مشکل در موتور (Diagnostic Hint):</strong> {finfo.get('engine_repair_hint_fa')}
        </div>
    </div>
"""

        html += "</div>\n"

    html += """
</body>
</html>
"""
    return html


def main() -> None:
    profiles, results, sanity_report = run_benchmark(max_workers=16)

    # Build Persian HTML report
    print("7. Building Persian HTML report with summary and per-profile workout plans...")
    html_content = build_persian_pdf_html(profiles, results, sanity_report)
    html_path = "/home/mohammad/project/fitsho/reports/fitsho_1000_profiles_audit_report.html"
    os.makedirs("/home/mohammad/project/fitsho/reports", exist_ok=True)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"   HTML saved to {html_path}")

    # Render PDF with WeasyPrint
    pdf_path = "/home/mohammad/project/fitsho/reports/fitsho_1000_profiles_audit_report.pdf"
    print(f"8. Rendering Persian PDF with WeasyPrint to {pdf_path} (takes ~1-2 minutes)...")
    weasyprint.HTML(string=html_content).write_pdf(pdf_path)
    size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    print(f"   PDF generated successfully: {pdf_path} ({size_mb:.2f} MB)")

    # Copy to root and public for download
    root_pdf = "/home/mohammad/project/fitsho/fitsho_1000_profiles_audit_report.pdf"
    pub_pdf = "/home/mohammad/project/fitsho/frontend/public/fitsho_1000_profiles_audit_report.pdf"
    pub_html = "/home/mohammad/project/fitsho/frontend/public/fitsho_1000_profiles_audit_report.html"

    shutil.copy2(pdf_path, root_pdf)
    shutil.copy2(pdf_path, pub_pdf)
    shutil.copy2(html_path, pub_html)
    print(f"   Copied PDF to {root_pdf} and {pub_pdf}")


if __name__ == "__main__":
    main()
