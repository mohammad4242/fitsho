import base64
from html import escape
from mimetypes import guess_type
from pathlib import Path

from weasyprint import HTML  # type: ignore[import-untyped]

from app.config import get_settings
from app.nutrition.schemas import WeeklyPlanDayResponse, WeeklyPlanMealResponse, WeeklyPlanResponse

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

_WEEKDAY_NAMES_FA = [
    "شنبه",
    "یکشنبه",
    "دوشنبه",
    "سه‌شنبه",
    "چهارشنبه",
    "پنجشنبه",
    "جمعه",
]

_SLOT_ROLE_FA = {
    "breakfast": "صبحانه",
    "morning_snack": "میان‌وعده صبح",
    "lunch": "ناهار",
    "afternoon_snack": "عصرانه",
    "dinner": "شام",
    "evening_snack": "میان‌وعده شب",
    "pre_workout": "قبل از تمرین",
    "post_workout": "بعد از تمرین",
    "free_meal": "وعده آزاد",
}

PDF_CSS = """
@page {
  size: A4;
  margin: 14mm 12mm 14mm 12mm;
  @bottom-right {
    content: "فیت‌شو (Fitsho) — برنامه اختصاصی تغذیه و رژیم غذایی";
    font-family: "Vazirmatn", "DejaVu Sans", sans-serif;
    font-size: 8pt;
    color: #728a84;
  }
  @bottom-left {
    content: "صفحه " counter(page) " از " counter(pages);
    font-family: "Vazirmatn", "DejaVu Sans", sans-serif;
    font-size: 8pt;
    color: #728a84;
  }
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  color: #102622;
  font-family: "Vazirmatn", "DejaVu Sans", sans-serif;
  font-size: 9.5pt;
  line-height: 1.6;
  direction: rtl;
  text-align: right;
  background-color: #ffffff;
}

.hero {
  background: linear-gradient(135deg, #094e43 0%, #087d6c 100%);
  color: #ffffff;
  padding: 14px 18px;
  border-radius: 6px;
  margin-bottom: 12px;
}

.hero-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.22);
  padding-bottom: 6px;
  margin-bottom: 8px;
}

.brand-badge {
  background: #ffffff;
  color: #087d6c;
  font-weight: 800;
  font-size: 11pt;
  padding: 2px 8px;
  border-radius: 4px;
  display: inline-block;
}

.plan-status {
  font-size: 8.5pt;
  color: #d1fae5;
  font-weight: bold;
}

.hero-title {
  font-size: 16pt;
  font-weight: 800;
  margin-bottom: 4px;
}

.hero-meta {
  font-size: 8.5pt;
  color: #d1fae5;
  display: flex;
  gap: 12px;
}

.day {
  margin-bottom: 12px;
  border: 1px solid #d4e3e0;
  border-radius: 6px;
  overflow: hidden;
  break-inside: avoid;
  background: #ffffff;
}

.day-header {
  background: #eef8f5;
  border-bottom: 1px solid #b8cbc6;
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.day-title {
  font-size: 11pt;
  font-weight: 700;
  color: #087d6c;
}

.day-macros {
  font-size: 8.5pt;
  color: #354b46;
  font-weight: bold;
  display: flex;
  gap: 8px;
}

.day-macro-item {
  background: #ffffff;
  border: 1px solid #c2d8d2;
  border-radius: 4px;
  padding: 1px 6px;
}

.meals-grid {
  padding: 8px;
}

.meal-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  border-bottom: 1px solid #eef3f1;
  padding: 8px 4px;
}

.meal-card:last-child {
  border-bottom: none;
}

.meal-thumb {
  width: 58px;
  height: 58px;
  min-width: 58px;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #d4e3e0;
  background-color: #f3f7f5;
  display: flex;
  align-items: center;
  justify-content: center;
}

.meal-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.meal-thumb-fallback {
  color: #087d6c;
  font-size: 8pt;
  font-weight: bold;
  text-align: center;
  padding: 4px;
  background: #e6f3ef;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.meal-body {
  flex: 1;
}

.meal-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 3px;
}

.meal-slot-badge {
  background: #087d6c;
  color: #ffffff;
  font-size: 7.5pt;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  display: inline-block;
}

.meal-name {
  font-size: 10pt;
  font-weight: 700;
  color: #1a2e2b;
}

.meal-foods {
  font-size: 8.5pt;
  color: #4a5d59;
  margin-bottom: 4px;
  line-height: 1.4;
}

.meal-macros {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.macro-chip {
  font-size: 7.5pt;
  border-radius: 3px;
  padding: 1px 5px;
  font-weight: 600;
}

.macro-cal {
  background: #fef3c7;
  color: #92400e;
}

.macro-pro {
  background: #e0f2fe;
  color: #0369a1;
}

.macro-carb {
  background: #f3e8ff;
  color: #6b21a8;
}

.macro-fat {
  background: #fee2e2;
  color: #991b1b;
}
"""


def _fa_number(val: int | float | str) -> str:
    if isinstance(val, float):
        if val.is_integer():
            s = str(int(val))
        else:
            s = f"{val:.1f}"
    else:
        s = str(val)
    return s.translate(_PERSIAN_DIGITS)


def _resolve_image_data_uri(image_url: str | None) -> str | None:
    if not image_url or not isinstance(image_url, str):
        return None
    image_str = image_url.strip()
    if image_str.startswith("data:"):
        return image_str

    settings = get_settings()
    # If it is a relative media path like /media/...
    rel_path = image_str
    if rel_path.startswith(settings.media_public_path):
        rel_path = rel_path[len(settings.media_public_path) :].lstrip("/")

    file_path = (settings.media_root / rel_path).resolve()
    if file_path.is_file():
        try:
            content = file_path.read_bytes()
            mime, _ = guess_type(file_path.name)
            mime = mime or "image/jpeg"
            encoded = base64.b64encode(content).decode("ascii")
            return f"data:{mime};base64,{encoded}"
        except OSError:
            return None

    direct_path = Path(image_str).resolve()
    if direct_path.is_file():
        try:
            content = direct_path.read_bytes()
            mime, _ = guess_type(direct_path.name)
            mime = mime or "image/jpeg"
            encoded = base64.b64encode(content).decode("ascii")
            return f"data:{mime};base64,{encoded}"
        except OSError:
            return None

    return None


def _render_meal_thumb(image_url: str | None, slot_label: str) -> str:
    data_uri = _resolve_image_data_uri(image_url)
    if data_uri:
        return f'<div class="meal-thumb"><img src="{data_uri}" alt="{escape(slot_label)}"/></div>'
    return (
        f'<div class="meal-thumb"><div class="meal-thumb-fallback">{escape(slot_label)}</div></div>'
    )


def _render_meal(meal: WeeklyPlanMealResponse) -> str:
    slot_label = _SLOT_ROLE_FA.get(meal.slot_role, meal.slot_role)
    meal_name = meal.name_fa.strip() if meal.name_fa and meal.name_fa.strip() else slot_label
    thumb = _render_meal_thumb(meal.image_url, slot_label)

    food_items: list[str] = []
    for food in meal.foods:
        name = escape(food.name_fa)
        if food.grams > 0:
            food_items.append(f"{name} ({_fa_number(round(food.grams))} گرم)")
        else:
            food_items.append(name)
    foods_str = " + ".join(food_items) if food_items else "—"

    cal = round(meal.nutrient_totals.get("energy_kcal", 0))
    pro = round(meal.nutrient_totals.get("protein_g", 0), 1)
    carb = round(meal.nutrient_totals.get("carbohydrate_g", 0), 1)
    fat = round(meal.nutrient_totals.get("fat_g", 0), 1)

    macros_html = (
        f'<span class="macro-chip macro-cal">{_fa_number(cal)} کیلوکالری</span>'
        f'<span class="macro-chip macro-pro">پروتئین {_fa_number(pro)}g</span>'
        f'<span class="macro-chip macro-carb">کربوهیدرات {_fa_number(carb)}g</span>'
        f'<span class="macro-chip macro-fat">چربی {_fa_number(fat)}g</span>'
    )

    return f"""
    <div class="meal-card">
      {thumb}
      <div class="meal-body">
        <div class="meal-header">
          <span class="meal-slot-badge">{escape(slot_label)}</span>
          <span class="meal-name">{escape(meal_name)}</span>
        </div>
        <div class="meal-foods">{foods_str}</div>
        <div class="meal-macros">{macros_html}</div>
      </div>
    </div>
    """


def _render_day(day: WeeklyPlanDayResponse) -> str:
    weekday_index = day.day_index % len(_WEEKDAY_NAMES_FA)
    weekday_name = _WEEKDAY_NAMES_FA[weekday_index]
    day_num = _fa_number(day.day_index + 1)

    cal = round(day.nutrient_totals.get("energy_kcal", 0))
    pro = round(day.nutrient_totals.get("protein_g", 0), 1)
    carb = round(day.nutrient_totals.get("carbohydrate_g", 0), 1)
    fat = round(day.nutrient_totals.get("fat_g", 0), 1)

    day_macros_html = (
        f'<span class="day-macro-item">کالری: {_fa_number(cal)} kcal</span>'
        f'<span class="day-macro-item">پروتئین: {_fa_number(pro)}g</span>'
        f'<span class="day-macro-item">کربو: {_fa_number(carb)}g</span>'
        f'<span class="day-macro-item">چربی: {_fa_number(fat)}g</span>'
    )

    meals_html = "".join(_render_meal(m) for m in day.meals)

    date_str = escape(day.plan_date.isoformat())
    return f"""
    <section class="day">
      <div class="day-header">
        <div class="day-title">روز {day_num} ({weekday_name}) · {date_str}</div>
        <div class="day-macros">{day_macros_html}</div>
      </div>
      <div class="meals-grid">
        {meals_html}
      </div>
    </section>
    """


def build_nutrition_plan_html(plan: WeeklyPlanResponse) -> str:
    status_label = "تأیید شده توسط پزشک" if plan.physician_approved else "نسخه اولیه برنامه"
    avg_cal = round(
        sum(d.nutrient_totals.get("energy_kcal", 0) for d in plan.days) / max(1, len(plan.days))
    )

    days_html = "".join(_render_day(day) for day in plan.days)

    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>برنامه تغذیه فیت‌شو</title>
  <style>{PDF_CSS}</style>
</head>
<body>
  <header class="hero">
    <div class="hero-top">
      <span class="brand-badge">فیت‌شو | FITSHO</span>
      <span class="plan-status">{escape(status_label)}</span>
    </div>
    <h1 class="hero-title">برنامه رژیم و تغذیه اختصاصی</h1>
    <div class="hero-meta">
      <span>دوره: {_fa_number(len(plan.days))} روزه</span>
      <span>میانگین کالری روزانه: {_fa_number(avg_cal)} کیلوکالری</span>
      <span>تاریخ شروع: {escape(plan.start_date.isoformat())}</span>
    </div>
  </header>
  {days_html}
</body>
</html>"""


def render_nutrition_plan_pdf(plan: WeeklyPlanResponse) -> bytes:
    html = build_nutrition_plan_html(plan)
    content = HTML(string=html).write_pdf()
    if not isinstance(content, bytes):
        raise RuntimeError("WeasyPrint did not return PDF bytes")
    return content
