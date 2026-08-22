from __future__ import annotations

from collections.abc import Sequence

from app.workout_reviews.schemas import (
    CoachTemplateSelectionResponse,
    CoachTemplateSelectionScoreResponse,
)

_SCORE_KEYS = ("priority", "body_analysis", "goal", "sex", "fallback")
_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_EXPERIENCE_FA = {
    "first_month": "ماه اول",
    "beginner": "مبتدی",
    "intermediate": "متوسط",
    "advanced": "پیشرفته",
}


def build_coach_template_selection(
    decision_trace: object,
) -> CoachTemplateSelectionResponse | None:
    selection = _selection_entry(decision_trace)
    if selection is None:
        return None
    requested_days = _integer(selection.get("requested_days"))
    experience_level = selection.get("experience_level")
    selected = selection.get("selected")
    candidates = selection.get("candidates")
    if (
        requested_days is None
        or not isinstance(experience_level, str)
        or not isinstance(selected, str)
        or not isinstance(candidates, Sequence)
        or isinstance(candidates, (str, bytes))
    ):
        return None
    candidate = next(
        (
            item
            for item in candidates
            if isinstance(item, dict) and item.get("slug") == selected
        ),
        None,
    )
    if candidate is None:
        return None
    score = _score(candidate.get("score"))
    reason_codes = _reason_codes(candidate.get("reason_codes"))
    if score is None or reason_codes is None:
        return None
    explanation_fa, explanation_en = _explanations(
        requested_days,
        experience_level,
        score,
        reason_codes,
    )
    return CoachTemplateSelectionResponse(
        selected_template=selected,
        explanation_fa=explanation_fa,
        explanation_en=explanation_en,
        score=score,
    )


def _selection_entry(decision_trace: object) -> dict[str, object] | None:
    if not isinstance(decision_trace, Sequence) or isinstance(decision_trace, (str, bytes)):
        return None
    return next(
        (
            item
            for item in decision_trace
            if isinstance(item, dict) and item.get("stage") == "template_selection"
        ),
        None,
    )


def _score(value: object) -> CoachTemplateSelectionScoreResponse | None:
    if not isinstance(value, dict):
        return None
    components = tuple(_integer(value.get(key)) for key in _SCORE_KEYS)
    total = _integer(value.get("total"))
    if total is None or any(component is None for component in components):
        return None
    priority, body_analysis, goal, sex, fallback = components
    if (
        priority is None
        or body_analysis is None
        or goal is None
        or sex is None
        or fallback is None
    ):
        return None
    if total != priority + body_analysis + goal + sex + fallback:
        return None
    return CoachTemplateSelectionScoreResponse(
        priority=priority,
        body_analysis=body_analysis,
        goal=goal,
        sex=sex,
        fallback=fallback,
        total=total,
    )


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _reason_codes(value: object) -> frozenset[str] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    return frozenset(value)


def _explanations(
    requested_days: int,
    experience_level: str,
    score: CoachTemplateSelectionScoreResponse,
    reason_codes: frozenset[str],
) -> tuple[str, str]:
    days_fa = str(requested_days).translate(_PERSIAN_DIGITS)
    level_fa = _EXPERIENCE_FA.get(experience_level, experience_level)
    structural_fa = (
        f"این ساختار {days_fa} روزه سطح {level_fa} با تعداد روزهای تمرین مقاومتی "
        "و سطح تجربه کاربر هم‌خوان است."
    )
    structural_en = (
        f"This {requested_days}-day {experience_level.replace('_', ' ')} structure matches "
        "the user's resistance-training frequency and experience level."
    )
    signals = _signals(score, reason_codes)
    if signals:
        main = signals[0]
        main_fa = f"عامل اصلی رتبه‌بندی، {main[2]} بود."
        main_en = f"The main ranking signal was {main[3]}."
        secondary_fa = ""
        secondary_en = ""
        if len(signals) > 1:
            secondary_fa = f" همچنین {signals[1][2]} از این انتخاب پشتیبانی کرد."
            secondary_en = f" {signals[1][3].capitalize()} also supported the selection."
    else:
        main_fa = "هیچ سیگنال شخصی‌سازی، امتیاز بیشتری نسبت به ساختارهای هم‌سطح ایجاد نکرد."
        main_en = "No personalization signal created a higher score among the eligible structures."
        secondary_fa = ""
        secondary_en = ""
    downstream_fa = (
        " حرکت‌ها، حجم تمرین و جزئیات جلسه پس از انتخاب ساختار بر اساس تجهیزات، "
        "محدودیت‌ها و سایر ورودی‌های پروفایل شخصی‌سازی شدند."
    )
    downstream_en = (
        " Exercises, volume, and session details were personalized afterward using equipment, "
        "limitations, and other profile inputs."
    )
    return (
        f"{structural_fa} {main_fa}{secondary_fa}{downstream_fa}",
        f"{structural_en} {main_en}{secondary_en}{downstream_en}",
    )


def _signals(
    score: CoachTemplateSelectionScoreResponse,
    reason_codes: frozenset[str],
) -> list[tuple[int, int, str, str]]:
    signals: list[tuple[int, int, str, str]] = []
    priority = _priority_signal(score.priority, reason_codes)
    body_analysis = _body_analysis_signal(score.body_analysis, reason_codes)
    goal = _goal_signal(score.goal, reason_codes)
    sex = _sex_signal(score.sex, reason_codes)
    fallback = _fallback_signal(score.fallback, reason_codes)
    for order, signal in enumerate((priority, body_analysis, goal, sex, fallback)):
        if signal is not None:
            signals.append((signal[0], order, signal[1], signal[2]))
    return sorted(signals, key=lambda item: (-item[0], item[1]))


def _priority_signal(
    value: int,
    reasons: frozenset[str],
) -> tuple[int, str, str] | None:
    if value <= 0:
        return None
    if "EXPLICIT_PRIORITY_EXACT_MATCH" in reasons:
        return (
            value,
            "هم‌راستایی دقیق با اولویت عضلانی صریح کاربر",
            "an exact match with the user's explicit muscle priority",
        )
    if "EXPLICIT_PRIORITY_REGIONAL_MATCH" in reasons:
        return (
            value,
            "هم‌راستایی ناحیه‌ای با اولویت عضلانی صریح کاربر",
            "a regional match with the user's explicit muscle priority",
        )
    return None


def _body_analysis_signal(
    value: int,
    reasons: frozenset[str],
) -> tuple[int, str, str] | None:
    if value <= 0:
        return None
    if "BODY_ANALYSIS_CLEAR_LAG_MATCH" in reasons:
        return (
            value,
            "هم‌راستایی با عقب‌ماندگی واضح ثبت‌شده در Body Analysis",
            "alignment with a clear lag recorded by Body Analysis",
        )
    if "BODY_ANALYSIS_MILD_LAG_MATCH" in reasons:
        return (
            value,
            "هم‌راستایی با عقب‌ماندگی خفیف ثبت‌شده در Body Analysis",
            "alignment with a mild lag recorded by Body Analysis",
        )
    return None


def _goal_signal(
    value: int,
    reasons: frozenset[str],
) -> tuple[int, str, str] | None:
    if value <= 0:
        return None
    if "GOAL_STRENGTH_BIAS_MATCH" in reasons:
        return (
            value,
            "هم‌راستایی هدف قدرت با ساختار قدرت‌محور قالب",
            "alignment between the strength goal and the template's strength-biased structure",
        )
    if "GOAL_COMPOUND_FOCUS_MATCH" in reasons:
        return (
            value,
            "هم‌راستایی هدف قدرت با تمرکز قالب بر حرکات چندمفصلی",
            "alignment between the strength goal and the template's compound focus",
        )
    if "GOAL_BALANCED_MATCH" in reasons:
        return (
            value,
            "هم‌راستایی هدف کاربر با ساختار متعادل قالب",
            "alignment between the user's goal and the template's balanced structure",
        )
    return None


def _sex_signal(
    value: int,
    reasons: frozenset[str],
) -> tuple[int, str, str] | None:
    if value <= 0:
        return None
    if reasons & {"SEX_PRIOR_GLUTE_MATCH", "SEX_PRIOR_LOWER_MATCH"}:
        return (
            value,
            "یک ترجیح پیش‌فرض کوچک برای تمرکز پایین‌تنه، به‌دلیل نبود اولویت عضلانی صریح",
            "a small default lower-body preference because no explicit muscle priority "
            "was provided",
        )
    if "SEX_PRIOR_UPPER_MATCH" in reasons:
        return (
            value,
            "یک ترجیح پیش‌فرض کوچک برای تمرکز بالاتنه، به‌دلیل نبود اولویت عضلانی صریح",
            "a small default upper-body preference because no explicit muscle priority "
            "was provided",
        )
    return None


def _fallback_signal(
    value: int,
    reasons: frozenset[str],
) -> tuple[int, str, str] | None:
    if value > 0 and "BALANCED_FALLBACK" in reasons:
        return (
            value,
            "اولویت ضعیف ساختار متعادل در نبود سیگنال قوی‌تر",
            "the weak balanced fallback when no stronger signal applied",
        )
    return None
