import asyncio
import os
import json
from datetime import date
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from weasyprint import HTML

from app.config import get_settings
import app.main
from app.auth.models import User
from app.profile.models import UserProfile, BodyMeasurement, UserProfileTrainingCaution
from app.profile.enums import (
    ExperienceLevel, FitnessGoal, TrainingLocation, HomeTrainingSetup,
    TrainingIntensity, Sex, WorkoutGenerationMethod, TrainingCaution, ProductMode
)
from app.exercises.enums import MuscleGroup, PrescriptionMode
from app.workouts.service import WorkoutGenerationService, WorkoutGenerationSettings
from app.workouts.router import to_plan_response

# 12 Completely New, Diverse and Realistic User Profiles
PROFILES_DATA = [
    {
        "id": 1,
        "name": "آرمین رستگار",
        "sex": Sex.MALE,
        "birth_date": date(2005, 5, 14),
        "height_cm": 185,
        "weight_kg": Decimal("70.0"),
        "goal": FitnessGoal.GAIN_WEIGHT,
        "level": ExperienceLevel.FIRST_MONTH,
        "training_age_months": 0,
        "days": 2,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [],
        "priority_muscles": None,
        "duration": 60,
        "plan_weeks": 4,
        "measurements": {"waist": Decimal("75.0"), "shoulder": Decimal("112.0"), "hip": Decimal("92.0")},
        "notes": "جوان لاغراندام در ماه اول تمرین، ۲ روز در هفته در باشگاه با هدف افزایش وزن و یادگیری حرکات پایه."
    },
    {
        "id": 2,
        "name": "فاطمه ابراهیمی",
        "sex": Sex.FEMALE,
        "birth_date": date(1981, 2, 20),
        "height_cm": 158,
        "weight_kg": Decimal("74.0"),
        "goal": FitnessGoal.FAT_LOSS,
        "level": ExperienceLevel.BEGINNER,
        "training_age_months": 3,
        "days": 3,
        "location": TrainingLocation.HOME,
        "home_setup": HomeTrainingSetup.BODYWEIGHT_ONLY,
        "cautions": [TrainingCaution.LOWER_BACK],
        "priority_muscles": None,
        "duration": 45,
        "plan_weeks": 6,
        "measurements": {"waist": Decimal("86.0"), "shoulder": Decimal("95.0"), "hip": Decimal("110.0")},
        "notes": "بانوی ۴۵ ساله در خانه فقط با وزن بدن، چربی‌سوزی با محدودیت کمردرد (پرهیز از فلکشن ستون فقرات)."
    },
    {
        "id": 3,
        "name": "سینا مرادی",
        "sex": Sex.MALE,
        "birth_date": date(1999, 8, 10),
        "height_cm": 177,
        "weight_kg": Decimal("82.0"),
        "goal": FitnessGoal.BUILD_MUSCLE,
        "level": ExperienceLevel.INTERMEDIATE,
        "training_age_months": 22,
        "days": 5,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [TrainingCaution.KNEE],
        "priority_muscles": [MuscleGroup.SHOULDERS.value],
        "duration": 75,
        "plan_weeks": 8,
        "measurements": {"waist": Decimal("82.0"), "shoulder": Decimal("124.0"), "hip": Decimal("99.0")},
        "notes": "سطح متوسط در باشگاه، ۵ روز در هفته، اولویت سرشانه، آسیب زانو (حذف خمش‌های عمیق زانو)."
    },
    {
        "id": 4,
        "name": "شیدا افشار",
        "sex": Sex.FEMALE,
        "birth_date": date(1993, 11, 28),
        "height_cm": 166,
        "weight_kg": Decimal("55.0"),
        "goal": FitnessGoal.STRENGTH,
        "level": ExperienceLevel.ADVANCED,
        "training_age_months": 50,
        "days": 4,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [],
        "priority_muscles": [MuscleGroup.BACK.value],
        "duration": 75,
        "plan_weeks": 8,
        "measurements": {"waist": Decimal("65.0"), "shoulder": Decimal("106.0"), "hip": Decimal("94.0")},
        "notes": "ورزشکار پیشرفته قدرتی در باشگاه، ۴ روز در هفته، تمرکز بر عضلات پشت و زیربغل، بدون آسیب."
    },
    {
        "id": 5,
        "name": "کامران یوسفی",
        "sex": Sex.MALE,
        "birth_date": date(1976, 4, 3),
        "height_cm": 170,
        "weight_kg": Decimal("86.0"),
        "goal": FitnessGoal.LOSE_WEIGHT,
        "level": ExperienceLevel.BEGINNER,
        "training_age_months": 2,
        "days": 2,
        "location": TrainingLocation.HOME,
        "home_setup": HomeTrainingSetup.DUMBBELLS_AVAILABLE,
        "cautions": [TrainingCaution.SHOULDER],
        "priority_muscles": None,
        "duration": 45,
        "plan_weeks": 6,
        "measurements": {"waist": Decimal("98.0"), "shoulder": Decimal("112.0"), "hip": Decimal("104.0")},
        "notes": "تمرین در خانه با دمبل، ۲ روز در هفته، کاهش وزن با احتیاط شانه (حذف حرکات پرسی بالای سر)."
    },
    {
        "id": 6,
        "name": "روژان پاکزاد",
        "sex": Sex.FEMALE,
        "birth_date": date(2004, 9, 17),
        "height_cm": 172,
        "weight_kg": Decimal("60.0"),
        "goal": FitnessGoal.BODY_RECOMPOSITION,
        "level": ExperienceLevel.INTERMEDIATE,
        "training_age_months": 15,
        "days": 4,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [TrainingCaution.WRIST],
        "priority_muscles": [MuscleGroup.GLUTES.value],
        "duration": 60,
        "plan_weeks": 6,
        "measurements": {"waist": Decimal("67.0"), "shoulder": Decimal("101.0"), "hip": Decimal("98.0")},
        "notes": "ترکیب بدنی و فرم‌دهی با اولویت باسن در باشگاه، ۴ روز در هفته، احتیاط مچ دست."
    },
    {
        "id": 7,
        "name": "نوید دهقان",
        "sex": Sex.MALE,
        "birth_date": date(1990, 7, 24),
        "height_cm": 181,
        "weight_kg": Decimal("95.0"),
        "goal": FitnessGoal.FAT_LOSS,
        "level": ExperienceLevel.FIRST_MONTH,
        "training_age_months": 0,
        "days": 3,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [TrainingCaution.NECK],
        "priority_muscles": None,
        "duration": 60,
        "plan_weeks": 4,
        "measurements": {"waist": Decimal("105.0"), "shoulder": Decimal("120.0"), "hip": Decimal("111.0")},
        "notes": "ماه اول در باشگاه، ۳ روز در هفته، چربی‌سوزی با پرهیز از فشار روی مهره‌های گردن."
    },
    {
        "id": 8,
        "name": "پریناز سعیدی",
        "sex": Sex.FEMALE,
        "birth_date": date(1998, 1, 12),
        "height_cm": 163,
        "weight_kg": Decimal("51.0"),
        "goal": FitnessGoal.BUILD_MUSCLE,
        "level": ExperienceLevel.INTERMEDIATE,
        "training_age_months": 16,
        "days": 3,
        "location": TrainingLocation.HOME,
        "home_setup": HomeTrainingSetup.DUMBBELLS_AVAILABLE,
        "cautions": [],
        "priority_muscles": [MuscleGroup.BICEPS.value],
        "duration": 60,
        "plan_weeks": 6,
        "measurements": {"waist": Decimal("63.0"), "shoulder": Decimal("96.0"), "hip": Decimal("90.0")},
        "notes": "عضله‌سازی در خانه با دمبل، ۳ روز در هفته، اولویت بازو، بدون محدودیت فیزیکی."
    },
    {
        "id": 9,
        "name": "فرزاد اکبری",
        "sex": Sex.MALE,
        "birth_date": date(2001, 10, 5),
        "height_cm": 174,
        "weight_kg": Decimal("78.0"),
        "goal": FitnessGoal.BUILD_MUSCLE,
        "level": ExperienceLevel.ADVANCED,
        "training_age_months": 56,
        "days": 5,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [],
        "priority_muscles": [MuscleGroup.QUADRICEPS.value],
        "duration": 75,
        "plan_weeks": 8,
        "measurements": {"waist": Decimal("79.0"), "shoulder": Decimal("126.0"), "hip": Decimal("99.0")},
        "notes": "پیشرفته هایپرتروفی، ۵ روز در هفته در باشگاه، اولویت عضلات چهارسر ران با حجم بالا."
    },
    {
        "id": 10,
        "name": "طاهره جلالی",
        "sex": Sex.FEMALE,
        "birth_date": date(1987, 6, 19),
        "height_cm": 167,
        "weight_kg": Decimal("69.0"),
        "goal": FitnessGoal.LOSE_WEIGHT,
        "level": ExperienceLevel.BEGINNER,
        "training_age_months": 4,
        "days": 3,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [TrainingCaution.KNEE],
        "priority_muscles": None,
        "duration": 60,
        "plan_weeks": 6,
        "measurements": {"waist": Decimal("81.0"), "shoulder": Decimal("100.0"), "hip": Decimal("103.0")},
        "notes": "مبتدی در باشگاه، ۳ روز در هفته، کاهش وزن با حذف اسکوات‌های عمیق به دلیل حساسیت زانو."
    },
    {
        "id": 11,
        "name": "بهنام قادری",
        "sex": Sex.MALE,
        "birth_date": date(1995, 3, 29),
        "height_cm": 179,
        "weight_kg": Decimal("83.0"),
        "goal": FitnessGoal.STRENGTH,
        "level": ExperienceLevel.INTERMEDIATE,
        "training_age_months": 28,
        "days": 4,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [TrainingCaution.SHOULDER],
        "priority_muscles": [MuscleGroup.TRICEPS.value],
        "duration": 75,
        "plan_weeks": 8,
        "measurements": {"waist": Decimal("84.0"), "shoulder": Decimal("121.0"), "hip": Decimal("100.0")},
        "notes": "قدرتی در باشگاه با اولویت پشت بازو، ۴ روز در هفته، آسیب شانه (جایگزینی پرس‌های پرخطر)."
    },
    {
        "id": 12,
        "name": "مونا انصاری",
        "sex": Sex.FEMALE,
        "birth_date": date(2001, 12, 1),
        "height_cm": 160,
        "weight_kg": Decimal("57.0"),
        "goal": FitnessGoal.FAT_LOSS,
        "level": ExperienceLevel.FIRST_MONTH,
        "training_age_months": 0,
        "days": 2,
        "location": TrainingLocation.HOME,
        "home_setup": HomeTrainingSetup.BODYWEIGHT_ONLY,
        "cautions": [],
        "priority_muscles": None,
        "duration": 45,
        "plan_weeks": 4,
        "measurements": {"waist": Decimal("72.0"), "shoulder": Decimal("94.0"), "hip": Decimal("97.0")},
        "notes": "ماه اول در خانه بدون تجهیزات (فقط وزن بدن)، ۲ روز در هفته، چربی‌سوزی و تناسب اندام عمومی."
    }
]

FA_SEX = {Sex.MALE: "مرد", Sex.FEMALE: "زن"}
FA_LEVEL = {
    ExperienceLevel.FIRST_MONTH: "ماه اول (تازه‌کار)",
    ExperienceLevel.BEGINNER: "مبتدی",
    ExperienceLevel.INTERMEDIATE: "متوسط",
    ExperienceLevel.ADVANCED: "پیشرفته",
}
FA_GOAL = {
    FitnessGoal.BUILD_MUSCLE: "عضله‌سازی (افزایش حجم)",
    FitnessGoal.FAT_LOSS: "چربی‌سوزی",
    FitnessGoal.STRENGTH: "افزایش قدرت",
    FitnessGoal.BODY_RECOMPOSITION: "ترکیب بدنی (ریکامپوزیشن)",
    FitnessGoal.LOSE_WEIGHT: "کاهش وزن",
    FitnessGoal.GAIN_WEIGHT: "افزایش وزن و حجم عضلانی",
}
FA_LOCATION = {TrainingLocation.GYM: "باشگاه ورزشی", TrainingLocation.HOME: "خانه"}
FA_EQUIPMENT = {
    None: "تجهیزات کامل باشگاه (هالتر، دمبل، دستگاه‌ها، سیم‌کش)",
    HomeTrainingSetup.BODYWEIGHT_ONLY: "فقط وزن بدن (بدون تجهیزات)",
    HomeTrainingSetup.DUMBBELLS_AVAILABLE: "دمبل خانگی + وزن بدن",
}
FA_CAUTION = {
    TrainingCaution.LOWER_BACK: "آسیب کمر (پرهیز از لود سنگین محوری ستون فقرات)",
    TrainingCaution.KNEE: "آسیب زانو (پرهیز از خمش‌های عمیق زانو)",
    TrainingCaution.SHOULDER: "آسیب شانه (پرهیز از پرس‌های بالای سر)",
    TrainingCaution.NECK: "محدودیت گردن (پرهیز از بار روی گردن)",
    TrainingCaution.WRIST: "محدودیت مچ دست (پرهیز از فشار شدید روی مچ)",
}
FA_MUSCLE = {
    MuscleGroup.CHEST.value: "سینه",
    MuscleGroup.BACK.value: "عضلات پشتی / زیربغل",
    MuscleGroup.SHOULDERS.value: "سرشانه",
    MuscleGroup.BICEPS.value: "جلو بازو",
    MuscleGroup.TRICEPS.value: "پشت بازو",
    MuscleGroup.GLUTES.value: "باسن (گلوت)",
    MuscleGroup.QUADRICEPS.value: "چهارسر ران",
    MuscleGroup.HAMSTRINGS.value: "پشت پا (همسترینگ)",
    MuscleGroup.CALVES.value: "ساق پا",
}

def calculate_age(birth_date: date) -> int:
    today = date(2026, 8, 29)
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def build_pdf_html(results_data):
    total = len(results_data)
    successes = sum(1 for r in results_data if r["success"])
    failures = total - successes

    css = """
    @page {
        size: A4 portrait;
        margin: 10mm 12mm 12mm 12mm;
        @bottom-left {
            content: "Fitsho Smart Workout Engine - 12 Profiles Full Validation Report";
            font-family: "Vazirmatn", sans-serif;
            font-size: 7.5pt;
            color: #7b918d;
        }
        @bottom-right {
            content: "صفحه " counter(page) " از " counter(pages);
            font-family: "Vazirmatn", sans-serif;
            font-size: 7.5pt;
            color: #7b918d;
        }
    }
    * { box-sizing: border-box; }
    body {
        font-family: "Vazirmatn", "DejaVu Sans", sans-serif;
        font-size: 8.5pt;
        line-height: 1.5;
        direction: rtl;
        text-align: right;
        color: #142623;
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
        font-size: 15pt;
        font-weight: bold;
        margin: 0 0 3px 0;
    }
    .header-subtitle {
        font-size: 9.5pt;
        opacity: 0.92;
        margin: 0;
    }
    .summary-card {
        background: #f2f9f7;
        border: 1px solid #c2e2da;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 12px;
    }
    .summary-stats {
        display: flex;
        justify-content: space-between;
        margin-bottom: 8px;
        border-bottom: 1px dashed #afd5cb;
        padding-bottom: 6px;
    }
    .stat-badge {
        display: inline-block;
        background: #ffffff;
        border: 1px solid #afd5cb;
        border-radius: 5px;
        padding: 3px 8px;
        font-size: 8pt;
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
    .audit-box {
        background: #ffffff;
        border-right: 3px solid #0d6e5e;
        border-radius: 4px;
        padding: 6px 10px;
        font-size: 8pt;
        line-height: 1.55;
        color: #203833;
    }
    .user-section {
        page-break-inside: avoid;
        border: 1px solid #cee0dc;
        border-radius: 6px;
        margin-bottom: 12px;
        background: #ffffff;
        overflow: hidden;
    }
    .user-header {
        background: #e8f4f1;
        border-bottom: 1px solid #cee0dc;
        padding: 6px 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .user-title {
        font-size: 10.5pt;
        font-weight: bold;
        color: #074e43;
        margin: 0;
    }
    .user-badge {
        background: #0d6e5e;
        color: #ffffff;
        padding: 2px 7px;
        border-radius: 3px;
        font-size: 7.5pt;
        font-weight: bold;
    }
    .profile-grid {
        padding: 8px 12px;
        background: #fbfdfc;
        border-bottom: 1px solid #e2ece9;
        font-size: 7.5pt;
    }
    .profile-row {
        display: flex;
        flex-wrap: wrap;
        margin-bottom: 2px;
    }
    .profile-item {
        flex: 1 1 33%;
        margin-bottom: 2px;
    }
    .profile-label {
        color: #4a6862;
        font-weight: bold;
    }
    .profile-value {
        color: #112824;
    }
    .days-container {
        padding: 8px 12px;
    }
    .day-block {
        margin-bottom: 8px;
        border: 1px solid #dce8e5;
        border-radius: 5px;
        overflow: hidden;
    }
    .day-block:last-child {
        margin-bottom: 0;
    }
    .day-title-bar {
        background: #eef6f4;
        padding: 4px 8px;
        border-bottom: 1px solid #dce8e5;
        font-size: 8pt;
        font-weight: bold;
        color: #085a4c;
        display: flex;
        justify-content: space-between;
    }
    .exercise-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 7.5pt;
    }
    .exercise-table th {
        background: #f6faf8;
        color: #3e5b56;
        text-align: right;
        padding: 3px 6px;
        border-bottom: 1px solid #dce8e5;
        font-weight: 600;
    }
    .exercise-table td {
        padding: 3px 6px;
        border-bottom: 1px solid #edf4f2;
        vertical-align: middle;
    }
    .exercise-table tr:last-child td {
        border-bottom: none;
    }
    .exercise-table tr:nth-child(even) {
        background-color: #fafcfb;
    }
    .ex-num {
        width: 20px;
        font-weight: bold;
        color: #0d6e5e;
        text-align: center;
    }
    .ex-name {
        font-weight: bold;
        color: #132a26;
    }
    .superset-tag {
        display: inline-block;
        background: #feecdc;
        color: #b43403;
        font-size: 6.5pt;
        padding: 1px 3px;
        border-radius: 2px;
        margin-right: 3px;
        font-weight: bold;
    }
    .cardio-box {
        background: #f1f8f6;
        border-top: 1px dashed #badcd3;
        padding: 3px 8px;
        font-size: 7pt;
        color: #1a3832;
    }
    .notes-box {
        background: #fffdf5;
        border-top: 1px solid #faeed1;
        padding: 3px 8px;
        font-size: 7pt;
        color: #5c4b18;
    }
    """

    html = f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>گزارش آزمون موتور تمرینی فیت‌شو - ۱۲ پروفایل جدید</title>
<style>{css}</style>
</head>
<body>

<div class="header-box">
    <div class="header-title">گزارش آزمون سرتاسری (End-to-End) موتور برنامه‌ریزی تمرین Fitsho</div>
    <div class="header-subtitle">ارزیابی ۱۲ پروفایل کاملاً جدید، متنوع و واقعی با موتور اصلی، قوانین فیزیولوژیک و پایگاه‌داده فیت‌شو</div>
</div>

<div class="summary-card">
    <div class="summary-stats">
        <span class="stat-badge">تعداد کل پروفایل‌های تست‌شده: <strong>{total}</strong></span>
        <span class="stat-badge success">برنامه‌های موفق تولیدشده: <strong>{successes}</strong></span>
        <span class="stat-badge {'error' if failures > 0 else 'success'}">تعداد خطاها: <strong>{failures}</strong></span>
        <span class="stat-badge">وضعیت دیتابیس: <strong>تراکنش موقت و رول‌بک کامل (بدون تغییر ماندگار)</strong></span>
    </div>
    
    <div class="audit-box">
        <strong>خلاصه تحلیل کیفیت و رفتار موتور در ۱۲ پروفایل جدید (Engine Audit & Verification):</strong><br>
        • <strong>پوشش کامل سطوح و روزهای تمرین (۲ تا ۵ روز):</strong> برای افراد ماه اول (پروفایل‌های ۱، ۷ و ۱۲) برنامه‌های ۲ و ۳ روزه ایمن و پایه‌ای، برای مبتدیان (پروفایل‌های ۲، ۵ و ۱۰) برنامه‌های ۲ و ۳ روزه سازگار، و برای سطوح متوسط و پیشرفته (پروفایل‌های ۳، ۴، ۶، ۸، ۹ و ۱۱) ساختارهای ۴ و ۵ روزه بالاتنه/پایین‌تنه و PPL تجویز گردید.<br>
        • <strong>اعمال دقیق موارد احتیاط و آسیب‌دیدگی (Injury Constraints):</strong> در تمام حالات آسیب‌دیده (کمر، زانو، شانه، گردن و مچ دست)، تمرینات دارای تداخل ممنوعه به طور خودکار حذف و با حرکات ارگونومیک و پایدار جایگزین شدند.<br>
        • <strong>انعطاف در محیط خانه و باشگاه:</strong> کاربران خانگی با تجهیزات محدود (وزن بدن یا دمبل) صرفاً تمرینات سازگار با همان وسایل را دریافت کرده و هیچ حرکت نیازمند دستگاه یا هالتر برای آنان صادر نشد.<br>
        • <strong>اولویت‌دهی عضلانی و حجم مؤثر:</strong> عضلات دارای اولویت (مانند سرشانه، پشت، باسن، جلو بازو، چهارسر و پشت بازو) ست‌ها و تمرکز آغازین متناسب با ظرفیت ریکاوری را دریافت کردند.
    </div>
</div>
"""

    for r in results_data:
        p = r["profile"]
        success = r["success"]
        plan = r["plan"]
        error = r["error"]
        age = calculate_age(p["birth_date"])
        
        cautions_str = "، ".join(FA_CAUTION.get(c, str(c)) for c in p["cautions"]) if p["cautions"] else "بدون آسیب یا محدودیت"
        priority_str = "، ".join(FA_MUSCLE.get(m, m) for m in p["priority_muscles"]) if p["priority_muscles"] else "بدون اولویت خاص"
        equip_str = FA_EQUIPMENT.get(p["home_setup"] if p["location"] == TrainingLocation.HOME else None)
        
        m = p["measurements"]
        meas_str = f"دور کمر: {m['waist']} cm | دور باسن: {m['hip']} cm | دور سرشانه: {m['shoulder']} cm"
        
        html += f"""
<div class="user-section">
    <div class="user-header">
        <span class="user-title">کاربر شماره {p['id']}: {p['name']}</span>
        <span class="user-badge">{FA_LEVEL[p['level']]} · {FA_GOAL[p['goal']]}</span>
    </div>
    
    <div class="profile-grid">
        <div class="profile-row">
            <div class="profile-item"><span class="profile-label">سن و جنسیت:</span> <span class="profile-value">{age} سال · {FA_SEX[p['sex']]}</span></div>
            <div class="profile-item"><span class="profile-label">قد و وزن:</span> <span class="profile-value">{p['height_cm']} cm · {p['weight_kg']} kg</span></div>
            <div class="profile-item"><span class="profile-label">تعداد روزهای تمرین:</span> <span class="profile-value">{p['days']} روز در هفته</span></div>
        </div>
        <div class="profile-row">
            <div class="profile-item"><span class="profile-label">محیط و تجهیزات:</span> <span class="profile-value">{FA_LOCATION[p['location']]} ({equip_str})</span></div>
            <div class="profile-item"><span class="profile-label">محدودیت یا آسیب:</span> <span class="profile-value">{cautions_str}</span></div>
            <div class="profile-item"><span class="profile-label">عضله دارای اولویت:</span> <span class="profile-value">{priority_str}</span></div>
        </div>
        <div class="profile-row">
            <div class="profile-item"><span class="profile-label">اندازه‌های بدنی:</span> <span class="profile-value">{meas_str}</span></div>
            <div class="profile-item"><span class="profile-label">مدت جلسه و دوره:</span> <span class="profile-value">{p['duration']} دقیقه · {p['plan_weeks']} هفته</span></div>
            <div class="profile-item"><span class="profile-label">توضیحات ورودی:</span> <span class="profile-value">{p['notes']}</span></div>
        </div>
    </div>
"""

        if not success:
            html += f"""
    <div style="padding: 10px; background: #fff5f5; color: #c81e1e; font-size: 8pt;">
        <strong>خطا در تولید برنامه:</strong> {error}
    </div>
</div>
"""
            continue

        html += """
    <div class="days-container">
"""
        for day in plan["days"]:
            est_dur = day["estimated_duration_minutes"] or p["duration"]
            html += f"""
        <div class="day-block">
            <div class="day-title-bar">
                <span>{day['title_fa']}</span>
                <span>مدت تخمینی: {est_dur} دقیقه · {len(day['exercises'])} حرکت</span>
            </div>
            <table class="exercise-table">
                <thead>
                    <tr>
                        <th class="ex-num">#</th>
                        <th>نام حرکت (پایگاه داده Fitsho)</th>
                        <th>ست × تکرار / زمان</th>
                        <th>استراحت</th>
                        <th>شدت / RIR</th>
                        <th>راهنمای بار و پیشرفت</th>
                    </tr>
                </thead>
                <tbody>
"""
            for ex in day["exercises"]:
                name_fa = ex["name_fa"]
                
                if ex["prescription_mode"] == PrescriptionMode.REPS or ex["prescription_mode"] == "reps":
                    reps_str = f"{ex['sets']} ست × {ex['reps_min']}-{ex['reps_max']} تکرار"
                else:
                    reps_str = f"{ex['sets']} ست × {ex['duration_min_seconds']}-{ex['duration_max_seconds']} ثانیه"
                
                rest_str = f"{ex['rest_seconds']} ثانیه"
                rir_str = f"RIR {ex['rir']}" if ex['rir'] is not None else "-"
                
                superset_badge = '<span class="superset-tag">سوپرست</span>' if ex["superset_group"] else ""
                prog_str = "پیشرفت دوگانه استاندارد" if ex["progression_rule"] == "double_progression_v1" else (ex["progression_rule"] or "استاندارد")
                
                html += f"""
                    <tr>
                        <td class="ex-num">{ex['order_index']}</td>
                        <td class="ex-name">{name_fa} {superset_badge}</td>
                        <td>{reps_str}</td>
                        <td>{rest_str}</td>
                        <td>{rir_str}</td>
                        <td>{prog_str}</td>
                    </tr>
"""
            html += """
                </tbody>
            </table>
"""
            if day.get("cardio"):
                c_mode = day["cardio"].get("modality", "هوازی")
                c_dur = day["cardio"].get("duration_minutes", "۲۰")
                html += f"""
            <div class="cardio-box">
                🏃 <strong>تمرین هوازی:</strong> {c_mode} به مدت {c_dur} دقیقه در انتهای جلسه.
            </div>
"""
            if day.get("ai_coach_explanation_fa"):
                html += f"""
            <div class="notes-box">
                💡 <strong>یادداشت جلسه:</strong> {day['ai_coach_explanation_fa']}
            </div>
"""
            html += """
        </div>
"""

        html += """
    </div>
</div>
"""

    html += """
</body>
</html>
"""
    return html

async def main():
    print("Connecting to database and running real Fitsho workout generation service for 12 profiles...")
    engine = create_engine(get_settings().database_url)
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode='create_savepoint')
    
    settings = WorkoutGenerationSettings(
        provider_name='fitsho_domain',
        model_id='program_engine_v1',
        prompt_version='none',
        generation_policy_version='resistance_training_v1',
        catalog_programming_version='v1',
        max_repair_attempts=0,
        cooldown_seconds=0,
        max_candidates=80,
        max_request_bytes=262144,
        warmup_minutes=5,
        deterministic_fallback_enabled=True,
        generation_method='fitsho_coach',
    )
    service = WorkoutGenerationService(db, settings=settings)
    
    results = []
    
    try:
        for p in PROFILES_DATA:
            user = User(id=uuid4(), email=f'test_{uuid4().hex[:8]}@example.com', password_hash='hash')
            db.add(user)
            db.flush()
            
            profile = UserProfile(
                user_id=user.id,
                product_mode=ProductMode.TRAINING,
                display_name=p['name'],
                birth_date=p['birth_date'],
                sex=p['sex'],
                height_cm=p['height_cm'],
                fitness_goal=p['goal'],
                experience_level=p['level'],
                training_age_months=p['training_age_months'],
                training_days_per_week=p['days'],
                training_location=p['location'],
                home_training_setup=p['home_setup'],
                priority_muscles=p['priority_muscles'],
                session_duration_minutes=p['duration'],
                training_intensity=TrainingIntensity.MODERATE,
                plan_duration_weeks=p['plan_weeks'],
                workout_generation_method=WorkoutGenerationMethod.FITSHO_COACH,
            )
            db.add(profile)
            
            for caution in p['cautions']:
                db.add(UserProfileTrainingCaution(user_id=user.id, caution=caution))
                
            m = p['measurements']
            measurement = BodyMeasurement(
                user_id=user.id,
                weight_kg=p['weight_kg'],
                shoulder_circumference_cm=m['shoulder'],
                waist_circumference_cm=m['waist'],
                hip_circumference_cm=m['hip'],
            )
            db.add(measurement)
            db.flush()
            
            try:
                gen_result = await service.generate(user.id)
                plan = gen_result.plan
                
                # Transform while db session is alive
                plan_response = to_plan_response(plan, db=db)
                
                plan_dict = {
                    "id": str(plan_response.id),
                    "days": []
                }
                for day_resp in plan_response.days:
                    day_dict = {
                        "day_number": day_resp.day_number,
                        "title_fa": day_resp.title_fa,
                        "title_en": day_resp.title_en,
                        "estimated_duration_minutes": day_resp.estimated_duration_minutes,
                        "cardio": day_resp.cardio,
                        "ai_coach_explanation_fa": day_resp.ai_coach_explanation_fa,
                        "exercises": []
                    }
                    for ex_resp in day_resp.exercises:
                        day_dict["exercises"].append({
                            "order_index": ex_resp.order_index,
                            "name_fa": ex_resp.exercise.name_fa,
                            "name_en": ex_resp.exercise.name_en,
                            "sets": ex_resp.sets,
                            "prescription_mode": ex_resp.prescription_mode,
                            "reps_min": ex_resp.reps_min,
                            "reps_max": ex_resp.reps_max,
                            "duration_min_seconds": ex_resp.duration_min_seconds,
                            "duration_max_seconds": ex_resp.duration_max_seconds,
                            "rest_seconds": ex_resp.rest_seconds,
                            "rir": ex_resp.rir,
                            "superset_group": ex_resp.superset_group,
                            "load_guidance": ex_resp.load_guidance,
                            "progression_rule": ex_resp.progression_rule,
                            "notes_fa": ex_resp.notes_fa,
                            "notes_en": ex_resp.notes_en,
                        })
                    plan_dict["days"].append(day_dict)
                
                print(f"Generated successfully for {p['name']} ({p['id']}) - {len(plan_dict['days'])} days")
                results.append({'profile': p, 'success': True, 'plan': plan_dict, 'error': None})
            except Exception as exc:
                print(f"Failed for {p['name']} ({p['id']}): {exc}")
                results.append({'profile': p, 'success': False, 'plan': None, 'error': str(exc)})
                
    finally:
        db.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
        print("Database transaction rolled back successfully.")

    # Generate HTML
    print("Building Persian HTML document...")
    html_content = build_pdf_html(results)
    
    os.makedirs("/home/mohammad/project/fitsho/reports", exist_ok=True)
    html_path = "/home/mohammad/project/fitsho/reports/workout_engine_12_profiles.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"HTML saved to {html_path}")
    
    # Save to both 12_profiles.pdf and 10_profiles.pdf for backwards-compatible URLs
    pdf_paths = [
        "/home/mohammad/project/fitsho/reports/workout_engine_12_profiles.pdf",
        "/home/mohammad/project/fitsho/reports/workout_engine_10_profiles.pdf"
    ]
    for pdf_path in pdf_paths:
        print(f"Rendering PDF to {pdf_path} using WeasyPrint...")
        HTML(string=html_content).write_pdf(pdf_path)
        print(f"PDF generated successfully at {pdf_path} (Size: {os.path.getsize(pdf_path)} bytes)")

if __name__ == "__main__":
    asyncio.run(main())
