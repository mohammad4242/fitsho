"""Curated meal structures backed only by Food Catalogue slugs."""

from app.nutrition.enums import MealCategory, MealIngredientRole

P = MealIngredientRole.PROTEIN
C = MealIngredientRole.CARBOHYDRATE
F = MealIngredientRole.FAT
FB = MealIngredientRole.FIBRE
M = MealIngredientRole.MICRONUTRIENT_SOURCE


def item(
    slug: str,
    reference: int,
    minimum: int,
    maximum: int,
    role: MealIngredientRole,
    *,
    required: bool = True,
) -> tuple[str, str, str, str, bool, MealIngredientRole]:
    return slug, str(reference), str(minimum), str(maximum), required, role


def recipe_item(
    slug: str, reference: int, minimum: int, maximum: int, *, required: bool = True
) -> tuple[str, str, str, str, bool]:
    return slug, str(reference), str(minimum), str(maximum), required


def ratio(
    numerator_slug: str, denominator_slug: str, minimum: str, maximum: str
) -> tuple[str, str, str, str]:
    return numerator_slug, denominator_slug, minimum, maximum


PREPARED_RECIPE_SEEDS: dict[str, dict[str, object]] = {
    "LU07": {
        "name_fa": "قورمه‌سبزی",
        "name_en": "Ghormeh sabzi",
        "final_cooked_yield_grams": "456.75",
        "ingredients": (
            recipe_item("beef-chuck-stew-meat", 120, 80, 200),
            recipe_item("red-kidney-beans", 40, 25, 70),
            recipe_item("mixed-herbs", 120, 70, 200),
            recipe_item("onion", 30, 15, 60),
            recipe_item("vegetable-oil", 5, 2, 10, required=False),
        ),
        "ratios": (ratio("beef-chuck-stew-meat", "red-kidney-beans", "1.5", "5"),),
        "gap_fa": "وزن نهایی پخته و ترکیب دقیق سبزی قورمه تخمینی است و منبع اندازه‌گیری‌شده ندارد",
        "gap_en": (
            "Final cooked yield and the exact Ghormeh herb blend are estimates "
            "without a measured source"
        ),
    },
    "LU08": {
        "name_fa": "قیمه",
        "name_en": "Gheimeh",
        "final_cooked_yield_grams": "485.75",
        "ingredients": (
            recipe_item("beef-chuck-stew-meat", 120, 80, 200),
            recipe_item("split-peas", 45, 25, 75),
            recipe_item("tomato-paste", 35, 15, 65),
            recipe_item("potato", 100, 50, 180, required=False),
            recipe_item("onion", 30, 15, 60),
            recipe_item("vegetable-oil", 5, 2, 10, required=False),
        ),
        "ratios": (ratio("beef-chuck-stew-meat", "split-peas", "1.5", "4"),),
        "gap_fa": "وزن نهایی پخته تخمینی است و منبع اندازه‌گیری‌شده ندارد",
        "gap_en": "Final cooked yield is an estimate without a measured source",
    },
    "LU11": {
        "name_fa": "آبگوشت",
        "name_en": "Abgoosht",
        "final_cooked_yield_grams": "740",
        "ingredients": (
            recipe_item("lamb", 120, 80, 200),
            recipe_item("chickpeas", 35, 20, 60),
            recipe_item("white-beans", 35, 20, 60),
            recipe_item("potato", 120, 70, 220),
            recipe_item("tomato-paste", 30, 15, 60),
            recipe_item("onion", 30, 15, 60),
        ),
        "ratios": (
            ratio("lamb", "chickpeas", "2", "6"),
            ratio("chickpeas", "white-beans", "0.5", "2"),
        ),
        "gap_fa": "وزن نهایی پخته و مقدار آب باقی‌مانده تخمینی است و منبع اندازه‌گیری‌شده ندارد",
        "gap_en": "Final cooked yield and retained broth are estimates without a measured source",
    },
}


SEED_MEALS: tuple[dict[str, object], ...] = (
    {
        "code": "BF01",
        "category": MealCategory.BREAKFAST,
        "name_fa": "املت گوجه + نان",
        "name_en": "Tomato omelette with bread",
        "items": (
            item("egg", 100, 50, 200, P),
            item("tomato", 120, 60, 220, M),
            item("sangak-bread", 60, 30, 120, C),
            item("vegetable-oil", 5, 2, 10, F, required=False),
        ),
    },
    {
        "code": "BF02",
        "category": MealCategory.BREAKFAST,
        "name_fa": "نیمرو + نان + گوجه",
        "name_en": "Fried eggs with bread and tomato",
        "items": (
            item("egg", 100, 50, 200, P),
            item("sangak-bread", 60, 30, 120, C),
            item("tomato", 80, 40, 150, M),
            item("vegetable-oil", 5, 2, 10, F, required=False),
        ),
    },
    {
        "code": "BF03",
        "category": MealCategory.BREAKFAST,
        "name_fa": "پنیر + گردو + نان + خیار و گوجه",
        "name_en": "Cheese, walnuts, bread, cucumber and tomato",
        "items": (
            item("low-fat-cheese", 50, 30, 90, P),
            item("walnuts", 20, 10, 35, F),
            item("sangak-bread", 60, 30, 120, C),
            item("cucumber", 80, 40, 150, FB),
            item("tomato", 80, 40, 150, M),
        ),
    },
    {
        "code": "BF04",
        "category": MealCategory.BREAKFAST,
        "name_fa": "پنیر + کره + نان + خیار و گوجه",
        "name_en": "Cheese, butter, bread, cucumber and tomato",
        "items": (
            item("low-fat-cheese", 50, 30, 90, P),
            item("butter", 10, 5, 20, F),
            item("sangak-bread", 60, 30, 120, C),
            item("cucumber", 80, 40, 150, FB),
            item("tomato", 80, 40, 150, M),
        ),
    },
    {
        "code": "BF05",
        "category": MealCategory.BREAKFAST,
        "name_fa": "تخم‌مرغ آب‌پز + نان + خیار و گوجه",
        "name_en": "Boiled eggs with bread, cucumber and tomato",
        "items": (
            item("egg", 100, 50, 200, P),
            item("sangak-bread", 60, 30, 120, C),
            item("cucumber", 80, 40, 150, FB),
            item("tomato", 80, 40, 150, M),
        ),
    },
    {
        "code": "BF06",
        "category": MealCategory.BREAKFAST,
        "name_fa": "عدسی + نان",
        "name_en": "Lentils with bread",
        "items": (
            item("lentils", 70, 40, 110, P),
            item("sangak-bread", 60, 30, 120, C),
            item("onion", 20, 10, 40, M, required=False),
        ),
    },
    {
        "code": "BF07",
        "category": MealCategory.BREAKFAST,
        "name_fa": "کره بادام‌زمینی + نان + موز",
        "name_en": "Peanut butter with bread and banana",
        "items": (
            item("creamy-peanut-butter", 30, 15, 50, F),
            item("sangak-bread", 60, 30, 120, C),
            item("banana", 120, 70, 200, M),
        ),
    },
    {
        "code": "BF08",
        "category": MealCategory.BREAKFAST,
        "name_fa": "جو دوسر + شیر + موز + مغزها",
        "name_en": "Oats, milk, banana and nuts",
        "items": (
            item("oats", 60, 35, 100, C),
            item("milk", 250, 150, 400, P),
            item("banana", 120, 70, 200, M),
            item("walnuts", 20, 10, 35, F, required=False),
            item("almonds", 15, 10, 30, F, required=False),
        ),
    },
    {
        "code": "LU01",
        "category": MealCategory.LUNCH,
        "name_fa": "جوجه کباب + برنج + گوجه کبابی",
        "name_en": "Chicken kebab with rice and grilled tomato",
        "items": (
            item("chicken-breast", 180, 120, 260, P),
            item("basmati-rice", 80, 50, 130, C),
            item("tomato", 120, 60, 220, M),
            item("vegetable-oil", 5, 2, 10, F, required=False),
        ),
    },
    {
        "code": "LU02",
        "category": MealCategory.LUNCH,
        "name_fa": "سینه مرغ آب‌پز + برنج + سالاد",
        "name_en": "Boiled chicken breast with rice and salad",
        "items": (
            item("chicken-breast", 160, 100, 250, P),
            item("basmati-rice", 80, 50, 130, C),
            item("lettuce", 80, 40, 150, FB),
            item("cucumber", 60, 30, 120, M),
            item("tomato", 60, 30, 120, M),
        ),
    },
    {
        "code": "LU03",
        "category": MealCategory.LUNCH,
        "name_fa": "زرشک‌پلو با مرغ + سالاد",
        "name_en": "Chicken rice with barberries and salad",
        "items": (
            item("chicken-breast", 170, 110, 260, P),
            item("basmati-rice", 80, 50, 130, C),
            item("lettuce", 60, 30, 120, FB),
            item("cucumber", 60, 30, 120, M),
            item("tomato", 60, 30, 120, M),
        ),
    },
    {
        "code": "LU04",
        "category": MealCategory.LUNCH,
        "name_fa": "ماهی کبابی/تنوری + برنج + سبزیجات",
        "name_en": "Grilled or baked fish with rice and vegetables",
        "items": (
            item("white-fish", 180, 120, 260, P),
            item("basmati-rice", 80, 50, 130, C),
            item("broccoli", 100, 50, 180, FB),
            item("carrot", 80, 40, 150, M),
        ),
    },
    {
        "code": "LU05",
        "category": MealCategory.LUNCH,
        "name_fa": "ماکارونی + گوشت چرخ‌کرده + سبزیجات",
        "name_en": "Pasta with ground beef and vegetables",
        "items": (
            item("pasta", 90, 60, 140, C),
            item("ground-beef", 140, 90, 220, P),
            item("carrot", 70, 35, 140, M),
            item("bell-pepper", 70, 35, 140, FB),
            item("tomato-paste", 30, 15, 60, M, required=False),
        ),
    },
    {
        "code": "LU06",
        "category": MealCategory.LUNCH,
        "name_fa": "ماکارونی + مرغ چرخ‌کرده + سبزیجات",
        "name_en": "Pasta with ground chicken and vegetables",
        "items": (
            item("pasta", 90, 60, 140, C),
            item("chicken-breast", 140, 90, 220, P),
            item("carrot", 70, 35, 140, M),
            item("bell-pepper", 70, 35, 140, FB),
            item("tomato-paste", 30, 15, 60, M, required=False),
        ),
    },
    {
        "code": "LU07",
        "category": MealCategory.LUNCH,
        "name_fa": "قورمه‌سبزی + برنج",
        "name_en": "Ghormeh sabzi with rice",
        "items": (item("basmati-rice", 80, 50, 130, C),),
    },
    {
        "code": "LU08",
        "category": MealCategory.LUNCH,
        "name_fa": "قیمه + برنج",
        "name_en": "Gheimeh with rice",
        "items": (item("basmati-rice", 80, 50, 130, C),),
    },
    {
        "code": "LU09",
        "category": MealCategory.LUNCH,
        "name_fa": "عدس‌پلو + گوشت یا مرغ چرخ‌کرده + ماست",
        "name_en": "Lentil rice with ground meat or chicken and yogurt",
        "items": (
            item("basmati-rice", 75, 45, 125, C),
            item("lentils", 45, 25, 75, FB),
            item("ground-beef", 100, 60, 170, P),
            item("plain-yogurt", 180, 100, 300, P),
            item("raisins", 15, 5, 30, M, required=False),
        ),
    },
    {
        "code": "LU10",
        "category": MealCategory.LUNCH,
        "name_fa": "لوبیاپلو + گوشت یا مرغ چرخ‌کرده + سالاد",
        "name_en": "Green bean rice with ground meat or chicken and salad",
        "items": (
            item("basmati-rice", 75, 45, 125, C),
            item("green-beans", 100, 50, 180, FB),
            item("ground-beef", 100, 60, 170, P),
            item("tomato-paste", 30, 15, 60, M),
            item("lettuce", 60, 30, 120, FB),
            item("cucumber", 60, 30, 120, M),
            item("tomato", 60, 30, 120, M),
        ),
    },
    {
        "code": "LU11",
        "category": MealCategory.LUNCH,
        "name_fa": "آبگوشت + نان سنگک + سبزی",
        "name_en": "Abgoosht with Sangak and herbs",
        "items": (
            item("sangak-bread", 60, 30, 120, C),
            item("mixed-herbs", 60, 30, 120, M),
        ),
    },
    {
        "code": "LU12",
        "category": MealCategory.LUNCH,
        "name_fa": "کباب تابه‌ای گوشت چرخ‌کرده + برنج + سالاد",
        "name_en": "Pan kebab with rice and salad",
        "items": (
            item("ground-beef", 170, 110, 250, P),
            item("basmati-rice", 80, 50, 130, C),
            item("onion", 30, 15, 60, M, required=False),
            item("lettuce", 60, 30, 120, FB),
            item("cucumber", 60, 30, 120, M),
            item("tomato", 60, 30, 120, M),
        ),
    },
    {
        "code": "LU13",
        "category": MealCategory.LUNCH,
        "name_fa": "کباب تابه‌ای ۵۰٪ مرغ + ۵۰٪ گوشت + برنج + سالاد",
        "name_en": "Half chicken, half beef pan kebab with rice and salad",
        "items": (
            item("chicken-breast", 85, 55, 125, P),
            item("ground-beef", 85, 55, 125, P),
            item("basmati-rice", 80, 50, 130, C),
            item("onion", 30, 15, 60, M, required=False),
            item("lettuce", 60, 30, 120, FB),
            item("cucumber", 60, 30, 120, M),
            item("tomato", 60, 30, 120, M),
        ),
    },
    {
        "code": "DN01",
        "category": MealCategory.DINNER,
        "name_fa": "سینه مرغ کبابی + برنج + سبزیجات",
        "name_en": "Grilled chicken breast with rice and vegetables",
        "items": (
            item("chicken-breast", 160, 100, 250, P),
            item("basmati-rice", 70, 45, 120, C),
            item("broccoli", 80, 40, 150, FB),
            item("carrot", 80, 40, 150, M),
        ),
    },
    {
        "code": "DN02",
        "category": MealCategory.DINNER,
        "name_fa": "سینه مرغ آب‌پز + نان + خیار و گوجه",
        "name_en": "Boiled chicken breast with bread, cucumber and tomato",
        "items": (
            item("chicken-breast", 160, 100, 250, P),
            item("sangak-bread", 60, 30, 120, C),
            item("cucumber", 80, 40, 150, FB),
            item("tomato", 80, 40, 150, M),
        ),
    },
    {
        "code": "DN03",
        "category": MealCategory.DINNER,
        "name_fa": "ماهی + سیب‌زمینی آب‌پز/تنوری + سبزیجات",
        "name_en": "Fish with boiled or baked potato and vegetables",
        "items": (
            item("white-fish", 170, 110, 250, P),
            item("potato", 250, 150, 400, C),
            item("broccoli", 80, 40, 150, FB),
            item("carrot", 80, 40, 150, M),
        ),
    },
    {
        "code": "DN04",
        "category": MealCategory.DINNER,
        "name_fa": "تخم‌مرغ + سیب‌زمینی + سالاد",
        "name_en": "Eggs with potato and salad",
        "items": (
            item("egg", 100, 50, 200, P),
            item("potato", 200, 120, 350, C),
            item("lettuce", 70, 35, 140, FB),
            item("cucumber", 60, 30, 120, M),
            item("tomato", 60, 30, 120, M),
        ),
    },
    {
        "code": "DN05",
        "category": MealCategory.DINNER,
        "name_fa": "عدسی + نان + ماست",
        "name_en": "Lentils with bread and yogurt",
        "items": (
            item("lentils", 65, 40, 105, P),
            item("sangak-bread", 60, 30, 120, C),
            item("plain-yogurt", 180, 100, 300, P),
            item("onion", 20, 10, 40, M, required=False),
        ),
    },
    {
        "code": "DN06",
        "category": MealCategory.DINNER,
        "name_fa": "خوراک لوبیا + نان + سبزیجات",
        "name_en": "Bean stew with bread and vegetables",
        "items": (
            item("pinto-beans", 70, 40, 110, P),
            item("sangak-bread", 60, 30, 120, C),
            item("tomato-paste", 30, 15, 60, M),
            item("carrot", 80, 40, 150, FB),
            item("onion", 25, 10, 50, M, required=False),
        ),
    },
    {
        "code": "DN07",
        "category": MealCategory.DINNER,
        "name_fa": "ساندویچ خانگی مرغ + سبزیجات",
        "name_en": "Homemade chicken sandwich with vegetables",
        "items": (
            item("chicken-breast", 130, 80, 200, P),
            item("sangak-bread", 60, 30, 120, C),
            item("lettuce", 60, 30, 120, FB),
            item("cucumber", 60, 30, 120, M),
            item("tomato", 60, 30, 120, M),
        ),
    },
    {
        "code": "DN08",
        "category": MealCategory.DINNER,
        "name_fa": "پیتزای مرغ خانگی با مرغ، پنیر، قارچ، فلفل دلمه‌ای و خمیر",
        "name_en": "Homemade chicken pizza with cheese, mushroom and bell pepper",
        "items": (
            item("chicken-breast", 120, 75, 190, P),
            item("low-fat-cheese", 60, 35, 100, P),
            item("mushroom", 80, 40, 150, FB),
            item("bell-pepper", 70, 35, 140, M),
            item("wheat-flour", 100, 60, 160, C),
            item("tomato-paste", 30, 15, 60, M, required=False),
            item("vegetable-oil", 5, 2, 10, F, required=False),
        ),
    },
    {
        "code": "SN01",
        "category": MealCategory.SNACK,
        "name_fa": "بادام‌زمینی",
        "name_en": "Peanuts",
        "items": (item("peanuts", 50, 20, 80, F),),
    },
    {
        "code": "SN02",
        "category": MealCategory.SNACK,
        "name_fa": "کره بادام‌زمینی + نان",
        "name_en": "Peanut butter with bread",
        "items": (item("creamy-peanut-butter", 30, 15, 50, F), item("sangak-bread", 30, 15, 60, C)),
    },
    {
        "code": "SN03",
        "category": MealCategory.SNACK,
        "name_fa": "شیر + موز",
        "name_en": "Milk and banana",
        "items": (item("milk", 250, 150, 400, P), item("banana", 120, 70, 200, C)),
    },
    {
        "code": "SN04",
        "category": MealCategory.SNACK,
        "name_fa": "ماست + میوه",
        "name_en": "Yogurt and fruit",
        "items": (item("plain-yogurt", 200, 120, 320, P), item("apple", 150, 80, 250, C)),
    },
    {
        "code": "SN05",
        "category": MealCategory.SNACK,
        "name_fa": "ماست + گردو",
        "name_en": "Yogurt and walnuts",
        "items": (item("plain-yogurt", 200, 120, 320, P), item("walnuts", 20, 10, 35, F)),
    },
    {
        "code": "SN06",
        "category": MealCategory.SNACK,
        "name_fa": "میوه + بادام‌زمینی",
        "name_en": "Fruit and peanuts",
        "items": (item("apple", 150, 80, 250, C), item("peanuts", 30, 15, 60, F)),
    },
    {
        "code": "SN07",
        "category": MealCategory.SNACK,
        "name_fa": "پنیر + نان",
        "name_en": "Cheese and bread",
        "items": (item("low-fat-cheese", 40, 25, 70, P), item("sangak-bread", 30, 15, 60, C)),
    },
    {
        "code": "SN08",
        "category": MealCategory.SNACK,
        "name_fa": "تخم‌مرغ آب‌پز",
        "name_en": "Boiled eggs",
        "items": (item("egg", 100, 50, 150, P),),
    },
    {
        "code": "PW01",
        "category": MealCategory.POST_WORKOUT,
        "name_fa": "تخم‌مرغ آب‌پز + سیب‌زمینی آب‌پز یا تنوری",
        "name_en": "Boiled eggs with boiled or baked potato",
        "items": (item("egg", 100, 50, 200, P), item("potato", 250, 150, 400, C)),
    },
)
