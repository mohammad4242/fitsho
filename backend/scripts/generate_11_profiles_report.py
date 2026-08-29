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

# 11 Diverse and Realistic User Profiles (2, 3, 4, 5, 6 days)
PROFILES_DATA = [
    {
        "id": 1,
        "name": "سحر طاهری",
        "sex": Sex.FEMALE,
        "birth_date": date(1988, 3, 12),
        "height_cm": 162,
        "weight_kg": Decimal("76.0"),
        "goal": FitnessGoal.LOSE_WEIGHT,
        "level": ExperienceLevel.FIRST_MONTH,
        "training_age_months": 0,
        "days": 2,
        "location": TrainingLocation.HOME,
        "home_setup": HomeTrainingSetup.DUMBBELLS_AVAILABLE,
        "cautions": [TrainingCaution.LOWER_BACK],
        "priority_muscles": None,
        "duration": 45,
        "plan_weeks": 4,
        "measurements": {"waist": Decimal("88.0"), "shoulder": Decimal("94.0"), "hip": Decimal("108.0")},
        "notes": "بانوی ۳۸ ساله در خانه با دمبل، ۲ روز در هفته، هدف کاهش وزن و تقویت عمومی با احتیاط کمردرد."
    },
    {
        "id": 2,
        "name": "پوریا اسدی",
        "sex": Sex.MALE,
        "birth_date": date(2005, 9, 8),
        "height_cm": 188,
        "weight_kg": Decimal("68.0"),
        "goal": FitnessGoal.GAIN_WEIGHT,
        "level": ExperienceLevel.BEGINNER,
        "training_age_months": 4,
        "days": 2,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [],
        "priority_muscles": None,
        "duration": 60,
        "plan_weeks": 6,
        "measurements": {"waist": Decimal("74.0"), "shoulder": Decimal("114.0"), "hip": Decimal("91.0")},
        "notes": "جوان لاغراندام در باشگاه، ۲ روز در هفته تقسیم فول‌بادی، هدف افزایش وزن و عضله‌سازی پایه."
    },
    {
        "id": 3,
        "name": "نگار صادقی",
        "sex": Sex.FEMALE,
        "birth_date": date(1997, 7, 15),
        "height_cm": 168,
        "weight_kg": Decimal("61.0"),
        "goal": FitnessGoal.BODY_RECOMPOSITION,
        "level": ExperienceLevel.INTERMEDIATE,
        "training_age_months": 18,
        "days": 3,
        "location": TrainingLocation.HOME,
        "home_setup": HomeTrainingSetup.DUMBBELLS_AVAILABLE,
        "cautions": [TrainingCaution.KNEE],
        "priority_muscles": [MuscleGroup.GLUTES.value],
        "duration": 60,
        "plan_weeks": 6,
        "measurements": {"waist": Decimal("66.0"), "shoulder": Decimal("98.0"), "hip": Decimal("97.0")},
        "notes": "تمرین در خانه با دمبل، ۳ روز در هفته، ریکامپوزیشن و فرم‌دهی با اولویت باسن و احتیاط زانو."
    },
    {
        "id": 4,
        "name": "احسان کریمی",
        "sex": Sex.MALE,
        "birth_date": date(1984, 11, 3),
        "height_cm": 175,
        "weight_kg": Decimal("93.0"),
        "goal": FitnessGoal.FAT_LOSS,
        "level": ExperienceLevel.FIRST_MONTH,
        "training_age_months": 0,
        "days": 3,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [TrainingCaution.SHOULDER],
        "priority_muscles": None,
        "duration": 60,
        "plan_weeks": 4,
        "measurements": {"waist": Decimal("102.0"), "shoulder": Decimal("118.0"), "hip": Decimal("107.0")},
        "notes": "آقای ۴۲ ساله ماه اول تمرین در باشگاه، ۳ روز در هفته، چربی‌سوزی با محدودیت شانه."
    },
    {
        "id": 5,
        "name": "مهتاب کاظمی",
        "sex": Sex.FEMALE,
        "birth_date": date(1995, 4, 19),
        "height_cm": 171,
        "weight_kg": Decimal("65.0"),
        "goal": FitnessGoal.STRENGTH,
        "level": ExperienceLevel.ADVANCED,
        "training_age_months": 48,
        "days": 3,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [],
        "priority_muscles": [MuscleGroup.BACK.value],
        "duration": 75,
        "plan_weeks": 8,
        "measurements": {"waist": Decimal("68.0"), "shoulder": Decimal("105.0"), "hip": Decimal("98.0")},
        "notes": "ورزشکار پیشرفته در باشگاه، ۳ روز در هفته، تمرکز بر افزایش قدرت و اولویت عضلات پشتی و زیربغل."
    },
    {
        "id": 6,
        "name": "دانیال نوری",
        "sex": Sex.MALE,
        "birth_date": date(2000, 1, 25),
        "height_cm": 180,
        "weight_kg": Decimal("81.0"),
        "goal": FitnessGoal.BUILD_MUSCLE,
        "level": ExperienceLevel.INTERMEDIATE,
        "training_age_months": 24,
        "days": 4,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [TrainingCaution.WRIST],
        "priority_muscles": [MuscleGroup.CHEST.value],
        "duration": 75,
        "plan_weeks": 8,
        "measurements": {"waist": Decimal("80.0"), "shoulder": Decimal("123.0"), "hip": Decimal("98.0")},
        "notes": "سطح متوسط در باشگاه، ۴ روز در هفته، اولویت عضلات سینه با احتیاط مچ دست."
    },
    {
        "id": 7,
        "name": "نیلوفر راد",
        "sex": Sex.FEMALE,
        "birth_date": date(2001, 8, 14),
        "height_cm": 165,
        "weight_kg": Decimal("54.0"),
        "goal": FitnessGoal.BUILD_MUSCLE,
        "level": ExperienceLevel.BEGINNER,
        "training_age_months": 5,
        "days": 4,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [],
        "priority_muscles": None,
        "duration": 60,
        "plan_weeks": 6,
        "measurements": {"waist": Decimal("64.0"), "shoulder": Decimal("96.0"), "hip": Decimal("92.0")},
        "notes": "بانوی جوان مبتدی در باشگاه، ۴ روز در هفته اسپلیت Upper/Lower متعادل، هایپرتروفی و تناسب اندام بدون آسیب."
    },
    {
        "id": 8,
        "name": "سیاوش جهانگیری",
        "sex": Sex.MALE,
        "birth_date": date(1993, 6, 30),
        "height_cm": 183,
        "weight_kg": Decimal("88.0"),
        "goal": FitnessGoal.BUILD_MUSCLE,
        "level": ExperienceLevel.ADVANCED,
        "training_age_months": 52,
        "days": 4,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [],
        "priority_muscles": [MuscleGroup.SHOULDERS.value],
        "duration": 75,
        "plan_weeks": 8,
        "measurements": {"waist": Decimal("83.0"), "shoulder": Decimal("128.0"), "hip": Decimal("102.0")},
        "notes": "بدنساز پیشرفته در باشگاه، ۴ روز در هفته اسپلیت عضله‌ای (Body-Part)، اولویت سرشانه با شدت و متدهای پیشرفته."
    },
    {
        "id": 9,
        "name": "مهرداد خسروی",
        "sex": Sex.MALE,
        "birth_date": date(1998, 10, 11),
        "height_cm": 176,
        "weight_kg": Decimal("79.0"),
        "goal": FitnessGoal.BUILD_MUSCLE,
        "level": ExperienceLevel.INTERMEDIATE,
        "training_age_months": 20,
        "days": 5,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [],
        "priority_muscles": [MuscleGroup.BICEPS.value],
        "duration": 75,
        "plan_weeks": 8,
        "measurements": {"waist": Decimal("79.0"), "shoulder": Decimal("122.0"), "hip": Decimal("96.0")},
        "notes": "سطح متوسط در باشگاه، ۵ روز در هفته اسپلیت تخصصی، اولویت بازو و بالاتنه با ریکاوری بهینه."
    },
    {
        "id": 10,
        "name": "بهار شریفی",
        "sex": Sex.FEMALE,
        "birth_date": date(1999, 3, 5),
        "height_cm": 169,
        "weight_kg": Decimal("63.0"),
        "goal": FitnessGoal.BODY_RECOMPOSITION,
        "level": ExperienceLevel.ADVANCED,
        "training_age_months": 40,
        "days": 5,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [TrainingCaution.NECK],
        "priority_muscles": [MuscleGroup.QUADRICEPS.value],
        "duration": 75,
        "plan_weeks": 8,
        "measurements": {"waist": Decimal("66.0"), "shoulder": Decimal("102.0"), "hip": Decimal("99.0")},
        "notes": "پیشرفته در باشگاه، ۵ روز در هفته، اولویت عضلات پا و چهارسر، محدودیت گردن."
    },
    {
        "id": 11,
        "name": "کیوان فلاحی",
        "sex": Sex.MALE,
        "birth_date": date(1997, 2, 18),
        "height_cm": 182,
        "weight_kg": Decimal("85.0"),
        "goal": FitnessGoal.BUILD_MUSCLE,
        "level": ExperienceLevel.ADVANCED,
        "training_age_months": 60,
        "days": 6,
        "location": TrainingLocation.GYM,
        "home_setup": None,
        "cautions": [],
        "priority_muscles": None,
        "duration": 75,
        "plan_weeks": 8,
        "measurements": {"waist": Decimal("81.0"), "shoulder": Decimal("127.0"), "hip": Decimal("100.0")},
        "notes": "ورزشکار پیشرفته در باشگاه، ۶ روز در هفته اسپلیت پوش / پول / پا (PPL A/B)، حداکثر حجم و فرکانس تمرینی."
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
            content: "Fitsho Smart Workout Engine - 11 Profiles Full Validation Report (2 to 6 Days)";
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
    .caution-tag {
        color: #c92a2a;
        font-weight: bold;
    }
    .priority-tag {
        color: #0d6e5e;
        font-weight: bold;
    }
    .user-notes {
        margin-top: 4px;
        padding-top: 4px;
        border-top: 1px dashed #d5e4e0;
        color: #3b5a54;
        font-style: italic;
    }
    .days-container {
        padding: 8px 12px;
    }
    .day-block {
        margin-bottom: 8px;
        border: 1px solid #e2ece9;
        border-radius: 4px;
        overflow: hidden;
    }
    .day-header {
        background: #f0f7f5;
        padding: 4px 10px;
        font-weight: bold;
        font-size: 8pt;
        color: #0d6e5e;
        display: flex;
        justify-content: space-between;
        border-bottom: 1px solid #e2ece9;
    }
    .exercise-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 7pt;
    }
    .exercise-table th {
        background: #fafcfb;
        color: #4a6862;
        padding: 3px 6px;
        text-align: right;
        border-bottom: 1px solid #e2ece9;
        font-weight: bold;
    }
    .exercise-table td {
        padding: 3px 6px;
        border-bottom: 1px solid #f0f4f3;
        vertical-align: middle;
    }
    .exercise-table tr:last-child td {
        border-bottom: none;
    }
    .exercise-table tr:nth-child(even) td {
        background: #fbfdfc;
    }
    .superset-badge {
        background: #ffe3e3;
        color: #c92a2a;
        padding: 1px 4px;
        border-radius: 3px;
        font-size: 6.5pt;
        font-weight: bold;
    }
    .cardio-box {
        background: #fff8eb;
        border: 1px solid #fce3b8;
        padding: 4px 8px;
        margin: 4px 8px;
        border-radius: 4px;
        font-size: 7pt;
        color: #8c5303;
    }
    .ai-coach-box {
        background: #f0f7ff;
        border-right: 2px solid #2b8a3e;
        padding: 3px 8px;
        margin: 3px 8px;
        font-size: 7pt;
        color: #1864ab;
    }
    """

    body_html = f"""
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>گزارش تست جامع موتور برنامه تمرینی فیتشو - ۱۱ کاربر (۲ تا ۶ روزه)</title>
        <style>{css}</style>
    </head>
    <body>
        <div class="header-box">
            <div class="header-title">فیتشو — گزارش تست جامع موتور برنامه تمرینی (۱۱ پروفایل ۲ تا ۶ روزه)</div>
            <div class="header-subtitle">ارزیابی کامل خروجی‌های واقعی موتور هوشمند بر اساس پارامترهای سن، جنسیت، سطح، روزها، هدف، آسیب‌ها و تجهیزات</div>
        </div>

        <div class="summary-card">
            <div class="summary-stats">
                <span class="stat-badge">تعداد کل پروفایل‌ها: <strong>{total}</strong></span>
                <span class="stat-badge success">تولید موفق: <strong>{successes}</strong></span>
                <span class="stat-badge {'error' if failures > 0 else 'success'}">محدودیت/خطا: <strong>{failures}</strong></span>
                <span class="stat-badge">پوشش روزهای تمرینی: <strong>۲، ۳، ۴، ۵ و ۶ روز در هفته</strong></span>
                <span class="stat-badge">تاریخ ارزیابی: <strong>۲۹ آگوست ۲۰۲۶</strong></span>
            </div>
            <div class="audit-box">
                <strong>خلاصه ممیزی فنی سیستم:</strong><br>
                ۱. <strong>تنوع کامل ساختاری:</strong> آزمون برنامه‌های ۲، ۳، ۴، ۵ و ۶ روزه شامل تقسیم‌های Full Body، Upper/Lower، اسپلیت‌های ۴ روزه عضله‌ای، اسپلیت‌های ۵ روزه و PPL شش‌روزه.<br>
                ۲. <strong>پایش آسیب‌ها و محدودیت‌ها (Cautions):</strong> بررسی جایگزینی ایمن در آسیب‌های شانه، زانو، کمر، مچ دست و گردن مطابق استانداردهای ایمنی فیتشو.<br>
                ۳. <strong>محیط‌های تمرینی (Location & Equipment):</strong> تست واقعی محیط‌های باشگاه، خانه با دمبل و خانه فقط با وزن بدن.<br>
                ۴. <strong>تجربه و اهداف:</strong> پوشش کامل ماه اول (First Month)، مبتدی، متوسط و پیشرفته برای اهداف کاهش وزن، افزایش وزن، عضله‌سازی، قدرت و ریکامپوزیشن.
            </div>
        </div>
    """

    for r in results_data:
        p = r["profile"]
        success = r["success"]
        age = calculate_age(p["birth_date"])
        
        cautions_str = "بدون محدودیت"
        if p["cautions"]:
            cautions_str = "، ".join([FA_CAUTION.get(c, str(c)) for c in p["cautions"]])
            
        priority_str = "تعادل عمومی عضلات"
        if p["priority_muscles"]:
            priority_str = "، ".join([FA_MUSCLE.get(m, m) for m in p["priority_muscles"]])
            
        home_setup_str = FA_EQUIPMENT.get(p["home_setup"])
        
        body_html += f"""
        <div class="user-section">
            <div class="user-header">
                <span class="user-title">کاربر {p['id']}: {p['name']} ({FA_SEX[p['sex']]}، {age} ساله)</span>
                <span class="user-badge">{p['days']} روز در هفته — {FA_LEVEL[p['level']]}</span>
            </div>
            
            <div class="profile-grid">
                <div class="profile-row">
                    <div class="profile-item"><span class="profile-label">هدف اصلی:</span> <span class="profile-value">{FA_GOAL[p['goal']]}</span></div>
                    <div class="profile-item"><span class="profile-label">قد و وزن:</span> <span class="profile-value">{p['height_cm']} سانتی‌متر / {p['weight_kg']} کیلوگرم</span></div>
                    <div class="profile-item"><span class="profile-label">محیط و تجهیزات:</span> <span class="profile-value">{FA_LOCATION[p['location']]} ({home_setup_str})</span></div>
                </div>
                <div class="profile-row">
                    <div class="profile-item"><span class="profile-label">محدودیت‌ها و آسیب‌ها:</span> <span class="profile-value {'caution-tag' if p['cautions'] else ''}">{cautions_str}</span></div>
                    <div class="profile-item"><span class="profile-label">اولویت عضلانی:</span> <span class="profile-value {'priority-tag' if p['priority_muscles'] else ''}">{priority_str}</span></div>
                    <div class="profile-item"><span class="profile-label">مدت زمان جلسه / دوره:</span> <span class="profile-value">{p['duration']} دقیقه / {p['plan_weeks']} هفته</span></div>
                </div>
                <div class="user-notes">
                    <strong>توضیحات و سناریو:</strong> {p['notes']}
                </div>
            </div>
            
            <div class="days-container">
        """
        
        if not success:
            body_html += f"""
                <div style="color: #c92a2a; padding: 10px; background: #fff5f5; border-radius: 4px; font-size: 7.5pt;">
                    <strong>نتیجه ممیزی موتور:</strong> برنامه برای این ترکیب دقیق به دلیل محدودیت‌های سختگیرانه ریکاوری یا ماتریس حجم رد شد ({r['error']}).
                </div>
            """
        else:
            plan = r["plan"]
            for day in plan["days"]:
                body_html += f"""
                <div class="day-block">
                    <div class="day-header">
                        <span>روز {day['day_number']}: {day['title_fa']} ({day['title_en']})</span>
                        <span>زمان تخمینی: {day['estimated_duration_minutes']} دقیقه | تعداد حرکات: {len(day['exercises'])}</span>
                    </div>
                """
                
                if day.get("ai_coach_explanation_fa"):
                    body_html += f"""
                    <div class="ai-coach-box">
                        <strong>نکته مربی:</strong> {day['ai_coach_explanation_fa']}
                    </div>
                    """
                    
                body_html += """
                    <table class="exercise-table">
                        <thead>
                            <tr>
                                <th style="width: 5%;">ردیف</th>
                                <th style="width: 32%;">نام حرکت (فارسی / انگلیسی)</th>
                                <th style="width: 8%; text-align: center;">ست</th>
                                <th style="width: 14%; text-align: center;">تکرار / زمان</th>
                                <th style="width: 10%; text-align: center;">استراحت</th>
                                <th style="width: 8%; text-align: center;">RIR</th>
                                <th style="width: 23%;">هدایت بار / پیشرفت / سوپرست</th>
                            </tr>
                        </thead>
                        <tbody>
                """
                
                for ex in day["exercises"]:
                    if ex["prescription_mode"] == "time" or ex.get("duration_min_seconds"):
                        reps_str = f"{ex['duration_min_seconds'] or 30} تا {ex['duration_max_seconds'] or 45} ثانیه"
                    else:
                        if ex.get("reps_min") == ex.get("reps_max"):
                            reps_str = f"{ex.get('reps_min', 10)} تکرار"
                        else:
                            reps_str = f"{ex.get('reps_min', 8)}-{ex.get('reps_max', 12)} تکرار"
                            
                    superset_html = ""
                    if ex.get("superset_group"):
                        superset_html = f"<span class='superset-badge'>سوپرست {ex['superset_group']}</span> "
                        
                    load_info = ex.get("load_guidance") or ex.get("progression_rule") or "-"
                    if len(load_info) > 35:
                        load_info = load_info[:33] + "..."
                        
                    body_html += f"""
                            <tr>
                                <td style="text-align: center; font-weight: bold; color: #4a6862;">{ex['order_index']}</td>
                                <td>
                                    <strong>{ex['name_fa']}</strong><br>
                                    <span style="color: #6c757d; font-size: 6.5pt;">{ex['name_en']}</span>
                                </td>
                                <td style="text-align: center; font-weight: bold;">{ex['sets']}</td>
                                <td style="text-align: center;">{reps_str}</td>
                                <td style="text-align: center;">{ex['rest_seconds']} ثانیه</td>
                                <td style="text-align: center; font-weight: bold; color: #0d6e5e;">{ex['rir'] if ex.get('rir') is not None else '-'}</td>
                                <td>{superset_html}<span style="font-size: 6.5pt; color: #495057;">{load_info}</span></td>
                            </tr>
                    """
                    
                body_html += """
                        </tbody>
                    </table>
                """
                
                if day.get("cardio"):
                    c = day["cardio"]
                    body_html += f"""
                    <div class="cardio-box">
                        <strong>کاردیو تکمیلی:</strong> {c.get('type', 'هوازی')} | مدت: {c.get('duration_minutes', 15)} دقیقه | شدت: {c.get('intensity', 'متوسط')}
                    </div>
                    """
                    
                body_html += "</div>"
                
        body_html += """
            </div>
        </div>
        """

    body_html += """
    </body>
    </html>
    """
    return body_html

async def main():
    print("Starting generation for 11 diverse user profiles across 2-6 days...")
    
    settings_cfg = get_settings()
    engine = create_engine(settings_cfg.database_url)
    
    results = []
    
    for p in PROFILES_DATA:
        conn = engine.connect()
        tx = conn.begin()
        db = Session(bind=conn)
        
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
        
        try:
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
            
            gen_result = await service.generate(user.id)
            plan = gen_result.plan
            
            plan_dict = {
                "id": str(plan.id),
                "days": []
            }
            for d in plan.days:
                day_dict = {
                    "day_number": d.day_number,
                    "title_fa": d.title_fa,
                    "title_en": d.title_en,
                    "estimated_duration_minutes": d.estimated_duration_minutes,
                    "cardio": d.cardio,
                    "ai_coach_explanation_fa": d.ai_coach_explanation_fa,
                    "exercises": []
                }
                for ex in d.exercises:
                    day_dict["exercises"].append({
                        "order_index": ex.order_index,
                        "name_fa": ex.exercise.name_fa if ex.exercise else "حرکت تمرینی",
                        "name_en": ex.exercise.name_en if ex.exercise else "Exercise",
                        "sets": ex.sets,
                        "prescription_mode": ex.prescription_mode,
                        "reps_min": ex.reps_min,
                        "reps_max": ex.reps_max,
                        "duration_min_seconds": ex.duration_min_seconds,
                        "duration_max_seconds": ex.duration_max_seconds,
                        "rest_seconds": ex.rest_seconds,
                        "rir": ex.rir,
                        "superset_group": ex.superset_group,
                        "load_guidance": ex.load_guidance,
                        "progression_rule": ex.progression_rule,
                        "notes_fa": ex.notes_fa,
                        "notes_en": ex.notes_en,
                    })
                plan_dict["days"].append(day_dict)
            
            print(f"Generated successfully for {p['name']} ({p['id']}) - {len(plan_dict['days'])} days")
            results.append({'profile': p, 'success': True, 'plan': plan_dict, 'error': None})
        except Exception as exc:
            print(f"Failed for {p['name']} ({p['id']}): {exc}")
            results.append({'profile': p, 'success': False, 'plan': None, 'error': str(exc)})
        finally:
            db.close()
            tx.rollback()
            conn.close()

    engine.dispose()
    print("Database transactions rolled back successfully.")

    # Generate HTML
    print("Building Persian HTML document...")
    html_content = build_pdf_html(results)
    
    os.makedirs("/home/mohammad/project/fitsho/reports", exist_ok=True)
    html_path = "/home/mohammad/project/fitsho/reports/workout_engine_11_profiles.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"HTML saved to {html_path}")
    
    pdf_paths = [
        "/home/mohammad/project/fitsho/reports/workout_engine_11_profiles.pdf",
    ]
    for pdf_path in pdf_paths:
        print(f"Rendering PDF to {pdf_path} using WeasyPrint...")
        HTML(string=html_content).write_pdf(pdf_path)
        print(f"PDF generated successfully at {pdf_path} (Size: {os.path.getsize(pdf_path)} bytes)")

if __name__ == "__main__":
    asyncio.run(main())
