#!/usr/bin/env python3
# ruff: noqa: E501, E402
"""Evaluate 30 realistic omnivore profiles against the Fitsho nutrition engine and render a PDF report."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import weasyprint
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

import app.main  # noqa: F401 - Register all SQLAlchemy models
from app.auth.models import User
from app.config import get_settings
from app.nutrition.enums import (
    BudgetStyle,
    CookingSkill,
    DailyActivityLevel,
    DietaryPattern,
    FoodItemKind,
    MainMealCountBucket,
    MealPreparationPreference,
    NutritionOnboardingStatus,
    NutritionPlanStyle,
    PreferredVariety,
    SafetyOutcome,
    SnackCountBucket,
    StructuredExerciseSource,
    StructuredExerciseType,
    Weekday,
)
from app.nutrition.models import (
    NutritionFoodItem,
    NutritionMedicalProfile,
    NutritionPlanGeneration,
    NutritionProfile,
    NutritionSafetyDecision,
    NutritionSafetyReason,
    NutritionStructuredExercise,
    NutritionWeeklyPlan,
)
from app.nutrition.plan_service import generate_weekly_plan
from app.profile.enums import FitnessGoal, ProductMode, Sex, TrainingIntensity
from app.profile.models import BodyMeasurement, UserProfile

# Persian Translations Dictionary
FA_SEX = {"male": "مرد", "female": "زن"}
FA_GOAL = {
    "lose_weight": "کاهش وزن",
    "fat_loss": "کاهش چربی",
    "gain_weight": "افزایش وزن",
    "build_muscle": "عضله‌سازی",
    "body_recomposition": "ترکیب بدنی (ریکامپ)",
    "maintain_weight": "تثبیت وزن",
    "improve_fitness": "آمادگی جسمانی",
    "strength": "افزایش قدرت",
}
FA_ACTIVITY = {
    "sedentary": "کم‌تحرک (پشت‌میزنشین)",
    "light": "فعالیت سبک",
    "moderate": "فعالیت متوسط",
    "very_active": "بسیار پرتحرک",
}
FA_EXERCISE = {
    "resistance": "بدنسازی و قدرتی",
    "endurance": "هوازی و استقامتی",
    "mixed": "ترکیبی (قدرتی + هوازی)",
    "other": "سایر رشته‌ها",
}
FA_BUDGET_STYLE = {
    "strict": "سخت‌گیرانه",
    "flexible": "انعطاف‌پذیر (تا +۱۵٪)",
}
FA_OUTCOME = {
    "success": "موفق",
    "infeasible": "غیرقابل اجرا (محدودیت تمپلیت/بودجه)",
    "target_infeasible": "ناممکن از نظر اهداف کالری/ماکرو",
    "safety_blocked": "توقف ایمنی بالینی",
    "failed": "ناموفق",
}
FA_REASON = {
    "SAFE_FEASIBLE_DRAFT_GENERATED": "برنامه غذایی ایمن، متناسب و قابل‌اجرا با موفقیت تولید شد.",
    "NO_COMPATIBLE_TEMPLATE_SUBSTITUTE": "تمپلیت غذایی منطبق با محدودیت‌های سلیقه‌ای یا بودجه‌ای یافت نشد.",
    "INSUFFICIENT_LOW_COST_TEMPLATE_COVERAGE": "تنوع غذاهای کم‌هزینه برای بودجه کاربر کافی نیست.",
    "STRICT_BUDGET_EXCEEDED": "هزینه تخمینی رژیم از بودجه سخت‌گیرانه تعیین شده فراتر رفت.",
    "FLEXIBLE_BUDGET_CAP_EXCEEDED": "هزینه تخمینی از سقف بودجه انعطاف‌پذیر فراتر رفت.",
    "CALORIE_TARGET_OUTSIDE_TOLERANCE": "کالری کل از محدوده مجاز هدف کاربر فاصله دارد.",
    "CALORIE_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS": "تأمین کالری هدف با اندازه پرس‌های استاندارد مقدور نیست.",
    "GOAL_RESELECTION_REQUIRED": "هدف انتخابی کاربر با وضعیت بدنی یا ورزشی همخوانی ندارد و نیاز به بازبینی دارد.",
    "PHYSICIAN_MANUAL_PLAN_REQUIRED": "به دلیل ملاحظات پزشکی نیاز به رژیم دستی زیر نظر پزشک است.",
    "PREFERENCE_EXCLUSION_NO_FEASIBLE_PLAN": "حذفیات یا سلیقه‌های غذایی کاربر امکان چینش برنامه را ناممکن کرد.",
    "DIETARY_PATTERN_NOT_SUPPORTED_V1": "الگوی غذایی در نسخه ۱ پشتیبانی نمی‌شود.",
}


@dataclass
class ProfileDef:
    index: int
    name: str
    sex: str
    age: int
    height_cm: int
    weight_kg: float
    goal: str
    activity: str
    trains: bool
    ex_type: str | None
    days_per_week: int | None
    minutes_per_session: int | None
    intensity: str | None
    meals: int
    snacks: int
    monthly_budget_irr: int
    budget_style: str
    cooking_skill: str
    cooking_time: int
    cooking_freq: int
    favourites: list[str]
    dislikes: list[str]
    allergies: list[str]
    intolerances: list[str]
    job_notes: str


# 30 Realistic, 100% Omnivore Iranian Profiles
PROFILES: list[ProfileDef] = [
    ProfileDef(
        index=1,
        name="آرمین رضایی",
        sex="male",
        age=22,
        height_cm=183,
        weight_kg=76.0,
        goal="build_muscle",
        activity="moderate",
        trains=True,
        ex_type="resistance",
        days_per_week=4,
        minutes_per_session=70,
        intensity="moderate",
        meals=3,
        snacks=2,
        monthly_budget_irr=55_000_000,
        budget_style="flexible",
        cooking_skill="basic",
        cooking_time=45,
        cooking_freq=4,
        favourites=["سینه مرغ", "تخم‌مرغ", "برنج"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="دانشجوی مهندسی، تمرین با وزنه ۴ روز در هفته با هدف هایپرتروفی و افزایش حجم عضلانی.",
    ),
    ProfileDef(
        index=2,
        name="سارا حسینی",
        sex="female",
        age=29,
        height_cm=164,
        weight_kg=69.5,
        goal="fat_loss",
        activity="light",
        trains=True,
        ex_type="mixed",
        days_per_week=3,
        minutes_per_session=45,
        intensity="moderate",
        meals=3,
        snacks=1,
        monthly_budget_irr=38_000_000,
        budget_style="strict",
        cooking_skill="basic",
        cooking_time=30,
        cooking_freq=5,
        favourites=["ماست", "سیب"],
        dislikes=["کرفس", "بادمجان"],
        allergies=[],
        intolerances=[],
        job_notes="کارمند دفتری، تحرک روزمره کم، ۳ روز پیاده‌روی سریع و فیتنس خانگی برای چربی‌سوزی.",
    ),
    ProfileDef(
        index=3,
        name="مهدی محمدی",
        sex="male",
        age=37,
        height_cm=176,
        weight_kg=89.0,
        goal="lose_weight",
        activity="sedentary",
        trains=False,
        ex_type=None,
        days_per_week=None,
        minutes_per_session=None,
        intensity=None,
        meals=2,
        snacks=1,
        monthly_budget_irr=45_000_000,
        budget_style="flexible",
        cooking_skill="basic",
        cooking_time=30,
        cooking_freq=3,
        favourites=["گوشت گوسفندی", "برنج"],
        dislikes=["کدو سبز"],
        allergies=[],
        intolerances=[],
        job_notes="مدیر فروش، ساعات طولانی پشت میز، قصد کنترل وزن بدون تمرین رسمی در آغاز کار.",
    ),
    ProfileDef(
        index=4,
        name="نگین باقری",
        sex="female",
        age=25,
        height_cm=169,
        weight_kg=57.0,
        goal="maintain_weight",
        activity="very_active",
        trains=True,
        ex_type="endurance",
        days_per_week=5,
        minutes_per_session=60,
        intensity="vigorous",
        meals=4,
        snacks=1,
        monthly_budget_irr=65_000_000,
        budget_style="flexible",
        cooking_skill="confident",
        cooking_time=60,
        cooking_freq=5,
        favourites=["جو دوسر", "موز", "ماست"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="مربی آمادگی جسمانی، فعالیت بدنی بالا، نیازمند رژیم با کربوهیدرات کافی جهت بازیابی انرژی.",
    ),
    ProfileDef(
        index=5,
        name="کامران شریفی",
        sex="male",
        age=44,
        height_cm=172,
        weight_kg=81.0,
        goal="improve_fitness",
        activity="moderate",
        trains=True,
        ex_type="mixed",
        days_per_week=3,
        minutes_per_session=50,
        intensity="moderate",
        meals=3,
        snacks=1,
        monthly_budget_irr=50_000_000,
        budget_style="flexible",
        cooking_skill="basic",
        cooking_time=45,
        cooking_freq=4,
        favourites=["عدس", "ماهی"],
        dislikes=["پیاز"],
        allergies=[],
        intolerances=[],
        job_notes="کارشناس مالی، حفظ سلامت قلبی‌عروقی و تناسب عمومی با تمرین هوازی و استقامتی.",
    ),
    ProfileDef(
        index=6,
        name="زهرا اسدی",
        sex="female",
        age=39,
        height_cm=157,
        weight_kg=62.0,
        goal="fat_loss",
        activity="light",
        trains=False,
        ex_type=None,
        days_per_week=None,
        minutes_per_session=None,
        intensity=None,
        meals=3,
        snacks=1,
        monthly_budget_irr=20_000_000,
        budget_style="strict",
        cooking_skill="confident",
        cooking_time=60,
        cooking_freq=6,
        favourites=["تخم‌مرغ", "عدس"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="خانه‌دار با بودجه اقتصادی سخت‌گیرانه، به دنبال رژیم چربی‌سوزی با خوراک‌های در دسترس و ارزان ایرانی.",
    ),
    ProfileDef(
        index=7,
        name="پویا عباسی",
        sex="male",
        age=28,
        height_cm=189,
        weight_kg=94.5,
        goal="gain_weight",
        activity="very_active",
        trains=True,
        ex_type="resistance",
        days_per_week=5,
        minutes_per_session=80,
        intensity="vigorous",
        meals=4,
        snacks=2,
        monthly_budget_irr=95_000_000,
        budget_style="flexible",
        cooking_skill="basic",
        cooking_time=45,
        cooking_freq=5,
        favourites=["سینه مرغ", "گوشت گوسفندی", "برنج", "کره بادام‌زمینی"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="ورزشکار بدنسازی قدرتی، قد بلند و متابولیسم بالا، نیازمند کالری و پروتئین بالا برای وزن‌گیری عضلانی.",
    ),
    ProfileDef(
        index=8,
        name="مریم نوری",
        sex="female",
        age=51,
        height_cm=161,
        weight_kg=75.0,
        goal="lose_weight",
        activity="sedentary",
        trains=True,
        ex_type="endurance",
        days_per_week=2,
        minutes_per_session=35,
        intensity="light",
        meals=2,
        snacks=1,
        monthly_budget_irr=32_000_000,
        budget_style="strict",
        cooking_skill="confident",
        cooking_time=45,
        cooking_freq=4,
        favourites=["مرغ", "خیار"],
        dislikes=["قارچ"],
        allergies=[],
        intolerances=["شیر"],
        job_notes="معلم دبیرستان، حساس به لاکتوز شیر، هدف کاهش وزن و کاهش بار مفاصل با پیاده‌روی سبک.",
    ),
    ProfileDef(
        index=9,
        name="سینا کاظمی",
        sex="male",
        age=31,
        height_cm=179,
        weight_kg=78.5,
        goal="body_recomposition",
        activity="moderate",
        trains=True,
        ex_type="resistance",
        days_per_week=4,
        minutes_per_session=60,
        intensity="moderate",
        meals=3,
        snacks=1,
        monthly_budget_irr=58_000_000,
        budget_style="flexible",
        cooking_skill="basic",
        cooking_time=30,
        cooking_freq=4,
        favourites=["سینه مرغ", "تخم‌مرغ", "سیب‌زمینی"],
        dislikes=["ماهی"],
        allergies=[],
        intolerances=[],
        job_notes="کارشناس دیجیتال مارکتینگ، ریکامپ بدنی همزمان کاهش چربی شکمی و حفظ عضلات اسکلتی.",
    ),
    ProfileDef(
        index=10,
        name="نیلوفر قاسمی",
        sex="female",
        age=21,
        height_cm=154,
        weight_kg=47.5,
        goal="build_muscle",
        activity="light",
        trains=True,
        ex_type="resistance",
        days_per_week=3,
        minutes_per_session=50,
        intensity="moderate",
        meals=3,
        snacks=2,
        monthly_budget_irr=36_000_000,
        budget_style="flexible",
        cooking_skill="basic",
        cooking_time=30,
        cooking_freq=4,
        favourites=["موز", "تخم‌مرغ", "گردو"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="دانشجوی کم‌وزن، افزایش وزن تمیز همراه با تمرین مقاومتی ۳ روز در هفته.",
    ),
    ProfileDef(
        index=11,
        name="جواد کریمی",
        sex="male",
        age=41,
        height_cm=175,
        weight_kg=96.0,
        goal="lose_weight",
        activity="sedentary",
        trains=False,
        ex_type=None,
        days_per_week=None,
        minutes_per_session=None,
        intensity=None,
        meals=2,
        snacks=1,
        monthly_budget_irr=18_000_000,
        budget_style="strict",
        cooking_skill="basic",
        cooking_time=30,
        cooking_freq=3,
        favourites=["نان سنگک", "عدس"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="راننده بین‌شهری، بی‌تحرک، بودجه بسیار محدود (تست استرس بودجه پایین موتور تغذیه).",
    ),
    ProfileDef(
        index=12,
        name="شیدا مرادی",
        sex="female",
        age=33,
        height_cm=167,
        weight_kg=61.5,
        goal="maintain_weight",
        activity="light",
        trains=True,
        ex_type="other",
        days_per_week=2,
        minutes_per_session=45,
        intensity="light",
        meals=3,
        snacks=1,
        monthly_budget_irr=46_000_000,
        budget_style="flexible",
        cooking_skill="basic",
        cooking_time=45,
        cooking_freq=3,
        favourites=["ماست", "گردو"],
        dislikes=["ماهی", "گل کلم"],
        allergies=[],
        intolerances=[],
        job_notes="طراح گرافیک، تمرین یوگا ۲ بار در هفته، تثبیت وزن و سلامت با حذف ماهی به خاطر بیزاری چشایی.",
    ),
    ProfileDef(
        index=13,
        name="غلامرضا حیدری",
        sex="male",
        age=56,
        height_cm=168,
        weight_kg=73.0,
        goal="improve_fitness",
        activity="light",
        trains=True,
        ex_type="endurance",
        days_per_week=4,
        minutes_per_session=40,
        intensity="light",
        meals=3,
        snacks=1,
        monthly_budget_irr=32_000_000,
        budget_style="strict",
        cooking_skill="confident",
        cooking_time=45,
        cooking_freq=5,
        favourites=["عدس", "مرغ"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="بازنشسته آموزش و پرورش، پیاده‌روی روزانه صبحگاهی، بهبود استقامت و سلامت قند و چربی خون.",
    ),
    ProfileDef(
        index=14,
        name="الهام رادمنش",
        sex="female",
        age=27,
        height_cm=165,
        weight_kg=55.5,
        goal="build_muscle",
        activity="sedentary",
        trains=True,
        ex_type="resistance",
        days_per_week=3,
        minutes_per_session=60,
        intensity="moderate",
        meals=3,
        snacks=2,
        monthly_budget_irr=52_000_000,
        budget_style="flexible",
        cooking_skill="basic",
        cooking_time=30,
        cooking_freq=4,
        favourites=["سینه مرغ", "تخم‌مرغ", "موز"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="برنامه‌نویس فرانت‌اند، نشستن طولانی پشت سیستم، شروع بدنسازی جهت فرم‌دهی و عضله‌سازی بالاتنه.",
    ),
    ProfileDef(
        index=15,
        name="فرشاد صادقی",
        sex="male",
        age=26,
        height_cm=182,
        weight_kg=84.0,
        goal="fat_loss",
        activity="moderate",
        trains=True,
        ex_type="mixed",
        days_per_week=4,
        minutes_per_session=60,
        intensity="moderate",
        meals=3,
        snacks=1,
        monthly_budget_irr=60_000_000,
        budget_style="flexible",
        cooking_skill="basic",
        cooking_time=30,
        cooking_freq=4,
        favourites=["سینه مرغ", "برنج", "گوجه‌فرنگی"],
        dislikes=["کدو سبز"],
        allergies=[],
        intolerances=[],
        job_notes="حسابدار شرکت، ۴ روز تمرین ترکیب وزنه و تمرین متناوب با هدف کاهش چربی شکم و پهلو.",
    ),
    ProfileDef(
        index=16,
        name="دکتر مونا کیانی",
        sex="female",
        age=42,
        height_cm=160,
        weight_kg=65.0,
        goal="improve_fitness",
        activity="moderate",
        trains=True,
        ex_type="endurance",
        days_per_week=3,
        minutes_per_session=45,
        intensity="moderate",
        meals=3,
        snacks=1,
        monthly_budget_irr=55_000_000,
        budget_style="flexible",
        cooking_skill="basic",
        cooking_time=30,
        cooking_freq=3,
        favourites=["تخم‌مرغ", "ماست"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="پزشک عمومی، شیفت‌های بیمارستانی، حفظ سطح انرژی و استقامت بدنی با شنا و پیاده‌روی.",
    ),
    ProfileDef(
        index=17,
        name="امید یزدانی",
        sex="male",
        age=34,
        height_cm=173,
        weight_kg=71.0,
        goal="maintain_weight",
        activity="light",
        trains=False,
        ex_type=None,
        days_per_week=None,
        minutes_per_session=None,
        intensity=None,
        meals=3,
        snacks=1,
        monthly_budget_irr=36_000_000,
        budget_style="strict",
        cooking_skill="basic",
        cooking_time=30,
        cooking_freq=4,
        favourites=["مرغ", "برنج"],
        dislikes=["بادمجان"],
        allergies=[],
        intolerances=[],
        job_notes="کارمند اداری، وزن در محدوده نرمال، خواستار ثبات وزن و مصرف متوازن مواد مغذی.",
    ),
    ProfileDef(
        index=18,
        name="سمیرا تقوی",
        sex="female",
        age=32,
        height_cm=166,
        weight_kg=81.0,
        goal="lose_weight",
        activity="sedentary",
        trains=True,
        ex_type="mixed",
        days_per_week=2,
        minutes_per_session=40,
        intensity="light",
        meals=2,
        snacks=1,
        monthly_budget_irr=28_000_000,
        budget_style="strict",
        cooking_skill="basic",
        cooking_time=30,
        cooking_freq=3,
        favourites=["عدس", "تخم‌مرغ"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="کارشناس امور مشتریان، ۲ وعده در روز به دلیل مشغله کاری، تمرکز بر کاهش پایدار وزن.",
    ),
    ProfileDef(
        index=19,
        name="داوود میرزایی",
        sex="male",
        age=49,
        height_cm=177,
        weight_kg=86.0,
        goal="fat_loss",
        activity="moderate",
        trains=True,
        ex_type="resistance",
        days_per_week=3,
        minutes_per_session=50,
        intensity="moderate",
        meals=3,
        snacks=1,
        monthly_budget_irr=50_000_000,
        budget_style="flexible",
        cooking_skill="confident",
        cooking_time=45,
        cooking_freq=4,
        favourites=["گوشت گوسفندی", "ماست"],
        dislikes=["فلفل دلمه‌ای"],
        allergies=[],
        intolerances=[],
        job_notes="کارشناس تأسیسات، ۳ جلسه تمرین فول‌بادی در هفته برای کنترل چربی احشایی و حفظ توده عضلانی.",
    ),
    ProfileDef(
        index=20,
        name="رویا فلاحی",
        sex="female",
        age=23,
        height_cm=171,
        weight_kg=62.5,
        goal="improve_fitness",
        activity="very_active",
        trains=True,
        ex_type="endurance",
        days_per_week=5,
        minutes_per_session=75,
        intensity="vigorous",
        meals=4,
        snacks=2,
        monthly_budget_irr=82_000_000,
        budget_style="flexible",
        cooking_skill="basic",
        cooking_time=30,
        cooking_freq=5,
        favourites=["موز", "سینه مرغ", "جو دوسر"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="ورزشکار رشته دوومیدانی، مصرف کالری روزانه بالا، نیازمند تأمین سریع گلیکوژن و پروتئین باکیفیت.",
    ),
    ProfileDef(
        index=21,
        name="سامان رستمی",
        sex="male",
        age=27,
        height_cm=191,
        weight_kg=106.0,
        goal="strength",
        activity="very_active",
        trains=True,
        ex_type="resistance",
        days_per_week=5,
        minutes_per_session=90,
        intensity="vigorous",
        meals=4,
        snacks=2,
        monthly_budget_irr=115_000_000,
        budget_style="flexible",
        cooking_skill="confident",
        cooking_time=60,
        cooking_freq=5,
        favourites=["سینه مرغ", "گوشت گوسفندی", "تخم‌مرغ", "برنج"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="پاورلیفتر سنگین‌وزن، تمرینات بسیار پرفشار و سنگین قدرتی، بودجه آزاد و دریافت درشت‌مغذی حداکثری.",
    ),
    ProfileDef(
        index=22,
        name="پروانه معتمدی",
        sex="female",
        age=36,
        height_cm=159,
        weight_kg=53.0,
        goal="maintain_weight",
        activity="moderate",
        trains=True,
        ex_type="mixed",
        days_per_week=3,
        minutes_per_session=45,
        intensity="moderate",
        meals=3,
        snacks=1,
        monthly_budget_irr=42_000_000,
        budget_style="flexible",
        cooking_skill="confident",
        cooking_time=45,
        cooking_freq=5,
        favourites=["ماهی", "زیتون"],
        dislikes=["کرفس"],
        allergies=[],
        intolerances=[],
        job_notes="مترجم کتاب، ترکیب پیاده‌روی و پیلاتس، تثبیت وزن و حفظ سرزندگی روزانه با مواد مغذی ارگانیک.",
    ),
    ProfileDef(
        index=23,
        name="شاهین افشار",
        sex="male",
        age=39,
        height_cm=181,
        weight_kg=77.0,
        goal="body_recomposition",
        activity="moderate",
        trains=True,
        ex_type="resistance",
        days_per_week=4,
        minutes_per_session=60,
        intensity="moderate",
        meals=3,
        snacks=1,
        monthly_budget_irr=62_000_000,
        budget_style="flexible",
        cooking_skill="basic",
        cooking_time=30,
        cooking_freq=4,
        favourites=["سینه مرغ", "عدس", "سیب‌زمینی"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="مدیر محصول استارتاپ، به دنبال تعادل فرم بدن و افزایش تراکم عضلانی همراه با برنامه کاری فشرده.",
    ),
    ProfileDef(
        index=24,
        name="فاطمه نیکنام",
        sex="female",
        age=48,
        height_cm=155,
        weight_kg=68.0,
        goal="fat_loss",
        activity="sedentary",
        trains=False,
        ex_type=None,
        days_per_week=None,
        minutes_per_session=None,
        intensity=None,
        meals=3,
        snacks=1,
        monthly_budget_irr=30_000_000,
        budget_style="strict",
        cooking_skill="confident",
        cooking_time=60,
        cooking_freq=6,
        favourites=["مرغ", "گوجه‌فرنگی"],
        dislikes=["بادمجان"],
        allergies=["بادام‌زمینی"],
        intolerances=[],
        job_notes="حسابدار بازنشسته، آلرژی قطعی به بادام‌زمینی، تحرک پایین و نیازمند کسر کالری ملایم و بی‌خطر.",
    ),
    ProfileDef(
        index=25,
        name="بهرام انصاری",
        sex="male",
        age=30,
        height_cm=178,
        weight_kg=82.0,
        goal="build_muscle",
        activity="moderate",
        trains=True,
        ex_type="resistance",
        days_per_week=4,
        minutes_per_session=65,
        intensity="moderate",
        meals=3,
        snacks=1,
        monthly_budget_irr=52_000_000,
        budget_style="flexible",
        cooking_skill="basic",
        cooking_time=35,
        cooking_freq=4,
        favourites=["سینه مرغ", "تخم‌مرغ"],
        dislikes=["قارچ"],
        allergies=[],
        intolerances=[],
        job_notes="مهندس زیرساخت شبکه، تمایل به عضلانی‌تر شدن بالاتنه و بازوها، تمرین ۴ روز در هفته در باشگاه محله.",
    ),
    ProfileDef(
        index=26,
        name="حنانه کمالی",
        sex="female",
        age=20,
        height_cm=162,
        weight_kg=51.5,
        goal="maintain_weight",
        activity="sedentary",
        trains=False,
        ex_type=None,
        days_per_week=None,
        minutes_per_session=None,
        intensity=None,
        meals=3,
        snacks=1,
        monthly_budget_irr=26_000_000,
        budget_style="strict",
        cooking_skill="none",
        cooking_time=20,
        cooking_freq=2,
        favourites=["تخم‌مرغ", "شیر"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="دانشجوی حقوق، عدم مهارت در آشپزی، نیازمند رژیم غذایی ساده و سریع جهت تثبیت وزن و جلوگیری از خستگی ذهنی.",
    ),
    ProfileDef(
        index=27,
        name="حاج علی توکلی",
        sex="male",
        age=63,
        height_cm=169,
        weight_kg=75.5,
        goal="maintain_weight",
        activity="light",
        trains=False,
        ex_type=None,
        days_per_week=None,
        minutes_per_session=None,
        intensity=None,
        meals=3,
        snacks=0,
        monthly_budget_irr=35_000_000,
        budget_style="strict",
        cooking_skill="confident",
        cooking_time=60,
        cooking_freq=6,
        favourites=["نان سنگک", "عدس", "مرغ"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="سالمند بازنشسته، ترجیح غذای سنتی ایرانی ۳ وعده اصلی بدون میان‌وعده، هدف حفظ سلامت و توان بدنی.",
    ),
    ProfileDef(
        index=28,
        name="مژگان سعادت",
        sex="female",
        age=35,
        height_cm=168,
        weight_kg=93.0,
        goal="lose_weight",
        activity="sedentary",
        trains=True,
        ex_type="endurance",
        days_per_week=2,
        minutes_per_session=30,
        intensity="light",
        meals=2,
        snacks=1,
        monthly_budget_irr=34_000_000,
        budget_style="strict",
        cooking_skill="basic",
        cooking_time=30,
        cooking_freq=3,
        favourites=["تخم‌مرغ", "سیب"],
        dislikes=["کدو سبز", "پیاز"],
        allergies=[],
        intolerances=[],
        job_notes="نویسنده دورکار، اضافه وزن کلاس ۱، برنامه ۲ وعده در روز برای کنترل اشتها و پیاده‌روی سبک هفتگی.",
    ),
    ProfileDef(
        index=29,
        name="کیوان پارسا",
        sex="male",
        age=32,
        height_cm=177,
        weight_kg=73.5,
        goal="body_recomposition",
        activity="very_active",
        trains=True,
        ex_type="mixed",
        days_per_week=3,
        minutes_per_session=60,
        intensity="moderate",
        meals=3,
        snacks=2,
        monthly_budget_irr=68_000_000,
        budget_style="flexible",
        cooking_skill="basic",
        cooking_time=40,
        cooking_freq=4,
        favourites=["سینه مرغ", "موز", "برنج"],
        dislikes=[],
        allergies=[],
        intolerances=[],
        job_notes="مهندس ناظر پروژه‌های عمرانی، فعالیت فیزیکی روزانه در کارگاه همراه با تمرین باشگاهی عصرها.",
    ),
    ProfileDef(
        index=30,
        name="پرستو طاهری",
        sex="female",
        age=28,
        height_cm=163,
        weight_kg=56.0,
        goal="maintain_weight",
        activity="moderate",
        trains=True,
        ex_type="mixed",
        days_per_week=2,
        minutes_per_session=45,
        intensity="moderate",
        meals=3,
        snacks=1,
        monthly_budget_irr=45_000_000,
        budget_style="flexible",
        cooking_skill="basic",
        cooking_time=30,
        cooking_freq=4,
        favourites=["ماست", "سینه مرغ", "گردو"],
        dislikes=["کرفس"],
        allergies=[],
        intolerances=[],
        job_notes="پرستار بخش اورژانس با کار شیفتی، هدف تأمین انرژی یکنواخت و تثبیت وزن در شیفت‌های متغیر کاری.",
    ),
]


@dataclass
class EvalFoodResult:
    name_fa: str
    grams: float
    cost_irr: int


@dataclass
class EvalMealResult:
    role: str
    name_fa: str
    cost_irr: int
    foods: list[EvalFoodResult]


@dataclass
class EvalDayResult:
    day_index: int
    cost_irr: int
    calories: float
    protein: float
    carbs: float
    fat: float
    meals: list[EvalMealResult]


@dataclass
class ProfileEvalResult:
    profile: ProfileDef
    outcome: str
    is_success: bool
    reason_codes: list[str]
    warning_codes: list[str]
    diagnostics: dict[str, Any]
    target_calories: float | None
    target_protein: float | None
    target_carbs: float | None
    target_fat: float | None
    weekly_cost_irr: int | None
    weekly_budget_irr: int
    program_code: str | None
    program_name_fa: str | None
    days: list[EvalDayResult]
    error_summary: str | None


def run_evaluation(profiles: list[ProfileDef]) -> list[ProfileEvalResult]:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    results: list[ProfileEvalResult] = []

    print(f"Executing Fitsho Nutrition Engine for {len(profiles)} Omnivore profiles...")

    with Session(engine) as db:
        for spec in profiles:
            uid = uuid5(NAMESPACE_URL, f"fitsho-omnivore-eval:20260905:{spec.index}")

            # Clean previous run for this test user safely
            db.execute(delete(NutritionWeeklyPlan).where(NutritionWeeklyPlan.user_id == uid))
            db.execute(delete(NutritionPlanGeneration).where(NutritionPlanGeneration.user_id == uid))
            db.execute(delete(User).where(User.id == uid))
            db.commit()

            # 1. User & Profile
            u = User(id=uid, email=f"omnivore_eval_{spec.index}@fitsho.test", password_hash="fake")
            db.add(u)
            db.flush()

            birth_date = date(2026 - spec.age, 6, 15)
            up = UserProfile(
                user_id=uid,
                product_mode=ProductMode.NUTRITION,
                display_name=spec.name,
                birth_date=birth_date,
                sex=Sex(spec.sex),
                height_cm=spec.height_cm,
                fitness_goal=FitnessGoal(spec.goal),
            )
            db.add(up)
            db.flush()

            bm = BodyMeasurement(user_id=uid, weight_kg=Decimal(str(spec.weight_kg)))
            db.add(bm)

            # 2. Medical & Safety
            med = NutritionMedicalProfile(
                user_id=uid,
                dangerous_food_reaction_history=bool(spec.allergies),
                pregnant=False,
                breastfeeding=False,
                eating_disorder_diagnosed=False,
                eating_disorder_active_symptoms=False,
                emergency_or_danger_symptoms=False,
                complex_medication_food_interaction=False,
                physician_dietary_restrictions=None,
                other_relevant_condition=None,
            )
            db.add(med)
            db.flush()

            safety = NutritionSafetyDecision(
                user_id=uid,
                medical_condition_policy_version="medical-condition-v1",
                revision=1,
                outcome=SafetyOutcome.STANDARD_AUTOMATIC,
                reasons=[NutritionSafetyReason(code="no_review_condition_declared")],
            )
            db.add(safety)

            # 3. Nutrition Profile (100% Omnivore)
            meal_bucket = (
                MainMealCountBucket.TWO
                if spec.meals == 2
                else (
                    MainMealCountBucket.THREE
                    if spec.meals == 3
                    else MainMealCountBucket.FOUR_OR_MORE
                )
            )
            snack_bucket = (
                SnackCountBucket.ZERO
                if spec.snacks == 0
                else (
                    SnackCountBucket.ONE
                    if spec.snacks == 1
                    else (
                        SnackCountBucket.TWO
                        if spec.snacks == 2
                        else SnackCountBucket.THREE_OR_MORE
                    )
                )
            )

            np = NutritionProfile(
                user_id=uid,
                onboarding_status=NutritionOnboardingStatus.COMPLETED,
                dietary_pattern=DietaryPattern.OMNIVORE,
                daily_activity_level=DailyActivityLevel(spec.activity),
                individual_monthly_food_budget_irr=spec.monthly_budget_irr,
                budget_style=BudgetStyle(spec.budget_style),
                meals_per_day=spec.meals,
                snacks_per_day=spec.snacks,
                main_meal_count_bucket=meal_bucket,
                snack_count_bucket=snack_bucket,
                effective_main_meal_slots=spec.meals,
                effective_snack_slots=spec.snacks,
                preferred_plan_start_day=Weekday.SATURDAY,
                plan_style=NutritionPlanStyle.BALANCED,
                cooking_skill=CookingSkill(spec.cooking_skill),
                maximum_cooking_time_minutes=spec.cooking_time,
                cooking_frequency_per_week=spec.cooking_freq,
                meal_preparation_preference=MealPreparationPreference.MIXED,
                refrigerator_access=True,
                freezer_access=True,
                supplied_meals_per_week=0,
                preferred_variety=PreferredVariety.MEDIUM,
                maximum_meal_repetition_per_week=2,
                accepts_leftovers=True,
                accepts_batch_cooking=True,
                daily_check_in_enabled=False,
            )
            db.add(np)
            db.flush()

            # 4. Structured Exercise
            se = NutritionStructuredExercise(
                user_id=uid,
                trains=spec.trains,
                exercise_type=StructuredExerciseType(spec.ex_type) if spec.trains and spec.ex_type else None,
                days_per_week=spec.days_per_week if spec.trains else None,
                minutes_per_session=spec.minutes_per_session if spec.trains else None,
                intensity=TrainingIntensity(spec.intensity) if spec.trains and spec.intensity else None,
                source=StructuredExerciseSource.USER_REPORTED,
            )
            db.add(se)

            # 5. Food Constraints (Dislikes, Allergies, Intolerances, Favourites)
            for item in spec.allergies:
                db.add(
                    NutritionFoodItem(
                        user_id=uid,
                        kind=FoodItemKind.ALLERGY,
                        name=item,
                        normalized_name=item,
                        details="حساسیت غذایی اعلام‌شده توسط کاربر",
                    )
                )
            for item in spec.intolerances:
                db.add(
                    NutritionFoodItem(
                        user_id=uid,
                        kind=FoodItemKind.INTOLERANCE,
                        name=item,
                        normalized_name=item,
                        details="عدم تحمل گوارشی",
                    )
                )
            for item in spec.dislikes:
                db.add(
                    NutritionFoodItem(
                        user_id=uid,
                        kind=FoodItemKind.DISLIKED,
                        name=item,
                        normalized_name=item,
                    )
                )
            for item in spec.favourites:
                db.add(
                    NutritionFoodItem(
                        user_id=uid,
                        kind=FoodItemKind.FAVOURITE,
                        name=item,
                        normalized_name=item,
                    )
                )

            db.commit()

            # Execute Engine
            try:
                gen_resp = generate_weekly_plan(db, uid)
                is_success = gen_resp.outcome == "success" and gen_resp.plan is not None

                t_cals = None
                t_prot = None
                t_carbs = None
                t_fat = None
                days_list: list[EvalDayResult] = []
                prog_code = None

                if gen_resp.plan:
                    if "calories" in gen_resp.plan.nutrients:
                        t_cals = gen_resp.plan.nutrients["calories"].planned
                    if "protein" in gen_resp.plan.nutrients:
                        t_prot = gen_resp.plan.nutrients["protein"].planned
                    if "carbohydrates" in gen_resp.plan.nutrients:
                        t_carbs = gen_resp.plan.nutrients["carbohydrates"].planned
                    if "fat" in gen_resp.plan.nutrients:
                        t_fat = gen_resp.plan.nutrients["fat"].planned

                    # Snapshot / Template metadata
                    snapshot = gen_resp.plan.input_snapshot or {}
                    prog_code = snapshot.get("selected_program_code") or snapshot.get("program_code")

                    for day in gen_resp.plan.days:
                        meals_list: list[EvalMealResult] = []
                        for m in day.meals:
                            foods_list = [
                                EvalFoodResult(name_fa=f.name_fa, grams=f.grams, cost_irr=f.cost_irr)
                                for f in m.foods
                            ]
                            meals_list.append(
                                EvalMealResult(
                                    role=m.slot_role,
                                    name_fa=m.name_fa or m.slot_role,
                                    cost_irr=m.cost_irr,
                                    foods=foods_list,
                                )
                            )
                        cals = day.nutrient_totals.get("calories", 0.0)
                        prot = day.nutrient_totals.get("protein", 0.0)
                        carbs = day.nutrient_totals.get("carbohydrates", 0.0)
                        fat = day.nutrient_totals.get("fat", 0.0)
                        days_list.append(
                            EvalDayResult(
                                day_index=day.day_index,
                                cost_irr=day.cost_irr,
                                calories=cals,
                                protein=prot,
                                carbs=carbs,
                                fat=fat,
                                meals=meals_list,
                            )
                        )

                err_msg = None
                if not is_success:
                    reasons_desc = [FA_REASON.get(rc, rc) for rc in gen_resp.reason_codes]
                    err_msg = " ؛ ".join(reasons_desc) if reasons_desc else "خطای نامشخص در ساخت برنامه"

                weekly_budget = spec.monthly_budget_irr * 12 // 52

                res = ProfileEvalResult(
                    profile=spec,
                    outcome=gen_resp.outcome,
                    is_success=is_success,
                    reason_codes=gen_resp.reason_codes,
                    warning_codes=gen_resp.warning_codes,
                    diagnostics={},
                    target_calories=t_cals,
                    target_protein=t_prot,
                    target_carbs=t_carbs,
                    target_fat=t_fat,
                    weekly_cost_irr=gen_resp.plan.weekly_cost_irr if gen_resp.plan else None,
                    weekly_budget_irr=weekly_budget,
                    program_code=prog_code,
                    program_name_fa=None,
                    days=days_list,
                    error_summary=err_msg,
                )
                results.append(res)
                print(
                    f"  [{spec.index:02d}/30] {spec.name} ({spec.sex}, {spec.age}y): "
                    f"{gen_resp.outcome.upper()} | Cost: {gen_resp.plan.weekly_cost_irr if gen_resp.plan else 'N/A':,} IRR"
                )

            except Exception as ex:
                import traceback

                tb = traceback.format_exc()
                print(f"  [{spec.index:02d}/30] {spec.name} ERROR: {ex}")
                results.append(
                    ProfileEvalResult(
                        profile=spec,
                        outcome="failed",
                        is_success=False,
                        reason_codes=["UNHANDLED_EXCEPTION"],
                        warning_codes=[],
                        diagnostics={"exception": str(ex), "traceback": tb},
                        target_calories=None,
                        target_protein=None,
                        target_carbs=None,
                        target_fat=None,
                        weekly_cost_irr=None,
                        weekly_budget_irr=spec.monthly_budget_irr * 12 // 52,
                        program_code=None,
                        program_name_fa=None,
                        days=[],
                        error_summary=f"استثنای سیستمی: {ex}",
                    )
                )

    return results


def render_pdf_report(results: list[ProfileEvalResult], output_pdf_path: str) -> None:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_count = len(results)
    success_count = sum(1 for r in results if r.is_success)
    failed_count = total_count - success_count

    html_parts = [
        """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>گزارش ارزیابی ۳۰ پروفایل همه‌چیزخوار موتور تغذیه فیتشو</title>
<style>
@page {
    size: A4 portrait;
    margin: 14mm 15mm 15mm 15mm;
    @bottom-center {
        content: "صفحه " counter(page) " از " counter(pages);
        font-family: 'Vazirmatn', Tahoma, sans-serif;
        font-size: 8pt;
        color: #64748b;
    }
    @top-right {
        content: "Fitsho Nutrition Engine — 30 Omnivore Profiles Evaluation";
        font-family: 'Vazirmatn', Tahoma, sans-serif;
        font-size: 7.5pt;
        color: #94a3b8;
    }
}
* {
    box-sizing: border-box;
}
body {
    font-family: 'Vazirmatn', Tahoma, sans-serif;
    direction: rtl;
    text-align: right;
    color: #1e293b;
    background-color: #ffffff;
    font-size: 9pt;
    line-height: 1.45;
    margin: 0;
    padding: 0;
}
.header-hero {
    border-bottom: 2px solid #2563eb;
    padding-bottom: 12px;
    margin-bottom: 18px;
}
.header-title {
    font-size: 18pt;
    font-weight: 800;
    color: #0f172a;
    margin: 0 0 6px 0;
}
.header-subtitle {
    font-size: 9.5pt;
    color: #475569;
    margin: 0 0 8px 0;
}
.meta-chips {
    display: flex;
    gap: 12px;
    font-size: 8.5pt;
    color: #334155;
}
.meta-chip {
    background: #f1f5f9;
    padding: 3px 8px;
    border-radius: 4px;
    font-weight: 600;
}
.summary-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 12px;
    margin-bottom: 24px;
    font-size: 8pt;
}
.summary-table th {
    background-color: #0f172a;
    color: #ffffff;
    padding: 6px 6px;
    font-weight: 700;
    text-align: center;
    border: 1px solid #334155;
}
.summary-table td {
    padding: 5px 6px;
    border: 1px solid #cbd5e1;
    text-align: center;
}
.summary-table tr:nth-child(even) {
    background-color: #f8fafc;
}
.badge-success {
    background-color: #dcfce7;
    color: #166534;
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 7.5pt;
    display: inline-block;
}
.badge-fail {
    background-color: #fee2e2;
    color: #991b1b;
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 7.5pt;
    display: inline-block;
}
.page-break {
    page-break-before: always;
}
.profile-card {
    page-break-inside: avoid;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 16px;
    background: #ffffff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.profile-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #f1f5f9;
    padding-bottom: 8px;
    margin-bottom: 10px;
}
.profile-name {
    font-size: 11pt;
    font-weight: 800;
    color: #1e3a8a;
    margin: 0;
}
.profile-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-bottom: 10px;
    background: #f8fafc;
    padding: 8px 10px;
    border-radius: 6px;
    font-size: 8pt;
}
.grid-item {
    margin: 0;
}
.grid-label {
    color: #64748b;
    font-size: 7.5pt;
    display: block;
}
.grid-val {
    color: #0f172a;
    font-weight: 700;
}
.plan-section {
    border-top: 1px dashed #cbd5e1;
    padding-top: 8px;
    margin-top: 8px;
}
.plan-title {
    font-size: 9pt;
    font-weight: 800;
    color: #047857;
    margin: 0 0 6px 0;
}
.plan-metrics {
    display: flex;
    gap: 12px;
    margin-bottom: 8px;
    font-size: 8pt;
}
.metric-box {
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    padding: 4px 8px;
    border-radius: 5px;
    flex: 1;
    text-align: center;
}
.metric-box-title {
    color: #065f46;
    font-size: 7pt;
    display: block;
}
.metric-box-val {
    color: #047857;
    font-weight: 800;
    font-size: 9pt;
}
.day-sample {
    background: #fafafa;
    border: 1px solid #f1f5f9;
    border-radius: 6px;
    padding: 6px 8px;
    margin-top: 6px;
    font-size: 7.5pt;
}
.meal-row {
    margin-bottom: 4px;
    padding-bottom: 4px;
    border-bottom: 1px dotted #e2e8f0;
}
.meal-row:last-child {
    border-bottom: none;
    margin-bottom: 0;
    padding-bottom: 0;
}
.meal-title {
    font-weight: 700;
    color: #1e293b;
}
.food-items {
    color: #475569;
    margin-right: 6px;
}
.error-box {
    background: #fff1f2;
    border: 1px solid #fecdd3;
    border-radius: 6px;
    padding: 8px 10px;
    margin-top: 8px;
    color: #9f1239;
    font-size: 8pt;
}
.error-title {
    font-weight: 800;
    margin-bottom: 4px;
}
</style>
</head>
<body>

<div class="header-hero">
    <h1 class="header-title">گزارش جامع ارزیابی ۳۰ پروفایل موتور تغذیه فیتشو (Omnivore)</h1>
    <p class="header-subtitle">
        ارزیابی ۱۰۰٪ واقعی و مستقیم موتور برنامه‌ریز تغذیه (بدون داده‌های ساختگی) برای ۳۰ ورزشکار و کاربر همه‌چیزخوار
    </p>
    <div class="meta-chips">
        <span class="meta-chip">تاریخ ارزیابی: """
        + now_str
        + """</span>
        <span class="meta-chip">تعداد کل پروفایل‌ها: """
        + str(total_count)
        + """</span>
        <span class="meta-chip" style="background:#dcfce7; color:#15803d;">برنامه‌های موفق: """
        + str(success_count)
        + """</span>
        <span class="meta-chip" style="background:#fee2e2; color:#b91c1c;">موارد رد/محدودیت: """
        + str(failed_count)
        + """</span>
        <span class="meta-chip">الگوی تغذیه: ۱۰۰٪ همه‌چیزخوار (Omnivore)</span>
    </div>
</div>

<h3 style="font-size:10.5pt; font-weight:800; margin: 12px 0 6px 0; color:#1e293b;">جدول خلاصه وضعیت ۳۰ پروفایل</h3>
<table class="summary-table">
    <thead>
        <tr>
            <th>#</th>
            <th>نام کاربر</th>
            <th>جنسیت</th>
            <th>سن</th>
            <th>قد / وزن</th>
            <th>هدف</th>
            <th>فعالیت / تمرین</th>
            <th>بودجه ماهانه</th>
            <th>وعده + میان‌وعده</th>
            <th>نتیجه موتور</th>
            <th>هزینه هفتگی رژیم</th>
        </tr>
    </thead>
    <tbody>
"""
    ]

    for r in results:
        p = r.profile
        badge = (
            '<span class="badge-success">موفق</span>'
            if r.is_success
            else '<span class="badge-fail">ناممکن / محدود</span>'
        )
        cost_str = f"{r.weekly_cost_irr:,} ریال" if r.weekly_cost_irr else "—"
        train_desc = (
            f"{FA_ACTIVITY.get(p.activity, p.activity)} / {p.days_per_week} روز"
            if p.trains
            else f"{FA_ACTIVITY.get(p.activity, p.activity)} / بدون تمرین"
        )
        html_parts.append(
            f"""        <tr>
            <td><strong>{p.index}</strong></td>
            <td style="text-align:right; font-weight:700;">{p.name}</td>
            <td>{FA_SEX.get(p.sex, p.sex)}</td>
            <td>{p.age}</td>
            <td>{p.height_cm}cm / {p.weight_kg}kg</td>
            <td>{FA_GOAL.get(p.goal, p.goal)}</td>
            <td style="font-size:7pt;">{train_desc}</td>
            <td>{p.monthly_budget_irr // 10_000:,} تومان</td>
            <td>{p.meals} وعده + {p.snacks} میان‌</td>
            <td>{badge}</td>
            <td style="font-weight:700; color:#047857;">{cost_str}</td>
        </tr>
"""
        )

    html_parts.append(
        """    </tbody>
</table>

<div class="page-break"></div>
<h2 style="font-size:14pt; font-weight:800; color:#0f172a; margin-bottom:14px; border-bottom:1px solid #e2e8f0; padding-bottom:6px;">
    جزئیات پروفایل‌ها و رژیم غذایی تولید شده توسط موتور فیتشو
</h2>
"""
    )

    for r in results:
        p = r.profile
        bmi = round(p.weight_kg / ((p.height_cm / 100) ** 2), 1)

        # Build preferences text
        prefs: list[str] = []
        if p.favourites:
            prefs.append(f"علاقه‌مندی‌ها: {', '.join(p.favourites)}")
        if p.dislikes:
            prefs.append(f"بیزاری‌ها: {', '.join(p.dislikes)}")
        if p.allergies:
            prefs.append(f"آلرژی قطعی: {', '.join(p.allergies)}")
        if p.intolerances:
            prefs.append(f"عدم تحمل گوارشی: {', '.join(p.intolerances)}")
        prefs_text = " | ".join(prefs) if prefs else "بدون محدودیت یا ترجیح خاص"

        status_badge = (
            '<span class="badge-success" style="font-size:8.5pt;">✓ تأیید و تولید برنامه غذایی</span>'
            if r.is_success
            else '<span class="badge-fail" style="font-size:8.5pt;">✕ عدم تولید برنامه (محدودیت موتور)</span>'
        )

        plan_html = ""
        if r.is_success and r.days:
            # Show Day 1 and Day 2 sample meals
            cals_str = f"{int(r.target_calories):,} kcal" if r.target_calories else "—"
            prot_str = f"{int(r.target_protein)} g" if r.target_protein else "—"
            carb_str = f"{int(r.target_carbs)} g" if r.target_carbs else "—"
            fat_str = f"{int(r.target_fat)} g" if r.target_fat else "—"
            weekly_cost = f"{r.weekly_cost_irr:,} ریال ({r.weekly_cost_irr // 10_000:,} تومان)" if r.weekly_cost_irr else "—"

            meals_day1_html = []
            d1 = r.days[0]
            for m in d1.meals:
                foods_summary = [f"{f.name_fa} ({int(f.grams)} گرم)" for f in m.foods]
                role_badge = "وعده اصلی" if m.role == "main_meal" else "میان‌وعده"
                meals_day1_html.append(
                    f"""<div class="meal-row">
                        <span class="meal-title">[{role_badge}] {m.name_fa}:</span>
                        <span class="food-items">{', '.join(foods_summary)}</span>
                        <span style="float:left; color:#64748b; font-size:7pt;">{m.cost_irr // 10_000:,} تومان</span>
                    </div>"""
                )

            # Day 2 meals
            meals_day2_html = []
            if len(r.days) > 1:
                d2 = r.days[1]
                for m in d2.meals:
                    foods_summary = [f"{f.name_fa} ({int(f.grams)} گرم)" for f in m.foods]
                    role_badge = "وعده اصلی" if m.role == "main_meal" else "میان‌وعده"
                    meals_day2_html.append(
                        f"""<div class="meal-row">
                            <span class="meal-title">[{role_badge}] {m.name_fa}:</span>
                            <span class="food-items">{', '.join(foods_summary)}</span>
                            <span style="float:left; color:#64748b; font-size:7pt;">{m.cost_irr // 10_000:,} تومان</span>
                        </div>"""
                    )

            plan_html = f"""
            <div class="plan-section">
                <div class="plan-title">برنامه غذایی تأیید شده توسط موتور فیتشو (Weekly Meal Plan):</div>
                <div class="plan-metrics">
                    <div class="metric-box">
                        <span class="metric-box-title">انرژی روزانه</span>
                        <span class="metric-box-val">{cals_str}</span>
                    </div>
                    <div class="metric-box">
                        <span class="metric-box-title">پروتئین هدف</span>
                        <span class="metric-box-val">{prot_str}</span>
                    </div>
                    <div class="metric-box">
                        <span class="metric-box-title">کربوهیدرات</span>
                        <span class="metric-box-val">{carb_str}</span>
                    </div>
                    <div class="metric-box">
                        <span class="metric-box-title">چربی</span>
                        <span class="metric-box-val">{fat_str}</span>
                    </div>
                    <div class="metric-box">
                        <span class="metric-box-title">هزینه هفتگی رژیم</span>
                        <span class="metric-box-val" style="font-size:8pt; color:#1e3a8a;">{weekly_cost}</span>
                    </div>
                </div>

                <div class="day-sample">
                    <div style="font-weight:800; color:#1e293b; margin-bottom:4px;">نمونه وعده‌های روز اول (شنبه) — مجموع کالری روزانه: {int(d1.calories)} kcal | پروتئین: {int(d1.protein)}g:</div>
                    {''.join(meals_day1_html)}
                </div>

                {'<div class="day-sample" style="margin-top:6px;"><div style="font-weight:800; color:#1e293b; margin-bottom:4px;">نمونه وعده‌های روز دوم (یکشنبه) — مجموع کالری روزانه: ' + str(int(d2.calories)) + ' kcal | پروتئین: ' + str(int(d2.protein)) + 'g:</div>' + ''.join(meals_day2_html) + '</div>' if meals_day2_html else ''}
            </div>
            """
        else:
            plan_html = f"""
            <div class="error-box">
                <div class="error-title">علت رد برنامه توسط موتور تغذیه (Engine Error / Safety Diagnostics):</div>
                <div><strong>وضعیت موتور:</strong> {r.outcome}</div>
                <div><strong>کدهای علت (Reason Codes):</strong> {', '.join(r.reason_codes) if r.reason_codes else 'ثبت نشده'}</div>
                <div style="margin-top:4px;"><strong>شرح تشخیصی:</strong> {r.error_summary or 'امکان صدور برنامه با شرایط ورودی کاربر مهیا نشد.'}</div>
            </div>
            """

        html_parts.append(
            f"""
<div class="profile-card">
    <div class="profile-card-header">
        <div>
            <h3 class="profile-name">پروفایل #{p.index}: {p.name} ({FA_SEX.get(p.sex, p.sex)}، {p.age} سال)</h3>
            <div style="font-size:7.5pt; color:#64748b; margin-top:2px;">{p.job_notes}</div>
        </div>
        <div>
            {status_badge}
        </div>
    </div>

    <div class="profile-grid">
        <div class="grid-item">
            <span class="grid-label">قد و وزن:</span>
            <span class="grid-val">{p.height_cm} سانتی‌متر / {p.weight_kg} کیلوگرم</span>
        </div>
        <div class="grid-item">
            <span class="grid-label">شاخص توده بدنی (BMI):</span>
            <span class="grid-val">{bmi} kg/m²</span>
        </div>
        <div class="grid-item">
            <span class="grid-label">هدف تناسب اندام:</span>
            <span class="grid-val">{FA_GOAL.get(p.goal, p.goal)}</span>
        </div>
        <div class="grid-item">
            <span class="grid-label">بودجه ماهانه غذا:</span>
            <span class="grid-val">{p.monthly_budget_irr // 10_000:,} تومان ({FA_BUDGET_STYLE.get(p.budget_style, p.budget_style)})</span>
        </div>
        <div class="grid-item">
            <span class="grid-label">سطح فعالیت روزمره:</span>
            <span class="grid-val">{FA_ACTIVITY.get(p.activity, p.activity)}</span>
        </div>
        <div class="grid-item">
            <span class="grid-label">ورزش و تمرین:</span>
            <span class="grid-val">{'بله (' + FA_EXERCISE.get(p.ex_type or '', p.ex_type or '') + '، ' + str(p.days_per_week) + ' روز/هفته)' if p.trains else 'بدون تمرین رسمی'}</span>
        </div>
        <div class="grid-item">
            <span class="grid-label">ساختار وعده‌ها:</span>
            <span class="grid-val">{p.meals} وعده اصلی + {p.snacks} میان‌وعده</span>
        </div>
        <div class="grid-item">
            <span class="grid-label">الگوی غذایی:</span>
            <span class="grid-val" style="color:#0284c7;">همه‌چیزخوار (Omnivore)</span>
        </div>
    </div>

    <div style="font-size:7.5pt; color:#475569; margin-bottom:6px; background:#f1f5f9; padding:4px 8px; border-radius:4px;">
        <strong>ترجیحات و محدودیت‌های غذایی:</strong> {prefs_text}
    </div>

    {plan_html}
</div>
"""
        )

    html_parts.append(
        """
</body>
</html>
"""
    )

    full_html = "".join(html_parts)
    print(f"Rendering PDF with Weasyprint to {output_pdf_path}...")
    weasyprint.HTML(string=full_html).write_pdf(output_pdf_path)
    print(f"PDF generated successfully: {output_pdf_path} ({os.path.getsize(output_pdf_path):,} bytes)")


def main() -> None:
    results = run_evaluation(PROFILES)
    out_dir = Path("/home/mohammad/project/fitsho/var/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = str(out_dir / "fitsho_30_omnivore_nutrition_plans.pdf")
    render_pdf_report(results, pdf_path)

    # Also copy to root for easy web serving / access
    root_pdf_path = "/home/mohammad/project/fitsho/fitsho_30_omnivore_nutrition_plans.pdf"
    import shutil

    shutil.copyfile(pdf_path, root_pdf_path)
    print(f"Report also copied to: {root_pdf_path}")


if __name__ == "__main__":
    main()
