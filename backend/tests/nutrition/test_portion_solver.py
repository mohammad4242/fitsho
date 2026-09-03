from decimal import Decimal

from app.nutrition.portion_solver import PortionVariable, solve_portions


def _variable(*, maximum: str = "150") -> PortionVariable:
    return PortionVariable(
        key="day-0:main_meal:0:protein-food",
        day_index=0,
        role="main_meal",
        slot_index=0,
        food_id="protein-food",
        grams=Decimal("50"),
        reference_grams=Decimal("50"),
        min_grams=Decimal("20"),
        max_grams=Decimal(maximum),
        nutrients_per_gram=(
            ("energy_kcal", Decimal("4")),
            ("protein_g", Decimal("0.5")),
        ),
        cost_per_gram=Decimal("2"),
    )


def test_bounded_solver_repairs_scale_then_clamp_residual() -> None:
    result = solve_portions(
        variables=(_variable(),),
        initial_totals={"energy_kcal": Decimal("200"), "protein_g": Decimal("25")},
        targets={"energy_kcal": Decimal("400"), "protein_g": Decimal("50")},
        minimums={},
        maximums={},
        upper_limits={},
        increment_g=Decimal("5"),
        maximum_iterations=40,
    )

    assert result.reason_codes == ()
    assert result.grams_by_key == (("day-0:main_meal:0:protein-food", Decimal("100")),)
    assert result.final_totals["energy_kcal"] == Decimal("400")
    assert result.final_totals["protein_g"] == Decimal("50")
    assert result.final_score < result.initial_score
    assert result.actions


def test_bounded_solver_is_deterministic_and_respects_bounds() -> None:
    variables = (_variable(maximum="80"),)
    first = solve_portions(
        variables=variables,
        initial_totals={"energy_kcal": Decimal("200"), "protein_g": Decimal("25")},
        targets={"energy_kcal": Decimal("500")},
        minimums={},
        maximums={},
        upper_limits={},
        increment_g=Decimal("5"),
        maximum_iterations=40,
    )
    second = solve_portions(
        variables=tuple(reversed(variables)),
        initial_totals={"energy_kcal": Decimal("200"), "protein_g": Decimal("25")},
        targets={"energy_kcal": Decimal("500")},
        minimums={},
        maximums={},
        upper_limits={},
        increment_g=Decimal("5"),
        maximum_iterations=40,
    )

    assert first == second
    assert Decimal("20") <= first.grams_by_key[0][1] <= Decimal("80")
    assert "CALORIE_TARGET_UNREACHABLE_WITH_PORTION_BOUNDS" in first.reason_codes


def test_bounded_solver_preserves_upper_limits() -> None:
    variable = PortionVariable(
        **{
            **_variable().__dict__,
            "nutrients_per_gram": (
                ("energy_kcal", Decimal("4")),
                ("protein_g", Decimal("0.5")),
                ("sodium_mg", Decimal("10")),
            ),
        }
    )

    result = solve_portions(
        variables=(variable,),
        initial_totals={
            "energy_kcal": Decimal("200"),
            "protein_g": Decimal("25"),
            "sodium_mg": Decimal("500"),
        },
        targets={"energy_kcal": Decimal("400"), "protein_g": Decimal("50")},
        minimums={},
        maximums={},
        upper_limits={"sodium_mg": Decimal("700")},
        increment_g=Decimal("5"),
        maximum_iterations=40,
    )

    assert result.final_totals["sodium_mg"] <= Decimal("700")
    assert Decimal("20") <= result.grams_by_key[0][1] <= Decimal("70")
