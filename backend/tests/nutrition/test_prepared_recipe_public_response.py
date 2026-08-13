from app.nutrition.plan_service import _public_prepared_recipe_summary


def _snapshot(status: str) -> dict[str, object]:
    return {
        "verification_status": status,
        "selected_ingredient_grams": {"beef-id": "90", "peas-id": "55"},
        "ingredients": [
            {
                "food_id": "beef-id",
                "grams": "90",
                "cost_irr": "90000",
                "price_reference_id": "private-price-id",
            }
        ],
        "nutrients_per_100g": {
            "energy_kcal": "172.4",
            "protein_g": "14.2",
            "carbohydrate_g": "11.3",
            "total_fat_g": "7.1",
            "fibre_g": "2.4",
            "sodium_mg": "210",
        },
        "cost_irr_per_100g": "48750",
        "provenance": {"source_name": "internal kitchen estimate"},
        "data_gaps": [{"message_fa": "internal gap"}],
        "price_reference_ids": ["private-price-id"],
    }


def test_draft_recipe_public_summary_exposes_only_estimated_nutrition_and_cost() -> None:
    summary = _public_prepared_recipe_summary(_snapshot("draft"))

    assert summary is not None
    body = summary.model_dump()
    assert body == {
        "status": "estimated",
        "nutrients_per_100g": {
            "energy_kcal": 172.4,
            "protein_g": 14.2,
            "carbohydrate_g": 11.3,
            "total_fat_g": 7.1,
            "fibre_g": 2.4,
        },
        "cost_irr_per_100g": 48750.0,
    }
    serialized = str(body)
    assert "beef-id" not in serialized
    assert "private-price-id" not in serialized
    assert "internal kitchen estimate" not in serialized
    assert "internal gap" not in serialized


def test_verified_recipe_public_summary_is_verified_and_simple_food_has_no_summary() -> None:
    verified = _public_prepared_recipe_summary(_snapshot("verified"))

    assert verified is not None
    assert verified.status == "verified"
    assert _public_prepared_recipe_summary(None) is None
