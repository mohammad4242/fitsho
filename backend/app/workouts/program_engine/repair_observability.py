"""Exact, bounded observability for post-construction repair operations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class RepairObservability:
    events: tuple[str, ...]
    structural_events: tuple[str, ...]
    workload_events: tuple[str, ...]
    scheduling_events: tuple[str, ...]
    actual_substitution_events: tuple[str, ...]

    @property
    def structural_repair_burden(self) -> int:
        return len(self.structural_events)

    @property
    def workload_repair_burden(self) -> int:
        return len(self.workload_events)

    @property
    def scheduling_repair_burden(self) -> int:
        return len(self.scheduling_events)

    @property
    def total_repair_burden(self) -> int:
        return len(self.events)

    @property
    def actual_substitution_count(self) -> int:
        return len(self.actual_substitution_events)

    def as_mapping(self) -> dict[str, object]:
        return {
            "events": self.events,
            "structural": self.structural_repair_burden,
            "workload": self.workload_repair_burden,
            "scheduling": self.scheduling_repair_burden,
            "total": self.total_repair_burden,
            "actual_substitution_count": self.actual_substitution_count,
        }


_STRUCTURAL_CODES = frozenset(
    {
        "DURATION_PLANNED_REDUCED_EXERCISE_COUNT",
        "MAIN_EXERCISE_TRIMMED_FOR_COUNT",
        "RECOVERY_APPLIED_REQUIRED_SLOT_RELAXATION",
        "SEMANTIC_NEAR_DUPLICATE_REJECTED",
        "SESSION_TRIMMED_FOR_TIME_LIMIT",
        "TEMPLATE_ACCESSORY_TRIMMED_FOR_TIME_LIMIT",
        "TEMPLATE_MAIN_COUNT_CAPPED_FOR_DURATION",
        "TEMPLATE_SEMANTIC_DUPLICATE_OMITTED",
        "TEMPLATE_SUPPLEMENTAL_TRIMMED_FOR_CAPACITY",
    }
)

_WORKLOAD_CODES = frozenset(
    {
        "ACCESSORY_REST_REDUCED_FOR_DURATION",
        "PRIORITY_VOLUME_REDISTRIBUTED",
        "SAFE_TEMPLATE_DROP_SET_APPLIED",
        "VOLUME_CAPPED_FOR_PREVIOUS_EFFECTIVE_VOLUME",
        "VOLUME_CAPPED_FOR_PREVIOUS_VOLUME",
        "VOLUME_CAPPED_FOR_SPLIT_FREQUENCY",
        "VOLUME_REDUCED_FOR_DURATION_CAPACITY",
        "VOLUME_REDUCED_FOR_RECOVERY",
        "VOLUME_REDUCED_FOR_TIME_LIMIT",
        "VOLUME_REPAIR_ADDED_EXERCISE_FOR_MINIMUM_COVERAGE",
        "VOLUME_REPAIR_ADDED_SET_FOR_DIRECT_MINIMUM",
        "VOLUME_REPAIR_ADDED_SET_FOR_EFFECTIVE_TARGET",
        "VOLUME_REPAIR_REDISTRIBUTED_SET_FOR_MINIMUM_COVERAGE",
        "VOLUME_REPAIR_REDISTRIBUTED_SET_FROM_SURPLUS",
        "VOLUME_REPAIR_REDISTRIBUTED_SET_TO_DIRECT_MINIMUM",
        "VOLUME_REPAIR_REDUCED_SET",
        "VOLUME_REPAIR_REDUCED_SET_FOR_EXERCISE_CAP",
        "VOLUME_REPAIR_REMOVED_REDUNDANT_EXERCISE",
        "VOLUME_REPAIR_SOFT_TARGET_REDUCED",
    }
)

_SCHEDULING_CODES = frozenset(
    {
        "DURATION_REPAIR_PRIMARY_BLOCK_EXTENDED",
        "RECOVERY_OPTIONAL_ISOLATION_REDISTRIBUTED",
        "RECOVERY_WEEKDAYS_REARRANGED_FOR_DIRECT_MUSCLE_OVERLAP",
        "RECOVERY_WEEKDAYS_REARRANGED_FOR_EXPOSURE_LOAD",
        "SAFE_SUPERSET_APPLIED_FOR_DURATION",
        "SESSION_DURATION_REPAIR_APPLIED",
        "SUPPLEMENTAL_WORK_TRIMMED_FOR_DURATION",
    }
)

_STAGE_CODES: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {
        "construction_recovery": MappingProxyType(
            {
                code: "scheduling"
                for code in (
                    "RECOVERY_APPLIED_REQUIRED_SLOT_RELAXATION",
                    "RECOVERY_OPTIONAL_ISOLATION_REDISTRIBUTED",
                    "RECOVERY_WEEKDAYS_REARRANGED_FOR_DIRECT_MUSCLE_OVERLAP",
                    "RECOVERY_WEEKDAYS_REARRANGED_FOR_EXPOSURE_LOAD",
                )
            }
        ),
        "duration_repair": MappingProxyType(
            {
                **{code: "workload" for code in ("ACCESSORY_REST_REDUCED_FOR_DURATION",)},
                **{
                    code: "scheduling"
                    for code in (
                        "DURATION_REPAIR_PRIMARY_BLOCK_EXTENDED",
                        "SAFE_SUPERSET_APPLIED_FOR_DURATION",
                        "SESSION_DURATION_REPAIR_APPLIED",
                        "SUPPLEMENTAL_WORK_TRIMMED_FOR_DURATION",
                    )
                },
            }
        ),
        "recovery_repair": MappingProxyType(
            {
                code: "scheduling"
                for code in (
                    "RECOVERY_OPTIONAL_ISOLATION_REDISTRIBUTED",
                    "RECOVERY_WEEKDAYS_REARRANGED_FOR_DIRECT_MUSCLE_OVERLAP",
                    "RECOVERY_WEEKDAYS_REARRANGED_FOR_EXPOSURE_LOAD",
                )
            }
        ),
        "session_duration": MappingProxyType(
            {
                **{
                    code: "structural"
                    for code in (
                        "DURATION_PLANNED_REDUCED_EXERCISE_COUNT",
                        "MAIN_EXERCISE_TRIMMED_FOR_COUNT",
                        "SESSION_TRIMMED_FOR_TIME_LIMIT",
                    )
                },
                **{
                    code: "workload"
                    for code in (
                        "ACCESSORY_REST_REDUCED_FOR_DURATION",
                        "VOLUME_CAPPED_FOR_PREVIOUS_EFFECTIVE_VOLUME",
                        "VOLUME_CAPPED_FOR_PREVIOUS_VOLUME",
                        "VOLUME_CAPPED_FOR_SPLIT_FREQUENCY",
                        "VOLUME_REDUCED_FOR_DURATION_CAPACITY",
                        "VOLUME_REDUCED_FOR_RECOVERY",
                        "VOLUME_REDUCED_FOR_TIME_LIMIT",
                    )
                },
                **{
                    code: "scheduling"
                    for code in (
                        "DURATION_REPAIR_PRIMARY_BLOCK_EXTENDED",
                        "SAFE_SUPERSET_APPLIED_FOR_DURATION",
                        "SESSION_DURATION_REPAIR_APPLIED",
                        "SUPPLEMENTAL_WORK_TRIMMED_FOR_DURATION",
                    )
                },
            }
        ),
        "template_adaptation": MappingProxyType(
            {
                **{
                    code: "structural"
                    for code in (
                        "TEMPLATE_ACCESSORY_TRIMMED_FOR_TIME_LIMIT",
                        "TEMPLATE_MAIN_COUNT_CAPPED_FOR_DURATION",
                        "TEMPLATE_SEMANTIC_DUPLICATE_OMITTED",
                        "TEMPLATE_SUPPLEMENTAL_TRIMMED_FOR_CAPACITY",
                    )
                },
                "SAFE_TEMPLATE_DROP_SET_APPLIED": "workload",
            }
        ),
        "volume": MappingProxyType(
            {
                code: "workload"
                for code in (
                    "VOLUME_CAPPED_FOR_PREVIOUS_EFFECTIVE_VOLUME",
                    "VOLUME_CAPPED_FOR_PREVIOUS_VOLUME",
                    "VOLUME_CAPPED_FOR_SPLIT_FREQUENCY",
                    "VOLUME_REDUCED_FOR_DURATION_CAPACITY",
                    "VOLUME_REDUCED_FOR_RECOVERY",
                    "VOLUME_REDUCED_FOR_TIME_LIMIT",
                )
            }
        ),
        "volume_repair": MappingProxyType(
            {
                **{
                    code: "workload"
                    for code in (
                        "PRIORITY_VOLUME_REDISTRIBUTED",
                        "VOLUME_REPAIR_ADDED_EXERCISE_FOR_MINIMUM_COVERAGE",
                        "VOLUME_REPAIR_ADDED_SET_FOR_DIRECT_MINIMUM",
                        "VOLUME_REPAIR_ADDED_SET_FOR_EFFECTIVE_TARGET",
                        "VOLUME_REPAIR_REDISTRIBUTED_SET_FOR_MINIMUM_COVERAGE",
                        "VOLUME_REPAIR_REDISTRIBUTED_SET_FROM_SURPLUS",
                        "VOLUME_REPAIR_REDISTRIBUTED_SET_TO_DIRECT_MINIMUM",
                        "VOLUME_REPAIR_REDUCED_SET",
                        "VOLUME_REPAIR_REDUCED_SET_FOR_EXERCISE_CAP",
                        "VOLUME_REPAIR_REMOVED_REDUNDANT_EXERCISE",
                        "VOLUME_REPAIR_SOFT_TARGET_REDUCED",
                    )
                },
            }
        ),
    }
)


def collect_repair_observability(
    trace: Sequence[Mapping[str, object]],
) -> RepairObservability:
    events: list[str] = []
    structural: list[str] = []
    workload: list[str] = []
    scheduling: list[str] = []
    substitutions: list[str] = []

    for trace_index, entry in enumerate(trace):
        stage = entry.get("stage")
        if not isinstance(stage, str):
            continue
        allowed_codes = _STAGE_CODES.get(stage, {})
        if stage == "template_adaptation":
            _collect_operations(
                entry.get("substitutions"),
                code="TEMPLATE_SAFE_SUBSTITUTION_APPLIED",
                stage=stage,
                trace_index=trace_index,
                target=events,
                category_target=structural,
                substitution_target=substitutions,
            )
            _collect_operations(
                entry.get("prescription_changes"),
                code="TEMPLATE_PRESCRIPTION_ADAPTED",
                stage=stage,
                trace_index=trace_index,
                target=events,
                category_target=workload,
            )

        per_session_evidence = entry.get("per_session_evidence")
        if isinstance(per_session_evidence, (tuple, list)):
            for evidence_index, evidence in enumerate(per_session_evidence):
                if not isinstance(evidence, Mapping):
                    continue
                _collect_reason_values(
                    evidence.get("reason_codes"),
                    stage=stage,
                    trace_index=trace_index,
                    field=f"session:{evidence_index}",
                    allowed_codes=allowed_codes,
                    events=events,
                    structural=structural,
                    workload=workload,
                    scheduling=scheduling,
                )

        if stage == "session_duration" and isinstance(per_session_evidence, (tuple, list)):
            continue
        for field in ("reason_codes", "reasons"):
            _collect_reason_values(
                entry.get(field),
                stage=stage,
                trace_index=trace_index,
                field=field,
                allowed_codes=allowed_codes,
                events=events,
                structural=structural,
                workload=workload,
                scheduling=scheduling,
            )

    return RepairObservability(
        events=tuple(events),
        structural_events=tuple(structural),
        workload_events=tuple(workload),
        scheduling_events=tuple(scheduling),
        actual_substitution_events=tuple(substitutions),
    )


def collect_repair_events(trace: Sequence[Mapping[str, object]]) -> tuple[str, ...]:
    """Return the exact event tokens used by candidate-survival evidence."""

    return collect_repair_observability(trace).events


def _collect_reason_values(
    value: object,
    *,
    stage: str,
    trace_index: int,
    field: str,
    allowed_codes: Mapping[str, str],
    events: list[str],
    structural: list[str],
    workload: list[str],
    scheduling: list[str],
) -> None:
    if not isinstance(value, (tuple, list, set, frozenset)):
        return
    for operation_index, code in enumerate(value):
        if not isinstance(code, str):
            continue
        category = allowed_codes.get(code)
        if category is None:
            continue
        token = f"{code}@{stage}:{trace_index}:{field}:operation:{operation_index}"
        events.append(token)
        _append_category(category, token, structural, workload, scheduling)


def _collect_operations(
    value: object,
    *,
    code: str,
    stage: str,
    trace_index: int,
    target: list[str],
    category_target: list[str],
    substitution_target: list[str] | None = None,
) -> None:
    if not isinstance(value, (tuple, list)):
        return
    for operation_index, operation in enumerate(value):
        day = operation.get("day_index") if isinstance(operation, Mapping) else None
        day_suffix = f":day:{day}" if isinstance(day, int) else ""
        token = f"{code}@{stage}:{trace_index}:operation:{operation_index}{day_suffix}"
        target.append(token)
        category_target.append(token)
        if substitution_target is not None:
            substitution_target.append(token)


def _append_category(
    category: str,
    token: str,
    structural: list[str],
    workload: list[str],
    scheduling: list[str],
) -> None:
    if category == "structural":
        structural.append(token)
    elif category == "workload":
        workload.append(token)
    elif category == "scheduling":
        scheduling.append(token)
