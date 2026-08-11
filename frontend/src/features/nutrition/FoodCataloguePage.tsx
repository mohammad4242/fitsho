import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import * as api from "./api";
import type { AdminFoodCatalogueItem, AdminFoodCatalogueResponse, FoodCatalogueItem, FoodCatalogueResponse } from "./api";
import "./foodCatalogue.css";

type LoadState = "loading" | "ready" | "error";

const primaryNutrientDefinitions = [
  ["energy_kcal", "کالری", "Calories", "kcal"],
  ["protein_g", "پروتئین", "Protein", "g"],
  ["carbohydrate_g", "کربوهیدرات", "Carbs", "g"],
  ["total_fat_g", "چربی", "Fat", "g"],
  ["fibre_g", "فیبر", "Fibre", "g"],
] as const;

const cardMacroDefinitions = primaryNutrientDefinitions.slice(1, 4);

export function FoodCataloguePage() {
  const { i18n } = useTranslation();
  const { user } = useAuth();
  const language = i18n.resolvedLanguage === "en" ? "en" : "fa";
  const fa = language === "fa";
  const l = (persian: string, english: string) => fa ? persian : english;
  const [state, setState] = useState<LoadState>("loading");
  const [data, setData] = useState<FoodCatalogueResponse | AdminFoodCatalogueResponse | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const [reload, setReload] = useState(0);
  const [details, setDetails] = useState<FoodCatalogueItem | null>(null);
  const [priceFood, setPriceFood] = useState<AdminFoodCatalogueItem | null>(null);
  const [imageFood, setImageFood] = useState<AdminFoodCatalogueItem | null>(null);
  const [addingFood, setAddingFood] = useState(false);

  useEffect(() => {
    let active = true;
    setState("loading");
    const getCatalogue = user?.is_admin ? api.getAdminFoodCatalogue : api.getFoodCatalogue;
    void getCatalogue({ query, category, page, pageSize: 24 })
      .then((result) => {
        if (!active) return;
        setData(result);
        setState("ready");
      })
      .catch(() => {
        if (active) setState("error");
      });
    return () => { active = false; };
  }, [category, page, query, reload, user?.is_admin]);

  function search(event: FormEvent) {
    event.preventDefault();
    setPage(1);
    setQuery(searchInput.trim());
  }

  function saved() {
    setAddingFood(false);
    setPriceFood(null);
    setImageFood(null);
    setReload((value) => value + 1);
  }

  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  return (
    <main className="food-catalogue-page fitsho-page" dir={fa ? "rtl" : "ltr"}>
      <section className="food-catalogue-hero">
        <div>
          <h1 className="fitsho-display">{l("کاتالوگ مواد غذایی", "Food catalogue")}</h1>
        </div>
        <Link className="food-catalogue-back" to="/nutrition-estimate">{l("تغذیه", "Nutrition")}</Link>
      </section>

      <section className="food-catalogue-toolbar" aria-label={l("جست‌وجو و فیلتر", "Search and filter")}>
        <form onSubmit={search} role="search">
          <label className="food-search-label" htmlFor="food-search">{l("جست‌وجوی ماده غذایی", "Search foods")}</label>
          <div>
            <input id="food-search" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder={l("مثلاً عدس یا سینه مرغ", "Try lentils or chicken breast")} />
            <button type="submit">{l("جست‌وجو", "Search")}</button>
          </div>
        </form>
        {user?.is_admin && <button aria-label={l("افزودن ماده غذایی", "Add food")} className="food-catalogue-add" type="button" onClick={() => setAddingFood(true)}>＋ {l("افزودن ماده غذایی", "Add food")}</button>}
        <nav className="food-category-chips" aria-label={l("گروه‌های غذایی", "Food categories")}>
          <button aria-pressed={category === ""} className={category === "" ? "is-active" : ""} onClick={() => { setCategory(""); setPage(1); }} type="button">{l("همه گروه‌ها", "All categories")}</button>
          {data?.categories.map((value) => <button aria-pressed={category === value} className={category === value ? "is-active" : ""} key={value} onClick={() => { setCategory(value); setPage(1); }} type="button">{categoryLabel(value, language)}</button>)}
        </nav>
      </section>

      {state === "loading" && <p className="food-catalogue-state" role="status">{l("در حال چیدن قفسه…", "Stocking the shelf…")}</p>}
      {state === "error" && <section className="food-catalogue-state" role="alert"><strong>{l("کاتالوگ دریافت نشد", "Catalogue unavailable")}</strong><button type="button" onClick={() => setReload((value) => value + 1)}>{l("تلاش دوباره", "Try again")}</button></section>}
      {state === "ready" && data?.items.length === 0 && <p className="food-catalogue-state">{l("ماده‌ای با این مشخصات پیدا نشد.", "No food matched these filters.")}</p>}
      {state === "ready" && data && data.items.length > 0 && (
        <section className="food-catalogue-grid" aria-label={l("مواد غذایی", "Foods")} role="list">
          {data.items.map((food) => <FoodCard food={food} key={food.id} language={language} onDetails={() => setDetails(food)} onImage={isAdminFood(food) ? () => setImageFood(food) : undefined} onPrice={isAdminFood(food) ? () => setPriceFood(food) : undefined} />)}
        </section>
      )}

      {state === "ready" && data && pageCount > 1 && <nav className="food-catalogue-pagination" aria-label={l("صفحه‌بندی", "Pagination")}><button disabled={page === 1} onClick={() => setPage((value) => value - 1)} type="button">{l("قبلی", "Previous")}</button><span>{formatNumber(page, language)} / {formatNumber(pageCount, language)}</span><button disabled={page === pageCount} onClick={() => setPage((value) => value + 1)} type="button">{l("بعدی", "Next")}</button></nav>}

      {details && <FoodDetails food={details} language={language} onClose={() => setDetails(null)} />}
      {priceFood && <PriceOverrideDialog food={priceFood} language={language} onClose={() => setPriceFood(null)} onSaved={saved} />}
      {imageFood && <FoodImageDialog food={imageFood} language={language} onClose={() => setImageFood(null)} onSaved={saved} />}
      {addingFood && <AddFoodDialog language={language} onClose={() => setAddingFood(false)} onSaved={saved} />}
    </main>
  );
}

function FoodCard({ food, language, onDetails, onImage, onPrice }: { food: FoodCatalogueItem; language: "fa" | "en"; onDetails: () => void; onImage?: () => void; onPrice?: () => void }) {
  const fa = language === "fa";
  const l = (persian: string, english: string) => fa ? persian : english;
  const portion = defaultPortion(food);
  return <article className="food-shelf-card" role="listitem">
    <FoodImage food={food} language={language} />
    <div className="food-shelf-card__content">
      <header><div className="food-shelf-card__identity"><span>{categoryLabel(food.category, language)}</span><h2>{fa ? food.name_fa : food.name_en}</h2><small>{fa ? food.name_en : food.name_fa}</small></div><div className="food-shelf-card__calories"><strong>{macroValue(scale(food.macros.energy_kcal, portion), "kcal", language)}</strong><span>{l("کالری", "Calories")}</span></div></header>
      <span className="food-shelf-card__basis">{basisLabel(portion, language)}</span>
      {isAdminFood(food) && <PriceTicket food={food} language={language} />}
      <div className="food-macro-strip">{cardMacroDefinitions.map(([code, faLabel, enLabel, unit]) => <div key={code}><strong>{macroValue(scale(food.macros[code], portion), unit, language)}</strong><span>{fa ? faLabel : enLabel}</span></div>)}</div>
      <footer><button type="button" onClick={onDetails}>{l("جزئیات بیشتر", "More details")}</button>{onImage && <button type="button" onClick={onImage} aria-label={l(`${food.image_url ? "جایگزینی" : "بارگذاری"} تصویر ${food.name_fa}`, `${food.image_url ? "Replace" : "Upload"} image for ${food.name_en}`)}>{l(food.image_url ? "جایگزینی تصویر" : "بارگذاری تصویر", food.image_url ? "Replace image" : "Upload image")}</button>}{onPrice && <button type="button" onClick={onPrice} aria-label={l(`ویرایش قیمت ${food.name_fa}`, `Edit price for ${food.name_en}`)}>{l("ویرایش قیمت", "Edit price")}</button>}</footer>
    </div>
  </article>;
}

function FoodImage({ food, language }: { food: FoodCatalogueItem; language: "fa" | "en" }) {
  const [failed, setFailed] = useState(false);
  const name = language === "fa" ? food.name_fa : food.name_en;
  useEffect(() => setFailed(false), [food.image_url]);
  if (!food.image_url || failed) {
    return <div className="food-shelf-card__image food-shelf-card__image--fallback" role="img" aria-label={language === "fa" ? `تصویر پیش‌فرض ${food.name_fa}` : `Default image for ${food.name_en}`}><span aria-hidden="true">◇</span></div>;
  }
  return <img className="food-shelf-card__image" src={food.image_url} alt={name} onError={() => setFailed(true)} />;
}

function FoodDetails({ food, language, onClose }: { food: FoodCatalogueItem; language: "fa" | "en"; onClose: () => void }) {
  const fa = language === "fa";
  const l = (persian: string, english: string) => fa ? persian : english;
  const name = fa ? food.name_fa : food.name_en;
  const [portion, setPortion] = useState(defaultPortion(food));
  return <div className="food-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section aria-label={l(`جزئیات ${food.name_fa}`, `${food.name_en} details`)} aria-modal="true" className="food-dialog" role="dialog"><button className="food-dialog__close" type="button" onClick={onClose} aria-label={l("بستن", "Close")}>×</button><p className="eyebrow eyebrow--accent">{l("ریز‌مغذی‌ها", "Micronutrients")}</p><h2>{name}</h2>{food.portions.length > 0 && <div className="food-basis-selector"><button type="button" className={portion ? "is-selected" : ""} onClick={() => setPortion(defaultPortion(food))}>{l("واحد معمول", "Common portion")}</button><button type="button" className={!portion ? "is-selected" : ""} onClick={() => setPortion(null)}>{l("۱۰۰ گرم", "100 g")}</button></div>}<p className="food-detail-basis">{basisLabel(portion, language)}{portion && ` · ${portionLabel(portion, language)} ≈ ${formatNumber(Number(portion.grams), language)} ${l("گرم", "g")}`}</p><div className="food-detail-grid">{food.nutrients.map((nutrient) => <article key={nutrient.nutrient_code}><span>{nutrientName(nutrient.nutrient_code, language)}</span><strong>{formatNumber(scale(nutrient.value_per_100g, portion) ?? 0, language)} {nutrient.unit}</strong></article>)}</div><footer><span>{l("منبع", "Source")}: {food.source.name}</span><a href={food.source.reference} target="_blank" rel="noreferrer">{l("مشاهده منبع", "View source")}</a></footer></section></div>;
}

function PriceTicket({ food, language }: { food: AdminFoodCatalogueItem; language: "fa" | "en" }) { const fa = language === "fa"; const l = (persian: string, english: string) => fa ? persian : english; return <div className={`food-price-ticket${food.price.status === "not_found" ? " is-missing" : ""}`}><span>{l("قیمت این هفته", "This week's price")}</span><strong>{food.price.status === "accepted" && food.price.reference_price_irr ? `${formatNumber(Number(food.price.reference_price_irr) / 10, language)} ${l("تومان", "Toman")}` : l("یافت نشد", "Not found")}</strong>{food.price.reference_unit && <small>{priceUnit(food.price.reference_unit, language)}</small>}{food.price.status === "accepted" && <small>{food.price.source === "manual_override" ? l("جایگزین موقت ادمین", "Temporary admin override") : l("به‌روزرسانی خودکار بازار", "Automatic market update")}{food.price.observed_at ? ` · ${formatDate(food.price.observed_at, language)}` : ""}</small>}</div>; }

function PriceOverrideDialog({ food, language, onClose, onSaved }: { food: AdminFoodCatalogueItem; language: "fa" | "en"; onClose: () => void; onSaved: () => void }) {
  const fa = language === "fa";
  const l = (persian: string, english: string) => fa ? persian : english;
  const [price, setPrice] = useState(food.price.reference_price_toman ?? "");
  const [unit, setUnit] = useState(food.price.canonical_unit ?? "TOMAN_PER_KG");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);
  function submit(event: FormEvent) { event.preventDefault(); setSaving(true); setError(false); void api.saveFoodPriceOverride(food.slug, { reference_price_toman: price, canonical_unit: unit, reason }).then(onSaved).catch(() => setError(true)).finally(() => setSaving(false)); }
  return <DialogFrame label={l(`ویرایش قیمت ${food.name_fa}`, `Edit price for ${food.name_en}`)} onClose={onClose}><h2>{l("قیمت دستی موقت", "Temporary manual price")}</h2><p>{l("این قیمت با اجرای موفق بعدی بازار منقضی می‌شود.", "This price expires after the next successful market refresh.")}</p><form className="food-admin-form" onSubmit={submit}><label>{l("قیمت (تومان)", "Price (Toman)")}<input inputMode="decimal" min="1" required value={price} onChange={(event) => setPrice(event.target.value)} /></label><label>{l("واحد", "Unit")}<select value={unit} onChange={(event) => setUnit(event.target.value)}><option value="TOMAN_PER_KG">{l("تومان/کیلوگرم", "Toman/kg")}</option><option value="TOMAN_PER_LITER">{l("تومان/لیتر", "Toman/litre")}</option><option value="TOMAN_PER_UNIT">{l("تومان/عدد", "Toman/unit")}</option></select></label><label>{l("دلیل ویرایش", "Reason")}<textarea minLength={5} required value={reason} onChange={(event) => setReason(event.target.value)} /></label>{error && <p role="alert">{l("قیمت ذخیره نشد.", "Price was not saved.")}</p>}<button disabled={saving} type="submit">{saving ? l("در حال ذخیره…", "Saving…") : l("ذخیره قیمت", "Save price")}</button></form></DialogFrame>;
}

function FoodImageDialog({ food, language, onClose, onSaved }: { food: AdminFoodCatalogueItem; language: "fa" | "en"; onClose: () => void; onSaved: () => void }) {
  const fa = language === "fa";
  const l = (persian: string, english: string) => fa ? persian : english;
  const [file, setFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setSaving(true);
    setError(false);
    void api.uploadCatalogueFoodImage(food.slug, file).then(onSaved).catch(() => setError(true)).finally(() => setSaving(false));
  }
  return <DialogFrame label={l(`تصویر ${food.name_fa}`, `Image for ${food.name_en}`)} onClose={onClose}><h2>{l(food.image_url ? "جایگزینی تصویر غذا" : "بارگذاری تصویر غذا", food.image_url ? "Replace food image" : "Upload food image")}</h2><p>{l("فایل JPEG، PNG، WebP یا GIF انتخاب کنید.", "Choose a JPEG, PNG, WebP, or GIF file.")}</p><form className="food-admin-form" onSubmit={submit}><label>{l("تصویر غذا", "Food image")}<input accept="image/gif,image/jpeg,image/png,image/webp" type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>{file && <p className="food-image-file">{file.name}</p>}{error && <p role="alert">{l("تصویر ذخیره نشد.", "Image was not saved.")}</p>}<button disabled={saving || !file} type="submit">{saving ? l("در حال ذخیره…", "Saving…") : l("ذخیره تصویر", "Save image")}</button></form></DialogFrame>;
}

function AddFoodDialog({ language, onClose, onSaved }: { language: "fa" | "en"; onClose: () => void; onSaved: () => void }) {
  const fa = language === "fa";
  const l = (persian: string, english: string) => fa ? persian : english;
  const [identity, setIdentity] = useState({ slug: "", name_fa: "", name_en: "", category: "", source_name: "", source_reference: "" });
  const [macros, setMacros] = useState<Record<string, string>>({ energy_kcal: "", protein_g: "", carbohydrate_g: "", total_fat_g: "", fibre_g: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);
  function submit(event: FormEvent) { event.preventDefault(); setSaving(true); setError(false); const nutrientUnits: Record<string, string> = { energy_kcal: "kcal", protein_g: "g", carbohydrate_g: "g", total_fat_g: "g", fibre_g: "g" }; void api.saveCatalogueFood({ ...identity, verification_status: "verified", measurement_basis: "as_purchased", canonical_quantity: 100, canonical_unit: "g", edible_portion: 1, data_version: "admin-verified-v1", source_food_id: null, source_access_date: new Date().toISOString().slice(0, 10), aliases: [], dietary_patterns: ["omnivore", "vegetarian", "vegan"], roles: ["flexible"], nutrients: Object.entries(macros).map(([nutrient_code, value_per_100g]) => ({ nutrient_code, value_per_100g: Number(value_per_100g), unit: nutrientUnits[nutrient_code], unit_form: "nutrient_mass", source_name: identity.source_name, source_reference: identity.source_reference, confidence: "high" })) }).then(onSaved).catch(() => setError(true)).finally(() => setSaving(false)); }
  return <DialogFrame label={l("افزودن ماده غذایی", "Add food")} onClose={onClose}><h2>{l("ماده غذایی تأییدشده", "Verified food")}</h2><p>{l("برای انتشار، مشخصات و پنج مقدار اصلی باید کامل باشند.", "Identity, provenance, and all five primary values are required.")}</p><form className="food-admin-form food-admin-form--wide" onSubmit={submit}>{(["slug", "name_fa", "name_en", "category", "source_name", "source_reference"] as const).map((field) => <label key={field}>{fieldLabel(field, language)}<input required type={field === "source_reference" ? "url" : "text"} value={identity[field]} onChange={(event) => setIdentity((value) => ({ ...value, [field]: event.target.value }))} /></label>)}{primaryNutrientDefinitions.map(([code, faLabel, enLabel, unit]) => <label key={code}>{fa ? faLabel : enLabel} ({unit})<input inputMode="decimal" min="0" required value={macros[code]} onChange={(event) => setMacros((value) => ({ ...value, [code]: event.target.value }))} /></label>)}{error && <p role="alert">{l("ماده غذایی ذخیره نشد.", "Food was not saved.")}</p>}<button disabled={saving} type="submit">{saving ? l("در حال ذخیره…", "Saving…") : l("افزودن به کاتالوگ", "Add to catalogue")}</button></form></DialogFrame>;
}

function DialogFrame({ children, label, onClose }: { children: ReactNode; label: string; onClose: () => void }) { return <div className="food-dialog-backdrop"><section aria-label={label} aria-modal="true" className="food-dialog" role="dialog"><button className="food-dialog__close" type="button" onClick={onClose} aria-label="Close">×</button>{children}</section></div>; }
function formatNumber(value: number, language: "fa" | "en") { return new Intl.NumberFormat(language === "fa" ? "fa-IR" : "en-US", { maximumFractionDigits: 1 }).format(value); }
function macroValue(value: string | number | null, unit: string, language: "fa" | "en") { return value === null ? "—" : `${formatNumber(Number(value), language)} ${language === "fa" && unit === "g" ? "گرم" : unit}`; }
function isAdminFood(food: FoodCatalogueItem): food is AdminFoodCatalogueItem { return "price" in food; }
function defaultPortion(food: FoodCatalogueItem) { return food.portions.find((portion) => portion.is_default) ?? null; }
function scale(value: string | number | null, portion: api.FoodCataloguePortion | null) { return value === null ? null : Number(value) * (portion ? Number(portion.grams) / 100 : 1); }
function portionLabel(portion: api.FoodCataloguePortion, language: "fa" | "en") { return language === "fa" ? portion.label_fa : portion.label_en; }
function basisLabel(portion: api.FoodCataloguePortion | null, language: "fa" | "en") { return portion ? `${language === "fa" ? "در " : "per "}${portionLabel(portion, language)}` : language === "fa" ? "در هر ۱۰۰ گرم" : "per 100 g"; }
function priceUnit(unit: string, language: "fa" | "en") { const labels: Record<string, [string, string]> = { IRR_PER_KG: ["تومان برای هر کیلوگرم", "Toman per kilogram"], IRR_PER_LITER: ["تومان برای هر لیتر", "Toman per litre"], IRR_PER_UNIT: ["تومان برای هر عدد", "Toman per unit"] }; return labels[unit]?.[language === "fa" ? 0 : 1] ?? unit; }
function formatDate(value: string, language: "fa" | "en") { return new Intl.DateTimeFormat(language === "fa" ? "fa-IR" : "en-US", { dateStyle: "short" }).format(new Date(value)); }
function nutrientName(code: string, language: "fa" | "en") { const labels: Record<string, [string, string]> = { energy_kcal: ["انرژی", "Energy"], protein_g: ["پروتئین", "Protein"], carbohydrate_g: ["کربوهیدرات", "Carbohydrate"], total_fat_g: ["چربی کل", "Total fat"], fibre_g: ["فیبر", "Fibre"], total_sugars_g: ["قند کل", "Total sugars"], saturated_fat_g: ["چربی اشباع", "Saturated fat"], calcium_mg: ["کلسیم", "Calcium"], iron_mg: ["آهن", "Iron"], zinc_mg: ["روی", "Zinc"], sodium_mg: ["سدیم", "Sodium"], potassium_mg: ["پتاسیم", "Potassium"], magnesium_mg: ["منیزیم", "Magnesium"], vitamin_c_mg: ["ویتامین C", "Vitamin C"], vitamin_d_mcg: ["ویتامین D", "Vitamin D"], vitamin_b12_mcg: ["ویتامین B12", "Vitamin B12"], folate_dfe_mcg: ["فولات", "Folate"] }; return labels[code]?.[language === "fa" ? 0 : 1] ?? code.replaceAll("_", " "); }
function categoryLabel(category: string, language: "fa" | "en") { const labels: Record<string, [string, string]> = { poultry: ["مرغ و ماکیان", "Poultry"], grains: ["غلات", "Grains"], legumes: ["حبوبات", "Legumes"], vegetables: ["سبزیجات", "Vegetables"], starchy_vegetables: ["سبزیجات نشاسته‌ای", "Starchy vegetables"], fruit: ["میوه", "Fruit"], dairy: ["لبنیات", "Dairy"], fats: ["چربی‌ها", "Fats"], nuts_seeds: ["مغزها و دانه‌ها", "Nuts & seeds"] }; return labels[category]?.[language === "fa" ? 0 : 1] ?? category.replaceAll("_", " "); }
function fieldLabel(field: string, language: "fa" | "en") { const labels: Record<string, [string, string]> = { slug: ["شناسه انگلیسی", "Slug"], name_fa: ["نام فارسی", "Persian name"], name_en: ["نام انگلیسی", "English name"], category: ["گروه غذایی", "Category"], source_name: ["نام منبع", "Source name"], source_reference: ["لینک منبع", "Source URL"] }; return labels[field][language === "fa" ? 0 : 1]; }
