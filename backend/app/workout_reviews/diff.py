from __future__ import annotations

from typing import cast
from uuid import UUID

from app.workouts.models import WorkoutPlan, WorkoutPlanExercise

COACH_DIFF_SCHEMA_VERSION = "1.0"

_CHANGE_ORDER = {
    "exercise_added": 0,
    "exercise_removed": 1,
    "exercise_reordered": 2,
    "exercise_changed": 3,
    "sets_changed": 4,
    "reps_range_changed": 5,
    "rir_changed": 6,
    "rest_changed": 7,
    "notes_changed": 8,
}


def build_coach_difference_summary(
    source: WorkoutPlan,
    approved: WorkoutPlan,
    *,
    review_id: UUID,
    coach_id: UUID,
    previous_active_plan_id: UUID | None,
) -> dict[str, object]:
    provenance = {
        "source_plan_id": str(source.id),
        "review_id": str(review_id),
        "approved_plan_id": str(approved.id),
        "coach_id": str(coach_id),
    }
    return {
        "schema_version": COACH_DIFF_SCHEMA_VERSION,
        "source_plan_id": str(source.id),
        "review_id": str(review_id),
        "approved_plan_id": str(approved.id),
        "reviewed_by_coach_id": str(coach_id),
        "reviewed_by_coach": True,
        "previous_active_plan_id": (
            str(previous_active_plan_id) if previous_active_plan_id is not None else None
        ),
        "coach_diff": build_coach_diff(source, approved, provenance=provenance),
    }


def build_coach_diff(
    source: WorkoutPlan,
    approved: WorkoutPlan,
    *,
    provenance: dict[str, str],
) -> list[dict[str, object]]:
    source_days = {day.day_number: day for day in source.days}
    approved_days = {day.day_number: day for day in approved.days}
    entries: list[dict[str, object]] = []

    for day_number in sorted(set(source_days) | set(approved_days)):
        source_day = source_days.get(day_number)
        approved_day = approved_days.get(day_number)
        source_items = (
            {item.order_index: item for item in source_day.exercises}
            if source_day is not None
            else {}
        )
        approved_items = (
            {item.order_index: item for item in approved_day.exercises}
            if approved_day is not None
            else {}
        )
        if _has_same_exercise_set(source_items, approved_items):
            if _has_reordered_exercises(source_items, approved_items):
                _append_reorder_entries(
                    entries, day_number, source_items, approved_items, provenance
                )
            for exercise_id in sorted(
                {item.exercise_id for item in source_items.values()}, key=str
            ):
                source_item = next(
                    item for item in source_items.values() if item.exercise_id == exercise_id
                )
                approved_item = next(
                    item for item in approved_items.values() if item.exercise_id == exercise_id
                )
                _append_field_entries(
                    entries,
                    day_number,
                    approved_item.order_index,
                    source_item,
                    approved_item,
                    provenance,
                )
            continue
        _append_reorder_entries(entries, day_number, source_items, approved_items, provenance)

        for order_index in sorted(set(source_items) | set(approved_items)):
            source_slot = source_items.get(order_index)
            approved_slot = approved_items.get(order_index)
            if source_slot is None:
                entries.append(
                    _entry(
                        "exercise_added",
                        day_number,
                        order_index,
                        generated=None,
                        approved=_item_snapshot(approved_slot),
                        source_item=None,
                        approved_item=approved_slot,
                        provenance=provenance,
                    )
                )
                continue
            if approved_slot is None:
                entries.append(
                    _entry(
                        "exercise_removed",
                        day_number,
                        order_index,
                        generated=_item_snapshot(source_slot),
                        approved=None,
                        source_item=source_slot,
                        approved_item=None,
                        provenance=provenance,
                    )
                )
                continue
            _append_field_entries(
                entries,
                day_number,
                order_index,
                source_slot,
                approved_slot,
                provenance,
            )

    return sorted(entries, key=_entry_sort_key)


def _has_same_exercise_set(
    source_items: dict[int, WorkoutPlanExercise],
    approved_items: dict[int, WorkoutPlanExercise],
) -> bool:
    source_ids = [item.exercise_id for item in source_items.values()]
    approved_ids = [item.exercise_id for item in approved_items.values()]
    return len(source_ids) == len(set(source_ids)) and set(source_ids) == set(approved_ids)


def _has_reordered_exercises(
    source_items: dict[int, WorkoutPlanExercise],
    approved_items: dict[int, WorkoutPlanExercise],
) -> bool:
    source_orders = {item.exercise_id: order for order, item in source_items.items()}
    approved_orders = {item.exercise_id: order for order, item in approved_items.items()}
    return any(source_orders[item_id] != approved_orders[item_id] for item_id in source_orders)


def _append_reorder_entries(
    entries: list[dict[str, object]],
    day_number: int,
    source_items: dict[int, WorkoutPlanExercise],
    approved_items: dict[int, WorkoutPlanExercise],
    provenance: dict[str, str],
) -> None:
    source_orders = {item.exercise_id: order for order, item in source_items.items()}
    approved_orders = {item.exercise_id: order for order, item in approved_items.items()}
    for exercise_id in sorted(set(source_orders) & set(approved_orders), key=str):
        source_order = source_orders[exercise_id]
        approved_order = approved_orders[exercise_id]
        if source_order == approved_order:
            continue
        entries.append(
            {
                "change_type": "exercise_reordered",
                "day_number": day_number,
                "order_index": approved_order,
                "generated": source_order,
                "approved": approved_order,
                "generated_order_index": source_order,
                "approved_order_index": approved_order,
                "generated_exercise_id": str(exercise_id),
                "approved_exercise_id": str(exercise_id),
                "provenance": dict(provenance),
            }
        )


def _append_field_entries(
    entries: list[dict[str, object]],
    day_number: int,
    order_index: int,
    source_item: WorkoutPlanExercise,
    approved_item: WorkoutPlanExercise,
    provenance: dict[str, str],
) -> None:
    common = {
        "day_number": day_number,
        "order_index": order_index,
        "generated_exercise_id": str(source_item.exercise_id),
        "approved_exercise_id": str(approved_item.exercise_id),
        "provenance": dict(provenance),
    }
    if source_item.exercise_id != approved_item.exercise_id:
        entries.append(
            {
                **common,
                "change_type": "exercise_changed",
                "generated": str(source_item.exercise_id),
                "approved": str(approved_item.exercise_id),
            }
        )
    if source_item.sets != approved_item.sets:
        entries.append(
            {
                **common,
                "change_type": "sets_changed",
                "generated": source_item.sets,
                "approved": approved_item.sets,
            }
        )
    if (source_item.reps_min, source_item.reps_max) != (
        approved_item.reps_min,
        approved_item.reps_max,
    ):
        entries.append(
            {
                **common,
                "change_type": "reps_range_changed",
                "generated": {"min": source_item.reps_min, "max": source_item.reps_max},
                "approved": {"min": approved_item.reps_min, "max": approved_item.reps_max},
            }
        )
    if source_item.rir != approved_item.rir:
        entries.append(
            {
                **common,
                "change_type": "rir_changed",
                "generated": source_item.rir,
                "approved": approved_item.rir,
            }
        )
    if source_item.rest_seconds != approved_item.rest_seconds:
        entries.append(
            {
                **common,
                "change_type": "rest_changed",
                "generated": source_item.rest_seconds,
                "approved": approved_item.rest_seconds,
            }
        )
    source_notes = {"en": source_item.notes_en, "fa": source_item.notes_fa}
    approved_notes = {"en": approved_item.notes_en, "fa": approved_item.notes_fa}
    if source_notes != approved_notes:
        entries.append(
            {
                **common,
                "change_type": "notes_changed",
                "generated": source_notes,
                "approved": approved_notes,
            }
        )


def _entry(
    change_type: str,
    day_number: int,
    order_index: int,
    *,
    generated: object,
    approved: object,
    source_item: WorkoutPlanExercise | None,
    approved_item: WorkoutPlanExercise | None,
    provenance: dict[str, str],
) -> dict[str, object]:
    return {
        "change_type": change_type,
        "day_number": day_number,
        "order_index": order_index,
        "generated": generated,
        "approved": approved,
        "generated_exercise_id": str(source_item.exercise_id) if source_item else None,
        "approved_exercise_id": str(approved_item.exercise_id) if approved_item else None,
        "provenance": dict(provenance),
    }


def _item_snapshot(item: WorkoutPlanExercise | None) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "exercise_id": str(item.exercise_id),
        "order_index": item.order_index,
        "sets": item.sets,
        "reps_min": item.reps_min,
        "reps_max": item.reps_max,
        "rir": item.rir,
        "rest_seconds": item.rest_seconds,
        "notes_en": item.notes_en,
        "notes_fa": item.notes_fa,
    }


def _entry_sort_key(entry: dict[str, object]) -> tuple[int, int, int, str]:
    change_type = str(entry["change_type"])
    return (
        cast(int, entry["day_number"]),
        cast(int, entry["order_index"]),
        _CHANGE_ORDER[change_type],
        change_type,
    )
