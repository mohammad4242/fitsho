from html import escape

from weasyprint import HTML  # type: ignore[import-untyped]

from app.workouts.schemas import WorkoutDayResponse, WorkoutPlanResponse

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

PDF_CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body {
  color: #102622;
  font-family: "Vazirmatn", "DejaVu Sans", sans-serif;
  font-size: 11pt;
  line-height: 1.75;
  direction: rtl;
  text-align: right;
}
h1, h2, h3, p { margin-top: 0; }
h1 { color: #087d6c; font-size: 24pt; margin-bottom: 2mm; }
.plan-meta { color: #4f625e; margin-bottom: 8mm; }
.note {
  background: #eef8f5;
  border-right: 3px solid #14a38b;
  border-radius: 3mm;
  margin: 0 0 4mm;
  padding: 3mm 4mm;
}
.day { margin: 0 0 8mm; }
.day-heading { border-bottom: 1px solid #b8cbc6; margin-bottom: 3mm; padding-bottom: 2mm; }
.day-heading h2 { display: inline; font-size: 16pt; }
.day-heading span { color: #5f716d; margin-right: 3mm; }
.exercise {
  border: 1px solid #d6e2df;
  border-radius: 3mm;
  break-inside: avoid;
  margin: 0 0 3mm;
  padding: 3mm 4mm;
}
.exercise-number {
  color: #087d6c;
  direction: ltr;
  display: inline-block;
  font-weight: bold;
  margin-left: 2mm;
  unicode-bidi: isolate;
}
.exercise h3 { font-size: 12pt; margin-bottom: 1mm; }
.prescription { color: #087d6c; font-weight: bold; margin-bottom: 1mm; }
.instruction { color: #354b46; margin-bottom: 1mm; }
.label { color: #647772; font-weight: bold; }
"""


def _fa_number(value: int) -> str:
    return str(value).translate(_PERSIAN_DIGITS)


def _paragraph(label: str, value: str | None, *, class_name: str = "note") -> str:
    if value is None or not value.strip():
        return ""
    return (
        f'<p class="{class_name}"><span class="label">{escape(label)}:</span> '
        f"{escape(value)}</p>"
    )


def _render_day(day: WorkoutDayResponse) -> str:
    exercises = "".join(
        _render_exercise(
            position=position,
            name=item.exercise.name_fa,
            sets=item.sets,
            reps_min=item.reps_min,
            reps_max=item.reps_max,
            rest_seconds=item.rest_seconds,
            notes=item.notes_fa or item.notes_en,
        )
        for position, item in enumerate(day.exercises, start=1)
    )
    explanation = _paragraph("توضیحات جلسه", day.ai_coach_explanation_fa)
    return (
        '<section class="day">'
        '<div class="day-heading">'
        f"<h2>{escape(_day_title(day))}</h2>"
        "</div>"
        f"{explanation}{exercises}</section>"
    )


def _day_title(day: WorkoutDayResponse) -> str:
    title = day.title_fa.strip()
    label = f"روز {_fa_number(day.day_number)}:"
    for prefix in (f"روز {day.day_number}:", label):
        if title.startswith(prefix):
            title = title[len(prefix) :].lstrip()
            break
    return f"{label} {title}"


def _render_exercise(
    *,
    position: int,
    name: str,
    sets: int,
    reps_min: int,
    reps_max: int,
    rest_seconds: int,
    notes: str | None,
) -> str:
    prescription = (
        f"{_fa_number(sets)} ست · {_fa_number(reps_min)} تا {_fa_number(reps_max)} تکرار · "
        f"{_fa_number(rest_seconds)} ثانیه استراحت"
    )
    note = _paragraph("یادداشت", notes, class_name="instruction")
    return (
        '<article class="exercise">'
        f'<h3><span class="exercise-number" dir="ltr">{_fa_number(position)})</span> '
        f"{escape(name)}</h3>"
        f'<p class="prescription">{prescription}</p>{note}'
        "</article>"
    )


def build_workout_plan_html(plan: WorkoutPlanResponse) -> str:
    program_notes = "".join(
        (
            _paragraph("توضیحات برنامه", plan.ai_coach_program_explanation_fa),
            _paragraph("یادداشت مربی", plan.coach_review.coach_note),
        )
    )
    days = "".join(_render_day(day) for day in plan.days)
    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8"><style>{PDF_CSS}</style></head>
<body>
  <h1>برنامه تمرینی من</h1>
  <p class="plan-meta">دوره {_fa_number(plan.plan_duration_weeks)} هفته‌ای ·
  {_fa_number(len(plan.days))} روز تمرین</p>
  {program_notes}
  {days}
</body>
</html>"""


def render_workout_plan_pdf(plan: WorkoutPlanResponse) -> bytes:
    content = HTML(string=build_workout_plan_html(plan)).write_pdf()
    if not isinstance(content, bytes):
        raise RuntimeError("WeasyPrint did not return PDF bytes")
    return content
