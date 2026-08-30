from dataclasses import replace

from app.workouts.program_engine import engine
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import WorkoutDay
from app.workouts.program_engine.session_duration import DurationRepairResult


def _day(minutes: int) -> WorkoutDay:
    return WorkoutDay(
        day_index=1,
        weekday=0,
        title="Test",
        focus="full_body",
        estimated_duration_minutes=minutes,
        exercises=(),
    )


def test_duration_certification_keeps_a_legitimate_late_repair(monkeypatch) -> None:
    original_day = _day(59)
    repaired_day = replace(original_day, estimated_duration_minutes=60)
    initial = DurationRepairResult(
        days=(original_day,), reasons=("INITIAL_REPAIR",), evidence=()
    )
    certified = DurationRepairResult(
        days=(repaired_day,), reasons=("LATE_REPAIR",), evidence=()
    )
    monkeypatch.setattr(engine, "repair_session_durations", lambda *args, **kwargs: certified)

    result = engine._certify_duration_repair(  # noqa: SLF001
        initial,
        (original_day,),
        object(),
        (),
        RULESET,
        volume=object(),
        session_capacity=object(),
    )

    assert result.days == (repaired_day,)
    assert result.reasons == ("INITIAL_REPAIR", "LATE_REPAIR")
