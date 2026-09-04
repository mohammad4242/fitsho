from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.estimate_service import create_estimate
from app.nutrition.models import (
    NutritionConsumptionEntry,
    NutritionDailyCheckIn,
    NutritionMealFeedback,
    NutritionTargetUpdateConsent,
    NutritionWeeklyPlan,
    NutritionWeeklyPlanDay,
)
from app.profile.enums import FitnessGoal
from app.profile.models import BodyMeasurement, UserProfile

ADHERENCE_FORMULA_VERSION = "nutrition-adherence-v1"


class AdherenceError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


def _ratio_score(actual: Decimal, planned: Decimal) -> float | None:
    if planned <= 0:
        return None
    return float(max(Decimal(), Decimal("100") - abs(actual - planned) / planned * 100))


def adherence_history(db: Session, user_id: UUID, start: date, end: date) -> dict[str, object]:
    check_ins = {
        row.entry_date: row
        for row in db.scalars(
            select(NutritionDailyCheckIn).where(
                NutritionDailyCheckIn.user_id == user_id,
                NutritionDailyCheckIn.entry_date.between(start, end),
            )
        )
    }
    entries = db.scalars(
        select(NutritionConsumptionEntry).where(
            NutritionConsumptionEntry.user_id == user_id,
            NutritionConsumptionEntry.entry_date.between(start, end),
        )
    ).all()
    by_date: defaultdict[date, list[NutritionConsumptionEntry]] = defaultdict(list)
    for entry in entries:
        by_date[entry.entry_date].append(entry)
    plan_ids = {row.plan_revision_id for row in check_ins.values() if row.plan_revision_id}
    plans = (
        {
            plan.id: plan
            for plan in db.scalars(
                select(NutritionWeeklyPlan)
                .where(NutritionWeeklyPlan.id.in_(plan_ids))
                .options(
                    selectinload(NutritionWeeklyPlan.days).selectinload(
                        NutritionWeeklyPlanDay.meals
                    )
                )
            ).all()
        }
        if plan_ids
        else {}
    )
    days: list[dict[str, object]] = []
    current = start
    while current <= end:
        check_in = check_ins.get(current)
        day_entries = by_date[current]
        actual: defaultdict[str, Decimal] = defaultdict(Decimal)
        approximate_count = 0
        for entry in day_entries:
            for code, value in entry.nutrients.items():
                actual[code] += Decimal(str(value))
            if entry.confidence.value != "high":
                approximate_count += 1
        plan = (
            plans.get(check_in.plan_revision_id)
            if check_in and check_in.plan_revision_id is not None
            else None
        )
        planned: dict[str, Decimal] = {}
        meal_count = 0
        if plan is not None:
            index = (current - plan.start_date).days % 7
            plan_day = next((row for row in plan.days if row.day_index == index), None)
            if plan_day:
                planned = {
                    code: Decimal(str(value)) for code, value in plan_day.nutrient_totals.items()
                }
                meal_count = len(plan_day.meals)
        sufficient = bool(day_entries) and (bool(planned) or check_in is not None)
        calorie = _ratio_score(actual["energy_kcal"], planned.get("energy_kcal", Decimal()))
        protein = _ratio_score(actual["protein_g"], planned.get("protein_g", Decimal()))
        confirmed_meals = len(
            {entry.planned_meal_id for entry in day_entries if entry.planned_meal_id}
        )
        meal_adherence = confirmed_meals / meal_count * 100 if meal_count else None
        completeness = (
            100.0
            if check_in and check_in.status.value in {"on_plan", "mostly_on_plan"}
            else 70.0
            if day_entries
            else 0.0
        )
        components = [
            value for value in (calorie, protein, meal_adherence, completeness) if value is not None
        ]
        days.append(
            {
                "date": current,
                "status": "sufficient" if sufficient else "insufficient_data",
                "check_in_status": check_in.status.value if check_in else "not_recorded",
                "plan_revision_id": plan.id if plan else None,
                "planned": {code: float(value) for code, value in planned.items()},
                "actual": {code: float(value) for code, value in actual.items()},
                "calorie_adherence": calorie if sufficient else None,
                "protein_adherence": protein if sufficient else None,
                "meal_adherence": meal_adherence if sufficient else None,
                "budget_adherence": None,
                "tracking_completeness": completeness,
                "exact_entry_ratio": (
                    (len(day_entries) - approximate_count) / len(day_entries)
                    if day_entries
                    else None
                ),
                "composite_score": sum(components) / len(components)
                if sufficient and components
                else None,
                "formula_version": ADHERENCE_FORMULA_VERSION,
                "structured_exercise_calories": None,
                "major_deviations": sum(
                    1 for entry in day_entries if entry.source.value == "quick_approximation"
                ),
            }
        )
        current = date.fromordinal(current.toordinal() + 1)
    weights = [
        {"measured_at": row.measured_at, "weight_kg": float(row.weight_kg)}
        for row in db.scalars(
            select(BodyMeasurement)
            .where(
                BodyMeasurement.user_id == user_id,
                BodyMeasurement.measured_at
                >= datetime.combine(start, datetime.min.time(), tzinfo=UTC),
                BodyMeasurement.measured_at
                < datetime.combine(
                    date.fromordinal(end.toordinal() + 1), datetime.min.time(), tzinfo=UTC
                ),
            )
            .order_by(BodyMeasurement.measured_at)
        )
    ]
    return {
        "start": start,
        "end": end,
        "days": days,
        "weight_trend": weights,
        "weight_causality_claimed": False,
        "explanation_codes": ["CONFIDENCE_AWARE", "NO_CAUSAL_WEIGHT_CLAIM"],
    }


def adaptive_preferences(db: Session, user_id: UUID) -> dict[str, object]:
    feedback = db.scalars(
        select(NutritionMealFeedback).where(NutritionMealFeedback.user_id == user_id)
    ).all()
    counts = Counter(row.feedback_type.value for row in feedback)
    return {
        "feedback_counts": dict(counts),
        "avoid_meal_ids": [
            row.meal_id for row in feedback if row.feedback_type.value == "do_not_suggest_again"
        ],
        "disliked_meal_ids": [
            row.meal_id for row in feedback if row.feedback_type.value == "disliked"
        ],
        "prefer_meal_ids": [
            row.meal_id
            for row in feedback
            if row.feedback_type.value in {"liked", "prefer_more_often"}
        ],
        "scientific_targets_changed": False,
    }


def confirm_target_update(
    db: Session,
    user_id: UUID,
    requested_goal: FitnessGoal,
    confirmed: bool,
) -> dict[str, object]:
    if not confirmed:
        raise AdherenceError("TARGET_UPDATE_CONFIRMATION_REQUIRED")
    profile = db.get(UserProfile, user_id)
    if profile is None or profile.fitness_goal is None:
        raise AdherenceError("PROFILE_NOT_FOUND")
    previous = profile.fitness_goal
    profile.fitness_goal = requested_goal
    audit = NutritionTargetUpdateConsent(
        user_id=user_id,
        previous_goal=previous.value,
        requested_goal=requested_goal.value,
        reason_codes=["USER_CONFIRMED_TARGET_CHANGE"],
        confirmed_at=datetime.now(UTC),
    )
    db.add(audit)
    db.commit()
    estimate = create_estimate(db, user_id)
    audit.estimate_id = estimate.id
    db.commit()
    return {
        "previous_goal": previous.value,
        "requested_goal": requested_goal.value,
        "estimate_id": estimate.id,
        "user_confirmed": True,
    }
