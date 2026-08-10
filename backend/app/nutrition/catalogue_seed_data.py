# ruff: noqa: E501
"""Versioned, curated Iranian base-food catalogue backed by USDA SR Legacy.

Values are per 100 g edible portion. Empty nutrient cells are intentionally
unavailable and must never be interpreted as zero.
"""

from dataclasses import dataclass
from decimal import Decimal

USDA_SOURCE_NAME = "USDA FoodData Central SR Legacy"
USDA_SOURCE_REFERENCE = "https://fdc.nal.usda.gov/download-datasets/"
USDA_DATA_VERSION = "sr-legacy-2018-04"
USDA_ACCESS_DATE = "2026-08-09"

NUTRIENT_COLUMNS = (
    "energy_kcal",
    "protein_g",
    "carbohydrate_g",
    "total_fat_g",
    "fibre_g",
    "total_sugars_g",
    "saturated_fat_g",
    "sodium_mg",
    "calcium_mg",
    "potassium_mg",
    "magnesium_mg",
    "iron_mg",
    "zinc_mg",
    "vitamin_c_mg",
    "vitamin_d_mcg",
    "vitamin_b12_mcg",
    "folate_dfe_mcg",
)

NUTRIENT_UNITS = {
    "energy_kcal": "kcal",
    "protein_g": "g",
    "carbohydrate_g": "g",
    "total_fat_g": "g",
    "fibre_g": "g",
    "total_sugars_g": "g",
    "saturated_fat_g": "g",
    "sodium_mg": "mg",
    "calcium_mg": "mg",
    "potassium_mg": "mg",
    "magnesium_mg": "mg",
    "iron_mg": "mg",
    "zinc_mg": "mg",
    "vitamin_c_mg": "mg",
    "vitamin_d_mcg": "mcg",
    "vitamin_b12_mcg": "mcg",
    "folate_dfe_mcg": "mcg",
}


@dataclass(frozen=True)
class ApprovedFoodSeed:
    slug: str
    name_fa: str
    name_en: str
    category: str
    roles: tuple[str, ...]
    aliases: tuple[str, ...]
    measurement_basis: str
    source_food_id: str | None
    portions: tuple["FoodPortionSeed", ...] = ()


@dataclass(frozen=True)
class FoodPortionSeed:
    code: str
    quantity: Decimal
    label_fa: str
    label_en: str
    grams: Decimal
    is_default: bool
    sort_order: int
    source_name: str
    source_reference: str


def _food(
    slug: str,
    name_fa: str,
    name_en: str,
    category: str,
    role: str,
    basis: str,
    source_food_id: str | None,
    *aliases: str,
    portions: tuple[FoodPortionSeed, ...] = (),
) -> ApprovedFoodSeed:
    return ApprovedFoodSeed(
        slug=slug,
        name_fa=name_fa,
        name_en=name_en,
        category=category,
        roles=(role,),
        aliases=(name_fa, name_en, *aliases),
        measurement_basis=basis,
        source_food_id=source_food_id,
        portions=portions,
    )


APPROVED_FOODS = (
    _food(
        "chicken-breast",
        "سینه مرغ",
        "Chicken breast",
        "poultry",
        "main_protein",
        "raw",
        "171077",
        "فیله مرغ",
    ),
    _food(
        "chicken-thigh-skinless",
        "ران مرغ بدون پوست",
        "Skinless chicken thigh",
        "poultry",
        "main_protein",
        "raw",
        "173627",
        "ران مرغ",
    ),
    _food("beef", "گوشت گوساله", "Beef", "red_meat", "main_protein", "raw", "174030", "گوشت گاو"),
    _food("lamb", "گوشت گوسفند", "Lamb", "red_meat", "main_protein", "raw", "174370"),
    _food("white-fish", "ماهی سفید", "White fish", "fish", "main_protein", "raw", "173711"),
    _food(
        "rainbow-trout",
        "ماهی قزل‌آلا",
        "Rainbow trout",
        "fish",
        "main_protein",
        "raw",
        "173717",
        "قزل آلا",
    ),
    _food(
        "canned-tuna",
        "تن ماهی",
        "Canned tuna",
        "fish",
        "main_protein",
        "as_purchased",
        "173709",
        "کنسرو تن ماهی",
    ),
    _food(
        "egg", "تخم‌مرغ", "Egg", "eggs", "main_protein", "raw", "171287", "تخم مرغ",
        portions=(FoodPortionSeed("piece", Decimal("1"), "۱ عدد", "1 piece", Decimal("50"), True, 0, USDA_SOURCE_NAME, USDA_SOURCE_REFERENCE),),
    ),
    _food("lentils", "عدس", "Lentils", "legumes", "main_protein", "dry", "172420", "عدس خشک"),
    _food("chickpeas", "نخود", "Chickpeas", "legumes", "main_protein", "dry", "173756", "نخود خشک"),
    _food("pinto-beans", "لوبیا چیتی", "Pinto beans", "legumes", "main_protein", "dry", "175199"),
    _food(
        "red-kidney-beans",
        "لوبیا قرمز",
        "Red kidney beans",
        "legumes",
        "main_protein",
        "dry",
        "173744",
    ),
    _food("white-beans", "لوبیا سفید", "White beans", "legumes", "main_protein", "dry", "175202"),
    _food(
        "black-eyed-peas",
        "لوبیا چشم‌بلبلی",
        "Black-eyed peas",
        "legumes",
        "main_protein",
        "dry",
        "173758",
        "لوبیا چشم بلبلی",
    ),
    _food("split-peas", "لپه", "Split peas", "legumes", "main_protein", "dry", "172428"),
    _food("mung-beans", "ماش", "Mung beans", "legumes", "main_protein", "dry", "174256"),
    _food("soybeans", "سویا", "Soybeans", "legumes", "main_protein", "dry", "174270", "دانه سویا"),
    _food(
        "basmati-rice",
        "برنج",
        "Basmati rice",
        "grains",
        "main_staple",
        "dry",
        "168877",
        "برنج خشک",
        "برنج باسماتی",
    ),
    _food("sangak-bread", "نان سنگک", "Sangak bread", "bread", "main_staple", "as_purchased", None),
    _food(
        "barbari-bread", "نان بربری", "Barbari bread", "bread", "main_staple", "as_purchased", None
    ),
    _food("lavash-bread", "نان لواش", "Lavash bread", "bread", "main_staple", "as_purchased", None),
    _food(
        "taftoon-bread", "نان تافتون", "Taftoon bread", "bread", "main_staple", "as_purchased", None
    ),
    _food("oats", "جو دوسر", "Oats", "grains", "main_staple", "dry", "173904", "اوتمیل"),
    _food("barley", "جو", "Barley", "grains", "main_staple", "dry", "170284", "جو پوست کنده"),
    _food(
        "potato",
        "سیب‌زمینی",
        "Potato",
        "starchy_vegetables",
        "main_staple",
        "raw",
        "170026",
        "سیب زمینی",
    ),
    _food("corn", "ذرت", "Corn", "starchy_vegetables", "main_staple", "raw", "169998"),
    _food("pasta", "ماکارونی", "Pasta", "grains", "main_staple", "dry", "169736", "پاستا"),
    _food("milk", "شیر", "Milk", "dairy", "flexible", "as_purchased", "172217", "شیر کامل"),
    _food(
        "plain-yogurt",
        "ماست ساده",
        "Plain yogurt",
        "dairy",
        "flexible",
        "as_purchased",
        "171284",
        "ماست",
    ),
    _food(
        "low-fat-cheese",
        "پنیر کم‌چرب",
        "Low-fat cheese",
        "dairy",
        "flexible",
        "as_purchased",
        "172182",
        "پنیر کم چرب",
    ),
    _food("tomato", "گوجه‌فرنگی", "Tomato", "vegetables", "flexible", "raw", "170457", "گوجه فرنگی"),
    _food("cucumber", "خیار", "Cucumber", "vegetables", "flexible", "raw", "168409"),
    _food("onion", "پیاز", "Onion", "vegetables", "flexible", "raw", "170000"),
    _food("carrot", "هویج", "Carrot", "vegetables", "flexible", "raw", "170393"),
    _food("lettuce", "کاهو", "Lettuce", "vegetables", "flexible", "raw", "169247"),
    _food("cabbage", "کلم", "Cabbage", "vegetables", "flexible", "raw", "169975"),
    _food("spinach", "اسفناج", "Spinach", "vegetables", "flexible", "raw", "168462"),
    _food("zucchini", "کدو سبز", "Zucchini", "vegetables", "flexible", "raw", "169291"),
    _food("eggplant", "بادمجان", "Eggplant", "vegetables", "flexible", "raw", "169228"),
    _food(
        "bell-pepper",
        "فلفل دلمه‌ای",
        "Bell pepper",
        "vegetables",
        "flexible",
        "raw",
        "170427",
        "فلفل دلمه ای",
    ),
    _food("mushroom", "قارچ", "Mushroom", "vegetables", "flexible", "raw", "169251"),
    _food("celery", "کرفس", "Celery", "vegetables", "flexible", "raw", "169988"),
    _food("broccoli", "بروکلی", "Broccoli", "vegetables", "flexible", "raw", "170379"),
    _food(
        "cauliflower", "گل‌کلم", "Cauliflower", "vegetables", "flexible", "raw", "169986", "گل کلم"
    ),
    _food(
        "mixed-herbs",
        "سبزی خوردن",
        "Mixed fresh herbs",
        "vegetables",
        "flexible",
        "raw",
        "170416",
        "سبزی تازه",
    ),
    _food("olive-oil", "روغن زیتون", "Olive oil", "fats", "flexible", "as_purchased", "171413"),
    _food(
        "vegetable-oil",
        "روغن مایع",
        "Vegetable oil",
        "fats",
        "flexible",
        "as_purchased",
        "171411",
        "روغن گیاهی",
    ),
    _food("butter", "کره", "Butter", "fats", "flexible", "as_purchased", "173410"),
    _food("walnuts", "گردو", "Walnuts", "nuts_seeds", "flexible", "raw", "170187"),
    _food("almonds", "بادام", "Almonds", "nuts_seeds", "flexible", "raw", "170567"),
    _food(
        "peanuts", "بادام‌زمینی", "Peanuts", "nuts_seeds", "flexible", "raw", "172430", "بادام زمینی"
    ),
    _food("sesame", "کنجد", "Sesame", "nuts_seeds", "flexible", "raw", "170150"),
    _food("tahini", "ارده", "Tahini", "nuts_seeds", "flexible", "as_purchased", "170189"),
    _food("apple", "سیب", "Apple", "fruit", "snack", "raw", "171688"),
    _food("banana", "موز", "Banana", "fruit", "snack", "raw", "173944"),
    _food("orange", "پرتقال", "Orange", "fruit", "snack", "raw", "169097"),
    _food("tangerine", "نارنگی", "Tangerine", "fruit", "snack", "raw", "169105"),
    _food("kiwi", "کیوی", "Kiwi", "fruit", "snack", "raw", "168153"),
    _food("pomegranate", "انار", "Pomegranate", "fruit", "snack", "raw", "169134"),
    _food("grapes", "انگور", "Grapes", "fruit", "snack", "raw", "174683"),
    _food("dates", "خرما", "Dates", "fruit", "snack", "raw", "171726"),
    _food("raisins", "کشمش", "Raisins", "fruit", "snack", "raw", "168165"),
    _food(
        "strawberries", "توت‌فرنگی", "Strawberries", "fruit", "snack", "raw", "167762", "توت فرنگی"
    ),
    _food("watermelon", "هندوانه", "Watermelon", "fruit", "snack", "raw", "167765"),
    _food("melon", "خربزه", "Melon", "fruit", "snack", "raw", "169092"),
)


_COMPOSITION_CSV = """slug|energy_kcal|protein_g|carbohydrate_g|total_fat_g|fibre_g|total_sugars_g|saturated_fat_g|sodium_mg|calcium_mg|potassium_mg|magnesium_mg|iron_mg|zinc_mg|vitamin_c_mg|vitamin_d_mcg|vitamin_b12_mcg|folate_dfe_mcg
chicken-breast|120|22.5|0|2.62|0|0|0.563|45|5|334|28|0.37|0.68|0|0|0.21|9
chicken-thigh-skinless|121|19.66|0|4.12|0|0|1.097|95|7|242|23|0.81|1.58|0|0|0.61|4
beef|176|20|0|10|0|0|3.927|66|12|321|20|2.24|4.79|0|0.1|2.21|6
lamb|282|16.56|0|23.41|0|0|10.19|59|16|222|21|1.55|3.41|0|0.1|2.31|18
white-fish|134|19.09|0|5.86|0|0|0.906|51|26|317|33|0.37|0.99|0|12|1|15
rainbow-trout|141|19.94|0|6.18|0|0|1.383|51|25|377|25|0.31|0.45|2.9|15.9|4.3|11
canned-tuna|86|19.44|0|0.96|0|0|0.211|247|17|179|23|1.63|0.69|0|1.2|2.55|4
egg|143|12.56|0.72|9.51|0|0.37|3.126|142|56|138|12|1.75|1.29|0|2|0.89|47
lentils|352|24.63|63.35|1.06|10.7|2.03|0.154|6|35|677|47|6.51|3.27|4.5|0|0|479
chickpeas|378|20.47|62.95|6.04|12.2|10.7|0.603|24|57|718|79|4.31|2.76|4|0|0|557
pinto-beans|347|21.42|62.55|1.23|15.5|2.11|0.235|12|113|1393|176|5.07|2.28|6.3|0|0|525
red-kidney-beans|337|22.53|61.29|1.06|15.2|2.1|0.154|12|83|1359|138|6.69|2.79|4.5|0|0|394
white-beans|333|23.36|60.27|0.85|15.2|2.11|0.219|16|240|1795|190|10.44|3.67|0|0|0|388
black-eyed-peas|336|23.52|60.03|1.26|10.6|6.9|0.331|16|110|1112|184|8.27|3.37|1.5|0|0|633
split-peas|364|23.12|61.63|3.89|22.2|3.14|0.408|5|46|852|63|4.73|3.49|1.8|0|0|15
mung-beans|347|23.86|62.62|1.15|16.3|6.6|0.348|15|132|1246|189|6.74|2.68|4.8|0|0|625
soybeans|446|36.49|30.16|19.94|9.3|7.33|2.884|2|277|1797|280|15.7|4.89|6|0|0|375
basmati-rice|365|7.13|79.95|0.66|1.3|0.12|0.18|5|28|115|25|4.31|1.09|0|0|0|387
oats|379|13.15|67.7|6.52|10.1|0.99|1.11|6|52|362|138|4.25|3.64|0|0|0|32
barley|352|9.91|77.72|1.16|15.6|0.8|0.244|9|29|280|79|2.5|2.13|0|0|0|23
potato|77|2.05|17.49|0.09|2.1|0.82|0.025|6|12|425|23|0.81|0.3|19.7|0|0|15
corn|86|3.27|18.7|1.35|2|6.26|0.325|15|2|270|37|0.52|0.46|6.8|0|0|42
pasta|371|13.04|74.67|1.51|3.2|2.67|0.277|6|21|223|53|3.3|1.41|0|0|0|391
milk|61|3.15|4.78|3.27|0|5.05|1.865|43|113|132|10|0.03|0.37|0|0.1|0.45|5
plain-yogurt|61|3.47|4.66|3.25|0|4.66|2.096|46|121|155|12|0.05|0.59|0.5|0.1|0.37|7
low-fat-cheese|81|10.45|4.76|2.27|0|4|1.235|308|111|125|9|0.13|0.51|0|0|0.47|8
tomato|18|0.88|3.89|0.2|1.2|2.63|0.028|5|10|237|11|0.27|0.17|13.7|0|0|15
cucumber|15|0.65|3.63|0.11|0.5|1.67|0.037|2|16|147|13|0.28|0.2|2.8|0|0|7
onion|40|1.1|9.34|0.1|1.7|4.24|0.042|4|23|146|10|0.21|0.17|7.4|0|0|19
carrot|41|0.93|9.58|0.24|2.8|4.74|0.032|69|33|320|12|0.3|0.24|5.9|0|0|19
lettuce|17|1.23|3.29|0.3|2.1|1.19|0.039|8|33|247|14|0.97|0.23|4|0|0|136
cabbage|25|1.28|5.8|0.1|2.5|3.2|0.034|18|40|170|12|0.47|0.18|36.6|0|0|43
spinach|23|2.86|3.63|0.39|2.2|0.42|0.063|79|99|558|79|2.71|0.53|28.1|0|0|194
zucchini|17|1.21|3.11|0.32|1|2.5|0.084|8|16|261|18|0.37|0.32|17.9|0|0|24
eggplant|25|0.98|5.88|0.18|3|3.53|0.034|2|9|229|14|0.23|0.16|2.2|0|0|22
bell-pepper|20|0.86|4.64|0.17|1.7|2.4|0.058|3|10|175|10|0.34|0.13|80.4|0|0|10
mushroom|22|3.09|3.26|0.34|1|1.98|0.05|5|3|318|9|0.5|0.52|2.1|0.2|0.04|17
celery|14|0.69|2.97|0.17|1.6|1.34|0.042|80|40|260|11|0.2|0.13|3.1|0|0|36
broccoli|34|2.82|6.64|0.37|2.6|1.7|0.114|33|47|316|21|0.73|0.41|89.2|0|0|63
cauliflower|25|1.92|4.97|0.28|2|1.91|0.13|30|22|299|15|0.42|0.27|48.2|0|0|57
mixed-herbs|36|2.97|6.33|0.79|3.3|0.85|0.132|56|138|554|50|6.2|1.07|133|0|0|152
olive-oil|884|0|0|100|0|0|13.808|2|1|1|0|0.56|0|0|0|0|0
vegetable-oil|884|0|0|100|0|0|15.65|0|0|0|0|0.05|0.01|0|0|0|0
butter|717|0.85|0.06|81.11|0|0.06|51.368|643|24|24|2|0.02|0.09|0|0|0.17|3
walnuts|654|15.23|13.71|65.21|6.7|2.61|6.126|2|98|441|158|2.91|3.09|1.3|0|0|98
almonds|579|21.15|21.55|49.93|12.5|4.35|3.802|1|269|733|270|3.71|3.12|0|0|0|44
peanuts|567|25.8|16.13|49.24|8.5|4.72|6.279|18|92|705|168|4.58|3.27|0|0|0|240
sesame|573|17.73|23.45|49.67|11.8|0.3|6.957|11|975|468|351|14.55|7.75|0|0|0|97
tahini|595|17|21.19|53.76|9.3|0.49|7.529|115|426|414|95|8.95|4.62|0|0|0|98
apple|52|0.26|13.81|0.17|2.4|10.39|0.028|1|6|107|5|0.12|0.04|4.6|0|0|3
banana|89|1.09|22.84|0.33|2.6|12.23|0.112|1|5|358|27|0.26|0.15|8.7|0|0|20
orange|47|0.94|11.75|0.12|2.4|9.35|0.015|0|40|181|10|0.1|0.07|53.2|0|0|30
tangerine|53|0.81|13.34|0.31|1.8|10.58|0.039|2|37|166|12|0.15|0.07|26.7|0|0|16
kiwi|61|1.14|14.66|0.52|3|8.99|0.029|3|34|312|17|0.31|0.14|92.7|0|0|25
pomegranate|83|1.67|18.7|1.17|4|13.67|0.12|3|10|236|12|0.3|0.35|10.2|0|0|38
grapes|69|0.72|18.1|0.16|0.9|15.48|0.054|2|10|191|7|0.36|0.07|3.2|0|0|2
dates|282|2.45|75.03|0.39|8|63.35|0.032|2|39|656|43|1.02|0.29|0.4|0|0|19
raisins|299|3.3|79.32|0.25|4.5|65.18|0.094|26|62|744|36|1.79|0.36|2.3|0|0|5
strawberries|32|0.67|7.68|0.3|2|4.89|0.015|1|16|153|13|0.41|0.14|58.8|0|0|24
watermelon|30|0.61|7.55|0.15|0.4|6.2|0.016|1|7|112|10|0.24|0.1|8.1|0|0|3
melon|34|0.84|8.16|0.19|0.9|7.86|0.051|16|9|267|12|0.21|0.18|36.7|0|0|21
"""


def composition_for(slug: str) -> dict[str, Decimal]:
    header, *rows = _COMPOSITION_CSV.strip().splitlines()
    columns = header.split("|")
    for row in rows:
        values = row.split("|")
        if values[0] == slug:
            return {
                code: Decimal(value)
                for code, value in zip(columns[1:], values[1:], strict=True)
                if value
            }
    return {}
