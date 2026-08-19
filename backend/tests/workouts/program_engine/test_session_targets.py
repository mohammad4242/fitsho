from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.session_targets import (
    ENGLISH_MUSCLE_NAMES,
    PERSIAN_MUSCLE_NAMES,
    english_session_title_for_targets,
    persian_session_title_for_targets,
)


def test_every_muscle_group_has_english_and_persian_title_localization() -> None:
    assert set(MuscleGroup) <= set(ENGLISH_MUSCLE_NAMES)
    assert set(MuscleGroup) <= set(PERSIAN_MUSCLE_NAMES)


def test_session_title_falls_back_when_a_localization_is_missing(monkeypatch) -> None:
    monkeypatch.setitem(ENGLISH_MUSCLE_NAMES, MuscleGroup.ABDUCTORS, "Temporary")
    monkeypatch.setitem(PERSIAN_MUSCLE_NAMES, MuscleGroup.ABDUCTORS, "موقت")
    monkeypatch.delitem(ENGLISH_MUSCLE_NAMES, MuscleGroup.ABDUCTORS)
    monkeypatch.delitem(PERSIAN_MUSCLE_NAMES, MuscleGroup.ABDUCTORS)

    assert english_session_title_for_targets(1, (MuscleGroup.ABDUCTORS,)) == "Day 1: Abductors"
    assert persian_session_title_for_targets(1, (MuscleGroup.ABDUCTORS,)) == "روز 1: abductors"
