from datetime import UTC, datetime
from uuid import UUID

from app.workouts.enums import WorkoutPlanStatus
from app.workouts.pdf import build_workout_plan_html, render_workout_plan_pdf
from app.workouts.schemas import (
    WorkoutDayResponse,
    WorkoutPlanCoachReviewResponse,
    WorkoutPlanExerciseResponse,
    WorkoutPlanResponse,
)


def _plan_response() -> WorkoutPlanResponse:
    return WorkoutPlanResponse(
        id=UUID("018f0000-0000-7000-8000-000000000001"),
        status=WorkoutPlanStatus.ACTIVE,
        created_at=datetime(2026, 8, 14, tzinfo=UTC),
        activated_at=datetime(2026, 8, 14, tzinfo=UTC),
        plan_duration_weeks=4,
        is_stale=False,
        days=[
            WorkoutDayResponse(
                day_number=1,
                title_en="Upper body",
                title_fa="بالاتنه",
                estimated_duration_minutes=45,
                ai_coach_explanation_fa="توضیح روز",
                exercises=[
                    WorkoutPlanExerciseResponse.model_validate(
                        {
                            "order_index": 1,
                            "sets": 3,
                            "reps_min": 8,
                            "reps_max": 12,
                            "rest_seconds": 90,
                            "rir": 2,
                            "estimated_minutes": 8,
                            "notes_en": "Move with control.",
                            "notes_fa": "کنترل‌شده حرکت کن.",
                            "exercise": {
                                "id": "018f0000-0000-7000-8000-000000000002",
                                "slug": "dumbbell-bench-press",
                                "name_en": "Dumbbell Bench Press",
                                "name_fa": "پرس سینه دمبل",
                                "body_region": "upper_body",
                                "primary_muscle": "chest",
                                "muscle_focus": "mid_chest",
                                "labels": [],
                                "secondary_muscles": ["triceps"],
                                "equipment": ["dumbbell", "bench"],
                                "difficulty": "beginner",
                                "media_path": "/media/bench.gif",
                                "media_type": "gif",
                            },
                            "alternatives": [],
                            "load_guidance": "وزنه را تدریجی افزایش بده.",
                            "progression_rule": "double_progression",
                        }
                    )
                ],
            )
        ],
        ai_coach_program_explanation_fa="توضیح برنامه",
        coach_review=WorkoutPlanCoachReviewResponse(
            state="coach_approved",
            coach_display_name="مربی سارا",
            coach_note="یادداشت مربی",
            approved_at=datetime(2026, 8, 14, tzinfo=UTC),
        ),
    )


def test_html_contains_persian_plan_details_and_rtl_layout() -> None:
    html = build_workout_plan_html(_plan_response())

    assert 'lang="fa" dir="rtl"' in html
    assert "برنامه تمرینی من" in html
    assert "بالاتنه" in html
    assert "پرس سینه دمبل" in html
    assert "۳ ست" in html
    assert "۸ تا ۱۲ تکرار" in html
    assert "۹۰ ثانیه استراحت" in html


def test_html_uses_vazirmatn_and_numbers_exercises_per_day() -> None:
    plan = _plan_response()
    second_exercise = plan.days[0].exercises[0].model_copy(
        deep=True,
        update={"order_index": 2},
    )
    second_exercise.exercise.name_fa = "قایقی سیم‌کش"
    plan.days[0].exercises.append(second_exercise)
    second_day = plan.days[0].model_copy(
        deep=True,
        update={"day_number": 2, "title_fa": "پایین‌تنه"},
    )
    second_day.exercises = [second_day.exercises[0]]
    plan.days.append(second_day)

    html = build_workout_plan_html(plan)

    assert 'font-family: "Vazirmatn", "DejaVu Sans", sans-serif' in html
    assert html.count('<span class="exercise-number" dir="ltr">۱</span>') == 2
    assert html.count('<span class="exercise-number" dir="ltr">۲</span>') == 1
    assert html.count('<span class="exercise-arrow">←</span>') == 3
    assert html.index("۱</span>") < html.index("۲</span>")


def test_html_keeps_exercise_number_beside_name_in_rtl_layout() -> None:
    html = build_workout_plan_html(_plan_response())

    assert (
        'class="exercise-number" dir="ltr">۱</span> '
        '<span class="exercise-arrow">←</span> پرس سینه دمبل</h3>' in html
    )
    assert "display: grid" not in html
    assert ".day { break-inside: avoid" not in html


def test_html_does_not_repeat_day_label_from_generated_title() -> None:
    plan = _plan_response()
    plan.days[0].title_fa = "روز 1: سینه + پشت بازو"

    html = build_workout_plan_html(plan)

    assert "روز ۱: روز ۱:" not in html
    assert "<h2>روز ۱: سینه + پشت بازو</h2>" in html


def test_html_keeps_notes_but_omits_duration_and_progression_details() -> None:
    html = build_workout_plan_html(_plan_response())

    assert "۴۵ دقیقه" not in html
    assert "راهنمای وزنه" not in html
    assert "وزنه را تدریجی افزایش بده." not in html
    assert "روش پیشرفت" not in html
    assert "double_progression" not in html
    assert "کنترل‌شده حرکت کن." in html
    assert "توضیح روز" in html
    assert "توضیح برنامه" in html
    assert "یادداشت مربی" in html


def test_html_escapes_persisted_text() -> None:
    plan = _plan_response()
    plan.days[0].exercises[0].notes_fa = "<script>ناامن</script>"

    html = build_workout_plan_html(plan)

    assert "<script>" not in html
    assert "&lt;script&gt;ناامن&lt;/script&gt;" in html


def test_renderer_returns_pdf_bytes() -> None:
    assert render_workout_plan_pdf(_plan_response()).startswith(b"%PDF-")
