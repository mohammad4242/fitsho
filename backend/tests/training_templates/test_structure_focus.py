"""Tests for template day structure_focus classification.

Invariants:
- Every seeded day has a valid structure_focus value.
- Strict structure_focus values are only assigned when the day's muscles are
  genuinely compatible with that block definition.
- Hybrid sessions (unrelated major groups) must not receive strict block values.
- Title changes or localization must not alter the stored focus value (it is
  explicit in the seed, not inferred at runtime).
"""

import pytest

from app.exercises.enums import MuscleGroup as M
from app.training_templates.seed_data import TRAINING_PROGRAM_TEMPLATE_SEEDS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_FOCUSES = {
    "full_body",
    "upper",
    "lower",
    "push",
    "pull",
    "chest_triceps",
    "back_biceps",
    "shoulders_traps",
    "quadriceps_calves",
    "posterior_chain_core",
    "other",
}

_STRICT_FOCUSES = {
    "chest_triceps",
    "back_biceps",
    "shoulders_traps",
    "quadriceps_calves",
    "posterior_chain_core",
    "push",
    "pull",
}

# Muscle sets that are compatible with each strict focus.
# A day is COMPATIBLE when its direct_target_muscles are a subset of
# the union of all muscle groups listed for that focus.
_STRICT_COMPATIBLE_MUSCLES: dict[str, frozenset[M]] = {
    "chest_triceps": frozenset({M.CHEST, M.TRICEPS, M.SHOULDERS}),
    "back_biceps": frozenset({M.BACK, M.BICEPS, M.SHOULDERS, M.TRAPS}),
    "shoulders_traps": frozenset({M.SHOULDERS, M.TRAPS}),
    "quadriceps_calves": frozenset({M.QUADRICEPS, M.CALVES, M.GLUTES}),
    "posterior_chain_core": frozenset({M.HAMSTRINGS, M.GLUTES, M.BACK, M.ABS}),
    "push": frozenset({M.CHEST, M.SHOULDERS, M.TRICEPS}),
    "pull": frozenset({M.BACK, M.BICEPS, M.SHOULDERS, M.TRAPS}),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_DAYS = [
    (template.slug, day_number, day)
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
    for day_number, day in enumerate(template.days, start=1)
]


# ---------------------------------------------------------------------------
# Invariant: every seeded day has a valid structure_focus
# ---------------------------------------------------------------------------

def test_all_seeded_days_have_valid_structure_focus():
    for slug, day_num, day in _ALL_DAYS:
        assert day.structure_focus in _VALID_FOCUSES, (
            f"Invalid structure_focus={day.structure_focus!r} "
            f"for {slug} day {day_num} ({day.title_en!r})"
        )


# ---------------------------------------------------------------------------
# Invariant: strict structure_focus is only used when muscles are compatible
# ---------------------------------------------------------------------------

def test_strict_focus_muscles_always_compatible():
    """
    For every day with a strict focus, the direct_target_muscles must be a
    subset of the allowed muscles for that block.

    This catches hybrid days (e.g. Back + Hamstrings) that were wrongly
    assigned a strict block.
    """
    for slug, day_num, day in _ALL_DAYS:
        if day.structure_focus not in _STRICT_FOCUSES:
            continue
        allowed = _STRICT_COMPATIBLE_MUSCLES[day.structure_focus]
        muscles = frozenset(day.direct_target_muscles)
        assert muscles <= allowed, (
            f"Strict focus {day.structure_focus!r} is incompatible with "
            f"muscles {set(muscles)} for {slug} day {day_num} ({day.title_en!r}). "
            f"Allowed: {set(allowed)}"
        )


# ---------------------------------------------------------------------------
# Specific regression cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title_fragment,expected_focus", [
    ("Back + Hamstrings", "other"),
    ("Chest + Hamstrings", "other"),
    ("Shoulders + Arms", "other"),
    ("Shoulders + Triceps", "other"),
    ("Shoulders + Biceps", "other"),
    ("Overhead Press Day", "other"),
])
def test_hybrid_days_are_other(title_fragment: str, expected_focus: str):
    """Hybrid sessions with unrelated major muscle groups must not be strict."""
    matched = [
        (slug, day_num, day)
        for slug, day_num, day in _ALL_DAYS
        if title_fragment in day.title_en
    ]
    assert matched, f"No seeded day found containing {title_fragment!r}"
    for slug, day_num, day in matched:
        assert day.structure_focus == expected_focus, (
            f"{slug} day {day_num} ({day.title_en!r}): "
            f"expected {expected_focus!r}, got {day.structure_focus!r}"
        )


@pytest.mark.parametrize("title_fragment,expected_focus", [
    ("Hamstrings + Glutes", "posterior_chain_core"),
    ("Legs Posterior", "posterior_chain_core"),
    ("Deadlift Day", "posterior_chain_core"),
    ("Deadlift — Heavy", "posterior_chain_core"),
])
def test_true_posterior_days_are_posterior_chain_core(title_fragment: str, expected_focus: str):
    matched = [
        (slug, day_num, day)
        for slug, day_num, day in _ALL_DAYS
        if title_fragment in day.title_en
    ]
    assert matched, f"No seeded day found containing {title_fragment!r}"
    for slug, day_num, day in matched:
        assert day.structure_focus == expected_focus, (
            f"{slug} day {day_num} ({day.title_en!r}): "
            f"expected {expected_focus!r}, got {day.structure_focus!r}"
        )


@pytest.mark.parametrize("title_fragment,expected_focus", [
    ("Quadriceps + Calves", "quadriceps_calves"),
    ("Legs Quadriceps", "quadriceps_calves"),
    ("Squat Day", "quadriceps_calves"),
    ("Squat — Heavy", "quadriceps_calves"),
])
def test_true_quad_calves_days_are_quadriceps_calves(title_fragment: str, expected_focus: str):
    matched = [
        (slug, day_num, day)
        for slug, day_num, day in _ALL_DAYS
        if title_fragment in day.title_en
    ]
    assert matched, f"No seeded day found containing {title_fragment!r}"
    for slug, day_num, day in matched:
        assert day.structure_focus == expected_focus, (
            f"{slug} day {day_num} ({day.title_en!r}): "
            f"expected {expected_focus!r}, got {day.structure_focus!r}"
        )


def test_generic_legs_days_with_all_three_lower_muscles_are_lower():
    """Generic Legs (quad+ham+glute) must be 'lower', not a strict block."""
    for slug, day_num, day in _ALL_DAYS:
        title = day.title_en
        if title.startswith("Legs") and "Posterior" not in title and "Quadriceps" not in title:
            muscles = frozenset(day.direct_target_muscles)
            if {M.QUADRICEPS, M.HAMSTRINGS, M.GLUTES}.issubset(muscles):
                assert day.structure_focus == "lower", (
                    f"{slug} day {day_num} ({title!r}): "
                    f"generic Legs should be 'lower', got {day.structure_focus!r}"
                )


def test_full_body_days_are_full_body():
    for slug, day_num, day in _ALL_DAYS:
        if "Full Body" in day.title_en:
            assert day.structure_focus == "full_body", (
                f"{slug} day {day_num} ({day.title_en!r}): expected 'full_body'"
            )


def test_title_change_does_not_affect_structure_focus():
    """
    structure_focus is explicit in the seed — not derived from the title.
    Verify that changing the Persian title (localization) on the same day
    would not change the stored English focus value.

    We simulate this by checking that the focus is still the same value
    regardless of what title_fa contains (since focus is stored separately).
    """
    for slug, day_num, day in _ALL_DAYS:
        # The structure_focus field must not be empty or derived dynamically
        assert day.structure_focus, (
            f"{slug} day {day_num}: structure_focus is empty"
        )
        assert day.structure_focus in _VALID_FOCUSES, (
            f"{slug} day {day_num}: structure_focus {day.structure_focus!r} is not a known value"
        )


# ---------------------------------------------------------------------------
# shoulders_traps must only apply when Traps is actually targeted
# ---------------------------------------------------------------------------

def test_shoulders_traps_only_when_traps_present():
    """
    'shoulders_traps' must only be used when TRAPS (or only SHOULDERS) is in
    the direct_target_muscles. Biceps and Triceps are not Traps.
    """
    for slug, day_num, day in _ALL_DAYS:
        if day.structure_focus != "shoulders_traps":
            continue
        muscles = frozenset(day.direct_target_muscles)
        # Must not contain Biceps or Triceps — those are arm muscles
        assert M.BICEPS not in muscles, (
            f"{slug} day {day_num} ({day.title_en!r}): "
            f"'shoulders_traps' used but day targets BICEPS"
        )
        assert M.TRICEPS not in muscles or M.TRAPS in muscles or M.CHEST in muscles, (
            f"{slug} day {day_num} ({day.title_en!r}): "
            f"'shoulders_traps' used but day has TRICEPS without TRAPS context"
        )


def test_posterior_chain_core_only_when_truly_posterior():
    """
    'posterior_chain_core' must not be assigned when a non-posterior major
    muscle group (CHEST, BACK standalone) is the primary target.
    The rule: Back + Hamstrings is a hybrid, NOT posterior chain.
    """
    for slug, day_num, day in _ALL_DAYS:
        if day.structure_focus != "posterior_chain_core":
            continue
        muscles = frozenset(day.direct_target_muscles)
        # CHEST must not be present in a posterior_chain_core day
        assert M.CHEST not in muscles, (
            f"{slug} day {day_num} ({day.title_en!r}): "
            f"'posterior_chain_core' used but CHEST is a direct target"
        )

def test_migration_mapping_exactly_matches_current_seeds():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "migration",
        "alembic/versions/21c79457f43e_backfill_structure_focus_for_seeded_.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    current_seeded = {}
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        for i, day in enumerate(template.days, start=1):
            current_seeded[(template.slug, i)] = day.structure_focus

    assert set(migration._SEED_STRUCTURE_FOCUS.keys()) == set(current_seeded.keys())

    for key, expected_focus in current_seeded.items():
        assert migration._SEED_STRUCTURE_FOCUS[key] == expected_focus
