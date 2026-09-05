"""Generate a clean, beautiful PDF report of Fitsho food catalogue."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from html import escape

from weasyprint import HTML

from app.config import get_settings
from app.database.session import get_engine
from app.nutrition.catalogue_view import member_food_catalogue
from sqlalchemy.orm import Session

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa_num(val: int | float | str | Decimal) -> str:
    if val is None or val == "":
        return "—"
    if isinstance(val, Decimal):
        val_float = float(val)
        if val_float.is_integer():
            s = f"{int(val_float)}"
        else:
            s = f"{val_float:.1f}"
    elif isinstance(val, float):
        if val.is_integer():
            s = f"{int(val)}"
        else:
            s = f"{val:.1f}"
    else:
        s = str(val)
    return s.translate(_PERSIAN_DIGITS)


CATEGORY_INFO = {
    "vegetables": ("سبزیجات", "Vegetables"),
    "fruit": ("میوه‌ها", "Fruits"),
    "nuts_seeds": ("مغزها و دانه‌ها", "Nuts & Seeds"),
    "legumes": ("حبوبات", "Legumes"),
    "dairy": ("لبنیات", "Dairy"),
    "grains": ("غلات و آردها", "Grains & Flours"),
    "bread": ("نان‌های سنتی", "Traditional Breads"),
    "red_meat": ("گوشت قرمز", "Red Meat"),
    "starchy_vegetables": ("سبزیجات نشاسته‌ای", "Starchy Vegetables"),
    "fats": ("روغن‌ها و چربی‌ها", "Oils & Fats"),
    "fish": ("ماهی و غذاهای دریایی", "Fish & Seafood"),
    "poultry": ("مرغ و ماکیان", "Poultry"),
    "eggs": ("تخم‌مرغ", "Eggs"),
}

BASIS_FA = {
    "raw": "خام",
    "dry": "خشک",
    "as_purchased": "آماده / خرید",
}


def build_html(categories_data: list[tuple[str, tuple[str, str], list]]) -> str:
    total_items = sum(len(items) for _, _, items in categories_data)
    total_categories = len(categories_data)

    # Table of contents items (2 columns for clean spacing)
    toc_cards = []
    for cat_key, (name_fa, name_en), items in categories_data:
        toc_cards.append(f"""
        <div class="toc-item">
            <span class="toc-dot"></span>
            <span class="toc-name">{escape(name_fa)}</span>
            <span class="toc-en">({escape(name_en)})</span>
            <span class="toc-count">{fa_num(len(items))} قلم</span>
        </div>
        """)
    toc_html = "\n".join(toc_cards)

    # Category sections
    sections = []
    for cat_key, (name_fa, name_en), items in categories_data:
        rows = []
        for idx, food in enumerate(items, start=1):
            macros = food.macros
            cal = fa_num(macros.get("energy_kcal"))
            protein = fa_num(macros.get("protein_g"))
            carbs = fa_num(macros.get("carbohydrate_g"))
            fat = fa_num(macros.get("total_fat_g"))
            fiber = fa_num(macros.get("fibre_g"))
            basis = BASIS_FA.get(str(food.measurement_basis), str(food.measurement_basis))

            rows.append(f"""
            <tr>
                <td class="col-num">{fa_num(idx)}</td>
                <td class="col-name">
                    <div class="food-fa">{escape(food.name_fa)}</div>
                    <div class="food-en">{escape(food.name_en)}</div>
                </td>
                <td class="col-basis"><span class="badge badge-basis">{basis}</span></td>
                <td class="col-macro cal-cell">{cal}</td>
                <td class="col-macro protein-cell">{protein}</td>
                <td class="col-macro carbs-cell">{carbs}</td>
                <td class="col-macro fat-cell">{fat}</td>
                <td class="col-macro fiber-cell">{fiber}</td>
            </tr>
            """)

        rows_html = "\n".join(rows)

        sections.append(f"""
        <section class="category-block">
            <div class="category-header">
                <div class="category-titles">
                    <h2>{escape(name_fa)}</h2>
                    <span class="category-en">{escape(name_en)}</span>
                </div>
                <span class="category-badge">{fa_num(len(items))} قلم ماده غذایی</span>
            </div>
            <table class="food-table">
                <thead>
                    <tr>
                        <th class="th-num">#</th>
                        <th class="th-name">نام ماده غذایی</th>
                        <th class="th-basis">مبنا</th>
                        <th class="th-macro">کالری<small>(kcal)</small></th>
                        <th class="th-macro">پروتئین<small>(g)</small></th>
                        <th class="th-macro">کربوهیدرات<small>(g)</small></th>
                        <th class="th-macro">چربی<small>(g)</small></th>
                        <th class="th-macro">فیبر<small>(g)</small></th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </section>
        """)

    body_content = "\n".join(sections)

    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>کاتالوگ جامع مواد غذایی فیت‌شو</title>
<style>
@page {{
    size: A4;
    margin: 15mm 13mm 15mm 13mm;
    @bottom-right {{
        content: "فیت‌شو (Fitsho) — کاتالوگ جامع مواد غذایی";
        font-family: "Vazirmatn", sans-serif;
        font-size: 8pt;
        color: #839791;
    }}
    @bottom-left {{
        content: "صفحه " counter(page) " از " counter(pages);
        font-family: "Vazirmatn", sans-serif;
        font-size: 8pt;
        color: #839791;
    }}
}}

* {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}}

body {{
    font-family: "Vazirmatn", "DejaVu Sans", sans-serif;
    direction: rtl;
    text-align: right;
    color: #1a2e2b;
    background-color: #ffffff;
    font-size: 9.5pt;
    line-height: 1.5;
}}

.hero {{
    background: linear-gradient(135deg, #094e43 0%, #087d6c 100%);
    color: #ffffff;
    padding: 16px 20px;
    border-radius: 8px;
    margin-bottom: 14px;
    box-shadow: 0 2px 6px rgba(8, 125, 108, 0.15);
}}

.hero-top {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.2);
    padding-bottom: 8px;
    margin-bottom: 10px;
}}

.hero-brand {{
    display: flex;
    align-items: center;
    gap: 8px;
}}

.brand-badge {{
    background: #ffffff;
    color: #087d6c;
    font-weight: 800;
    font-size: 13pt;
    padding: 2px 10px;
    border-radius: 6px;
}}

.brand-sub {{
    font-size: 9pt;
    color: #d1fae5;
    font-weight: 400;
}}

.hero-title {{
    font-size: 15pt;
    font-weight: 700;
    margin-bottom: 4px;
}}

.hero-desc {{
    font-size: 8.5pt;
    color: #e6f7f3;
    margin-bottom: 12px;
    line-height: 1.6;
}}

.stats-grid {{
    display: flex;
    gap: 10px;
}}

.stat-chip {{
    background: rgba(255, 255, 255, 0.15);
    border: 1px solid rgba(255, 255, 255, 0.25);
    padding: 5px 12px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
}}

.stat-chip strong {{
    font-size: 10.5pt;
    font-weight: 700;
}}

.stat-chip span {{
    font-size: 8pt;
    color: #e6f7f3;
}}

.intro-box {{
    background: #f0fdf9;
    border: 1px solid #99f6e4;
    border-radius: 6px;
    padding: 8px 12px;
    margin-bottom: 14px;
    font-size: 8pt;
    color: #0f766e;
    line-height: 1.6;
}}

.toc-title {{
    font-size: 10pt;
    font-weight: 700;
    color: #087d6c;
    margin-bottom: 8px;
}}

.toc-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 6px 12px;
    margin-bottom: 16px;
}}

.toc-item {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 5px;
    padding: 5px 10px;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 8pt;
}}

.toc-dot {{
    width: 6px;
    height: 6px;
    background: #087d6c;
    border-radius: 50%;
    display: inline-block;
    flex-shrink: 0;
}}

.toc-name {{
    font-weight: 600;
    color: #1e293b;
}}

.toc-en {{
    color: #64748b;
    font-size: 7.5pt;
}}

.toc-count {{
    margin-right: auto;
    background: #e2e8f0;
    color: #334155;
    padding: 1px 6px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 7.5pt;
}}

.category-block {{
    margin-bottom: 18px;
    break-inside: auto;
}}

.category-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #f4fbf9;
    border-right: 4px solid #087d6c;
    border-radius: 4px;
    padding: 6px 10px;
    margin-bottom: 5px;
    break-after: avoid;
}}

.category-titles h2 {{
    font-size: 10.5pt;
    font-weight: 700;
    color: #094e43;
    display: inline;
}}

.category-en {{
    font-size: 8pt;
    color: #6b7280;
    margin-right: 6px;
}}

.category-badge {{
    background: #087d6c;
    color: #ffffff;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 7.5pt;
    font-weight: 600;
}}

.food-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 8pt;
    table-layout: fixed;
}}

thead {{
    display: table-header-group;
}}

.food-table th {{
    background: #e6f4f1;
    color: #0f766e;
    font-weight: 600;
    text-align: center;
    padding: 5px 4px;
    border: 1px solid #cce8e2;
    font-size: 7.5pt;
}}

.food-table th small {{
    display: block;
    font-size: 6.5pt;
    color: #14b8a6;
    font-weight: normal;
}}

.food-table th.th-name {{
    text-align: right;
    padding-right: 8px;
    width: 32%;
}}

.food-table th.th-num {{
    width: 5%;
}}

.food-table th.th-basis {{
    width: 11%;
}}

.food-table th.th-macro {{
    width: 10.4%;
}}

.food-table td {{
    padding: 4px 6px;
    border: 1px solid #e5e7eb;
    text-align: center;
    vertical-align: middle;
}}

.food-table tbody tr:nth-child(even) {{
    background-color: #fafbfc;
}}

.food-table td.col-num {{
    color: #6b7280;
    font-size: 7pt;
    font-weight: 600;
}}

.food-table td.col-name {{
    text-align: right;
    padding-right: 8px;
}}

.food-fa {{
    font-weight: 600;
    color: #111827;
    font-size: 8.5pt;
    line-height: 1.25;
}}

.food-en {{
    font-size: 7pt;
    color: #6b7280;
    font-family: sans-serif;
    line-height: 1.2;
    margin-top: 1px;
}}

.badge-basis {{
    display: inline-block;
    background: #f1f5f9;
    color: #475569;
    font-size: 7pt;
    padding: 1px 5px;
    border-radius: 4px;
    border: 1px solid #cbd5e1;
}}

.cal-cell {{
    color: #c2410c;
    font-weight: 700;
}}

.protein-cell {{
    color: #0369a1;
    font-weight: 700;
}}

.carbs-cell {{
    color: #6d28d9;
}}

.fat-cell {{
    color: #b45309;
}}

.fiber-cell {{
    color: #15803d;
}}

tr {{
    break-inside: avoid;
}}
</style>
</head>
<body>

<div class="hero">
    <div class="hero-top">
        <div class="hero-brand">
            <span class="brand-badge">فیت‌شو</span>
            <span class="brand-sub">همراه هوشمند تناسب اندام و تغذیه</span>
        </div>
        <div style="font-size: 8pt; color: #d1fae5; direction: ltr;">
            Fitsho Nutrition Food Catalogue
        </div>
    </div>
    <div class="hero-title">کاتالوگ جامع مواد غذایی و ارزش تغذیه‌ای</div>
    <div class="hero-desc">
        ارزش‌های غذایی محاسبه‌شده به ازای هر ۱۰۰ گرم بخش خوراکی (Edible Portion) براساس پایگاه‌های داده استاندارد USDA و پژوهش‌های معتبر تغذیه ایران.
    </div>
    <div class="stats-grid">
        <div class="stat-chip">
            <strong>{fa_num(total_items)}</strong>
            <span>ماده غذایی تاییدشده</span>
        </div>
        <div class="stat-chip">
            <strong>{fa_num(total_categories)}</strong>
            <span>گروه غذایی</span>
        </div>
        <div class="stat-chip">
            <strong>۱۰۰ گرم خوراکی</strong>
            <span>مبنای مقادیر ماکرو</span>
        </div>
    </div>
</div>

<div class="toc-title">دسته‌بندی‌های کاتالوگ غذایی:</div>
<div class="toc-grid">
    {toc_html}
</div>

<div class="intro-box">
    <strong>راهنما:</strong> تمام مقادیر ماکرونوترینت‌ها (کالری، پروتئین، کربوهیدرات، چربی و فیبر) بر حسب ۱۰۰ گرم بخش خوراکی محاسبه شده‌اند. مبنای سنجش («خام»، «خشک» یا «آماده مصرف») مشخص‌کننده شرایط توزین استاندارد ماده غذایی در برنامه‌های تغذیه فیت‌شو است.
</div>

{body_content}

</body>
</html>
"""


def main():
    settings = get_settings()
    engine = get_engine(settings.database_url)

    with Session(engine) as session:
        result = member_food_catalogue(session, query=None, category=None, page=1, page_size=500)
        items = result.items

    by_category = {}
    for item in items:
        by_category.setdefault(item.category, []).append(item)

    sorted_cat_keys = sorted(by_category.keys(), key=lambda k: len(by_category[k]), reverse=True)

    categories_data = []
    for cat_key in sorted_cat_keys:
        cat_info = CATEGORY_INFO.get(cat_key, (cat_key, cat_key))
        cat_items = sorted(by_category[cat_key], key=lambda x: x.name_fa)
        categories_data.append((cat_key, cat_info, cat_items))

    html_content = build_html(categories_data)

    output_pdf_path = Path("/home/mohammad/project/fitsho/backend/var/media/fitsho_food_catalogue.pdf")
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating PDF for {len(items)} items across {len(categories_data)} categories...")
    HTML(string=html_content).write_pdf(str(output_pdf_path))
    print(f"Saved PDF to {output_pdf_path} ({output_pdf_path.stat().st_size} bytes)")

    public_path = Path("/home/mohammad/project/fitsho/frontend/public/fitsho_food_catalogue.pdf")
    public_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_bytes(output_pdf_path.read_bytes())
    print(f"Copied to {public_path}")

    reports_path = Path("/home/mohammad/project/fitsho/reports/fitsho_food_catalogue.pdf")
    reports_path.parent.mkdir(parents=True, exist_ok=True)
    reports_path.write_bytes(output_pdf_path.read_bytes())
    print(f"Copied to {reports_path}")


if __name__ == "__main__":
    main()
