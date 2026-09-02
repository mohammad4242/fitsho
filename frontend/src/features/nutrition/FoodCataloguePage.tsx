import { type FormEvent, type ReactNode, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import * as api from "./api";
import type { AdminFoodCatalogueItem, AdminFoodCatalogueResponse, FoodCatalogueItem, FoodCatalogueResponse } from "./api";
import "./foodCatalogue.css";

type LoadState = "loading" | "ready" | "error";
type PriceResearchState =
  | { status: "researching" }
  | { status: "error"; message: string };
type CataloguePriceReferenceUnit = NonNullable<AdminFoodCatalogueItem["price"]["reference_unit"]>;

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
  const [priceResearchStates, setPriceResearchStates] = useState<Record<string, PriceResearchState>>({});
  const [imageFood, setImageFood] = useState<AdminFoodCatalogueItem | null>(null);
  const [deleteFood, setDeleteFood] = useState<AdminFoodCatalogueItem | null>(null);
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

  function researchPrice(food: AdminFoodCatalogueItem) {
    if (priceResearchStates[food.slug]?.status === "researching") return;
    setPriceResearchStates((current) => ({ ...current, [food.slug]: { status: "researching" } }));
    void api.researchFoodPrice(food.slug, true)
      .then((result) => {
        const candidatePrice = result.candidate_reference_price_toman?.trim();
        const canonicalUnit = result.canonical_unit?.trim();
        const referenceUnit = canonicalUnit ? cataloguePriceReferenceUnit(canonicalUnit) : null;
        if (result.status === "success" && candidatePrice && canonicalUnit && referenceUnit) {
          setData((current) => updateAdminCataloguePrice(current, food.slug, candidatePrice, canonicalUnit, referenceUnit));
          setPriceResearchStates((current) => {
            const next = { ...current };
            delete next[food.slug];
            return next;
          });
          return;
        }
        const fallback = result.status === "no_quotes"
          ? l("قیمتی در فروشگاه‌های آنلاین برای این ماده غذایی یافت نشد.", "No prices were found in online stores.")
          : l("قیمت معتبر از سرویس استعلام دریافت نشد.", "The price inquiry service returned no valid price.");
        setPriceResearchStates((current) => ({
          ...current,
          [food.slug]: { status: "error", message: result.message?.trim() || fallback },
        }));
      })
      .catch((error: unknown) => {
        const fallback = l("خطا در برقراری ارتباط با سرویس استعلام قیمت.", "Failed to connect to the price inquiry service.");
        const message = error instanceof Error && error.message.trim() ? error.message : fallback;
        setPriceResearchStates((current) => ({ ...current, [food.slug]: { status: "error", message } }));
      });
  }

  function saved() {
    setAddingFood(false);
    setPriceFood(null);
    setImageFood(null);
    setReload((value) => value + 1);
  }

  function deleted() {
    setDeleteFood(null);
    if (page > 1 && data?.items.length === 1) {
      setPage((value) => value - 1);
      return;
    }
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
          {data.items.map((food) => (
            <FoodCard
              food={food}
              key={food.id}
              language={language}
              onDetails={() => setDetails(food)}
              onImage={isAdminFood(food) ? () => setImageFood(food) : undefined}
              onPrice={isAdminFood(food) ? () => setPriceFood(food) : undefined}
              onResearchPrice={isAdminFood(food) ? () => researchPrice(food) : undefined}
              researchState={isAdminFood(food) ? priceResearchStates[food.slug] : undefined}
              onDelete={isAdminFood(food) ? () => setDeleteFood(food) : undefined}
            />
          ))}
        </section>
      )}

      {state === "ready" && data && pageCount > 1 && <nav className="food-catalogue-pagination" aria-label={l("صفحه‌بندی", "Pagination")}><button disabled={page === 1} onClick={() => setPage((value) => value - 1)} type="button">{l("قبلی", "Previous")}</button><span>{formatNumber(page, language)} / {formatNumber(pageCount, language)}</span><button disabled={page === pageCount} onClick={() => setPage((value) => value + 1)} type="button">{l("بعدی", "Next")}</button></nav>}

      {details && <FoodDetails food={details} language={language} onClose={() => setDetails(null)} />}
      {priceFood && (
        <PriceOverrideDialog
          food={priceFood}
          language={language}
          onClose={() => setPriceFood(null)}
          onSaved={saved}
        />
      )}
      {imageFood && <FoodImageDialog food={imageFood} language={language} onClose={() => setImageFood(null)} onSaved={saved} />}
      {deleteFood && <DeleteFoodDialog food={deleteFood} language={language} onClose={() => setDeleteFood(null)} onDeleted={deleted} />}
      {addingFood && <AddFoodDialog language={language} onClose={() => setAddingFood(false)} onSaved={saved} />}
    </main>
  );
}

function FoodCard({ food, language, onDetails, onImage, onPrice, onResearchPrice, researchState, onDelete }: { food: FoodCatalogueItem; language: "fa" | "en"; onDetails: () => void; onImage?: () => void; onPrice?: () => void; onResearchPrice?: () => void; researchState?: PriceResearchState; onDelete?: () => void }) {
  const fa = language === "fa";
  const l = (persian: string, english: string) => fa ? persian : english;
  const portion = defaultPortion(food);
  const researching = researchState?.status === "researching";
  return <article className="food-shelf-card" role="listitem">
    <FoodImage food={food} language={language} />
    <div className="food-shelf-card__content">
      <header><div className="food-shelf-card__identity"><span>{categoryLabel(food.category, language)}</span><h2>{fa ? food.name_fa : food.name_en}</h2><small>{fa ? food.name_en : food.name_fa}</small></div><div className="food-shelf-card__calories"><strong>{macroValue(scale(food.macros.energy_kcal, portion), "kcal", language)}</strong><span>{l("کالری", "Calories")}</span></div></header>
      <span className="food-shelf-card__basis">{basisLabel(portion, language)}</span>
      {isAdminFood(food) && <PriceTicket food={food} language={language} researchState={researchState} />}
      <div className="food-macro-strip">{cardMacroDefinitions.map(([code, faLabel, enLabel, unit]) => <div key={code}><strong>{macroValue(scale(food.macros[code], portion), unit, language)}</strong><span>{fa ? faLabel : enLabel}</span></div>)}</div>
      <footer>
        <button type="button" onClick={onDetails}>{l("جزئیات بیشتر", "More details")}</button>
        {onImage && <button type="button" onClick={onImage} aria-label={l(`${food.image_url ? "جایگزینی" : "بارگذاری"} تصویر ${food.name_fa}`, `${food.image_url ? "Replace" : "Upload"} image for ${food.name_en}`)}>{l(food.image_url ? "جایگزینی تصویر" : "بارگذاری تصویر", food.image_url ? "Replace image" : "Upload image")}</button>}
        {onPrice && <button type="button" onClick={onPrice} aria-label={l(`ویرایش قیمت ${food.name_fa}`, `Edit price for ${food.name_en}`)}>{l("ویرایش قیمت", "Edit price")}</button>}
        {onResearchPrice && <button className="food-card-research" disabled={researching} type="button" onClick={onResearchPrice} aria-label={researching ? l(`در حال استعلام قیمت ${food.name_fa}`, `Inquiring price for ${food.name_en}`) : l(`استعلام قیمت ${food.name_fa}`, `Inquire price for ${food.name_en}`)}>{l("استعلام قیمت", "Inquire price")}</button>}
        {onDelete && <button className="food-card-delete" type="button" onClick={onDelete} aria-label={l(`حذف ${food.name_fa}`, `Delete ${food.name_en}`)}>{l("حذف", "Delete")}</button>}
      </footer>
    </div>
  </article>;
}

function DeleteFoodDialog({ food, language, onClose, onDeleted }: { food: AdminFoodCatalogueItem; language: "fa" | "en"; onClose: () => void; onDeleted: () => void }) {
  const fa = language === "fa";
  const l = (persian: string, english: string) => fa ? persian : english;
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(false);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (deleting) return;
    setDeleting(true);
    setError(false);
    void api.deleteCatalogueFood(food.slug)
      .then(onDeleted)
      .catch(() => setError(true))
      .finally(() => setDeleting(false));
  }

  return (
    <DialogFrame label={l("حذف ماده غذایی؟", "Delete food?")} onClose={onClose}>
      <p className="eyebrow eyebrow--accent">{l("اقدام مدیر", "Admin action")}</p>
      <h2>{l("حذف ماده غذایی؟", "Delete food?")}</h2>
      <p>{l(`«${food.name_fa}» از کاتالوگ فعال حذف شود؟`, `Remove “${food.name_en}” from the active catalogue?`)}</p>
      <p>{l("این ماده دیگر در کاتالوگ و برنامه‌های غذایی جدید استفاده نمی‌شود، اما اطلاعات و سوابق تاریخی آن حذف نخواهند شد.", "It will no longer be available for new nutrition plans. Historical records will be preserved.")}</p>
      <form className="food-delete-dialog" onSubmit={submit}>
        {error && <p className="food-delete-dialog__error" role="alert">{l("حذف ماده غذایی انجام نشد.", "Food deletion failed.")}</p>}
        <footer className="food-dialog__actions">
          <button disabled={deleting} type="button" onClick={onClose}>{l("انصراف", "Cancel")}</button>
          <button className="food-dialog-delete" disabled={deleting} type="submit">{deleting ? l("در حال حذف…", "Deleting…") : l("حذف ماده غذایی", "Delete food")}</button>
        </footer>
      </form>
    </DialogFrame>
  );
}

function FoodImage({ food, language }: { food: FoodCatalogueItem; language: "fa" | "en" }) {
  const [failure, setFailure] = useState<{ imageUrl: string | null; failed: boolean }>({
    imageUrl: food.image_url,
    failed: false,
  });
  const name = language === "fa" ? food.name_fa : food.name_en;
  const failed = failure.imageUrl === food.image_url && failure.failed;
  if (!food.image_url || failed) {
    return <div className="food-shelf-card__image food-shelf-card__image--fallback" role="img" aria-label={language === "fa" ? `تصویر پیش‌فرض ${food.name_fa}` : `Default image for ${food.name_en}`}><span aria-hidden="true">◇</span></div>;
  }
  return <img className="food-shelf-card__image" src={food.image_url} alt={name} onError={() => setFailure({ imageUrl: food.image_url, failed: true })} />;
}

function FoodDetails({ food, language, onClose }: { food: FoodCatalogueItem; language: "fa" | "en"; onClose: () => void }) {
  const fa = language === "fa";
  const l = (persian: string, english: string) => fa ? persian : english;
  const name = fa ? food.name_fa : food.name_en;
  const [portion, setPortion] = useState(defaultPortion(food));
  return <div className="food-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section aria-label={l(`جزئیات ${food.name_fa}`, `${food.name_en} details`)} aria-modal="true" className="food-dialog" role="dialog"><button className="food-dialog__close" type="button" onClick={onClose} aria-label={l("بستن", "Close")}>×</button><p className="eyebrow eyebrow--accent">{l("ریز‌مغذی‌ها", "Micronutrients")}</p><h2>{name}</h2>{food.portions.length > 0 && <div className="food-basis-selector"><button type="button" className={portion ? "is-selected" : ""} onClick={() => setPortion(defaultPortion(food))}>{l("واحد معمول", "Common portion")}</button><button type="button" className={!portion ? "is-selected" : ""} onClick={() => setPortion(null)}>{l("۱۰۰ گرم", "100 g")}</button></div>}<p className="food-detail-basis">{basisLabel(portion, language)}{portion && ` · ${portionLabel(portion, language)} ≈ ${formatNumber(Number(portion.grams), language)} ${l("گرم", "g")}`}</p><div className="food-detail-grid">{food.nutrients.map((nutrient) => <article key={nutrient.nutrient_code}><span>{nutrientName(nutrient.nutrient_code, language)}</span><strong>{formatNumber(scale(nutrient.value_per_100g, portion) ?? 0, language)} {nutrient.unit}</strong></article>)}</div><footer><span>{l("منبع", "Source")}: {food.source.name}</span><a href={food.source.reference} target="_blank" rel="noreferrer">{l("مشاهده منبع", "View source")}</a></footer></section></div>;
}

function PriceTicket({ food, language, researchState }: { food: AdminFoodCatalogueItem; language: "fa" | "en"; researchState?: PriceResearchState }) {
  const fa = language === "fa";
  const l = (persian: string, english: string) => fa ? persian : english;
  const researching = researchState?.status === "researching";
  const priceInToman = food.price.reference_price_toman
    ? Number(food.price.reference_price_toman)
    : food.price.reference_price_irr
      ? Number(food.price.reference_price_irr) / 10
      : null;
  const hasPrice = food.price.status === "accepted" && priceInToman !== null;
  const className = [
    "food-price-ticket",
    food.price.status === "not_found" ? "is-missing" : "",
    researching ? "is-researching" : "",
    researchState?.status === "error" ? "is-error" : "",
  ].filter(Boolean).join(" ");
  return (
    <div className={className} aria-live={researching ? "polite" : undefined}>
      <span>{researching ? l("وضعیت استعلام", "Inquiry status") : l("قیمت این هفته", "This week's price")}</span>
      {researching
        ? <strong role="status">{l("در حال استعلام…", "Price inquiry in progress…")}</strong>
        : <strong>{hasPrice ? `${formatNumber(priceInToman, language)} ${l("تومان", "Toman")}` : l("یافت نشد", "Not found")}</strong>}
      {!researching && food.price.reference_unit && hasPrice && <small>{priceUnit(food.price.reference_unit, language)}</small>}
      {!researching && hasPrice && <small>{food.price.source === "manual_override" ? l("جایگزین موقت ادمین", "Temporary admin override") : l("به‌روزرسانی خودکار بازار", "Automatic market update")}{food.price.observed_at ? ` · ${formatDate(food.price.observed_at, language)}` : ""}</small>}
      {researchState?.status === "error" && <small className="food-price-ticket__error" role="alert">{researchState.message}</small>}
    </div>
  );
}

function PriceOverrideDialog({
  food,
  language,
  onClose,
  onSaved,
}: {
  food: AdminFoodCatalogueItem;
  language: "fa" | "en";
  onClose: () => void;
  onSaved: () => void;
}) {
  const fa = language === "fa";
  const l = (persian: string, english: string) => (fa ? persian : english);
  const [price, setPrice] = useState(food.price.reference_price_toman ?? "");
  const [unit, setUnit] = useState(food.price.canonical_unit ?? "TOMAN_PER_KG");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);

  const [researching, setResearching] = useState(false);
  const [researchResult, setResearchResult] = useState<api.SingleFoodPriceResearchResponse | null>(null);
  const [researchError, setResearchError] = useState<string | null>(null);

  const runResearch = useCallback(async () => {
    setResearching(true);
    setResearchError(null);
    try {
      const res = await api.researchFoodPrice(food.slug);
      setResearchResult(res);
      if (res.status === "success" && res.candidate_reference_price_toman) {
        setPrice(String(res.candidate_reference_price_toman));
        if (res.canonical_unit) {
          setUnit(res.canonical_unit);
        }
        setReason((prev) => prev || (fa ? "استعلام خودکار از فروشگاه‌های آنلاین توسط ایجنت" : "Automated AI online market inquiry"));
      } else if (res.status === "failed" || res.status === "no_quotes") {
        setResearchError(res.message || (fa ? "قیمتی در فروشگاه‌ها یافت نشد." : "No prices found in online stores."));
      }
    } catch {
      setResearchError(fa ? "خطا در برقراری ارتباط با سرویس استعلام قیمت." : "Failed to connect to price inquiry service.");
    } finally {
      setResearching(false);
    }
  }, [fa, food.slug]);

  function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(false);
    void api
      .saveFoodPriceOverride(food.slug, { reference_price_toman: price, canonical_unit: unit, reason })
      .then(onSaved)
      .catch(() => setError(true))
      .finally(() => setSaving(false));
  }

  return (
    <DialogFrame label={l(`ویرایش قیمت ${food.name_fa}`, `Edit price for ${food.name_en}`)} onClose={onClose}>
      <h2>{l("قیمت و استعلام هوشمند", "Price & AI Inquiry")}</h2>
      <p>{l("این قیمت با اجرای موفق بعدی بازار منقضی می‌شود.", "This price expires after the next successful market refresh.")}</p>

      <div className="food-ai-research-box">
        <button
          type="button"
          className="food-ai-research-btn"
          disabled={researching || saving}
          onClick={() => void runResearch()}
        >
          {researching
            ? l("در حال جستجوی آنلاین قیمت… (ممکن است ۱ تا ۲ دقیقه طول بکشد)", "Searching online markets… (1-2 min)")
            : l("⚡ استعلام هوشمند قیمت با ایجنت", "⚡ AI Price Inquiry with Agent")}
        </button>

        {researchError && <p className="food-ai-research-error" role="alert">{researchError}</p>}

        {researchResult && researchResult.quotes.length > 0 && (
          <div className="food-ai-quotes">
            <h4>{l("قیمت‌های کشف‌شده در فروشگاه‌ها:", "Discovered store quotes:")}</h4>
            <ul>
              {researchResult.quotes.map((q, idx) => (
                <li key={idx}>
                  <a href={q.source_url} target="_blank" rel="noreferrer">
                    {q.source_name} ({q.source_domain}):
                  </a>{" "}
                  <strong>
                    {formatNumber(Number(q.normal_price_toman), language)} {l("تومان", "Toman")}
                  </strong>{" "}
                  <small>({formatNumber(Number(q.package_quantity), language)} {q.package_unit})</small>
                </li>
              ))}
            </ul>
            {researchResult.candidate_reference_price_toman && (
              <p className="food-ai-suggested-badge">
                {l("قیمت پیشنهادی بازار:", "Suggested market price:")}{" "}
                <strong>
                  {formatNumber(Number(researchResult.candidate_reference_price_toman), language)}{" "}
                  {l("تومان", "Toman")}
                </strong>
              </p>
            )}
          </div>
        )}
      </div>

      <form className="food-admin-form" onSubmit={submit}>
        <label>
          {l("قیمت (تومان)", "Price (Toman)")}
          <input
            inputMode="decimal"
            min="1"
            required
            value={price}
            onChange={(event) => setPrice(event.target.value)}
          />
        </label>
        <label>
          {l("واحد", "Unit")}
          <select value={unit} onChange={(event) => setUnit(event.target.value)}>
            <option value="TOMAN_PER_KG">{l("تومان/کیلوگرم", "Toman/kg")}</option>
            <option value="TOMAN_PER_LITER">{l("تومان/لیتر", "Toman/litre")}</option>
            <option value="TOMAN_PER_UNIT">{l("تومان/عدد", "Toman/unit")}</option>
          </select>
        </label>
        <label>
          {l("دلیل ویرایش", "Reason")}
          <textarea
            minLength={5}
            required
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        {error && <p role="alert">{l("قیمت ذخیره نشد.", "Price was not saved.")}</p>}
        <button disabled={saving || researching} type="submit">
          {saving ? l("در حال ذخیره…", "Saving…") : l("ذخیره قیمت", "Save price")}
        </button>
      </form>
    </DialogFrame>
  );
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
function cataloguePriceReferenceUnit(unit: string): CataloguePriceReferenceUnit | null {
  const units: Record<string, CataloguePriceReferenceUnit> = {
    TOMAN_PER_KG: "IRR_PER_KG",
    TOMAN_PER_LITER: "IRR_PER_LITER",
    TOMAN_PER_UNIT: "IRR_PER_UNIT",
  };
  return units[unit] ?? null;
}
function updateAdminCataloguePrice(
  current: FoodCatalogueResponse | AdminFoodCatalogueResponse | null,
  slug: string,
  referencePriceToman: string,
  canonicalUnit: string,
  referenceUnit: CataloguePriceReferenceUnit,
) {
  if (!current) return current;
  return {
    ...current,
    items: current.items.map((item) => {
      if (!isAdminFood(item) || item.slug !== slug) return item;
      return {
        ...item,
        price: {
          status: "accepted" as const,
          reference_price_toman: referencePriceToman,
          canonical_unit: canonicalUnit,
          reference_unit: referenceUnit,
          source: "manual_override" as const,
        },
      };
    }),
  };
}
function defaultPortion(food: FoodCatalogueItem) { return food.portions.find((portion) => portion.is_default) ?? null; }
function scale(value: string | number | null, portion: api.FoodCataloguePortion | null) { return value === null ? null : Number(value) * (portion ? Number(portion.grams) / 100 : 1); }
function portionLabel(portion: api.FoodCataloguePortion, language: "fa" | "en") { return language === "fa" ? portion.label_fa : portion.label_en; }
function basisLabel(portion: api.FoodCataloguePortion | null, language: "fa" | "en") { return portion ? `${language === "fa" ? "در " : "per "}${portionLabel(portion, language)}` : language === "fa" ? "در هر ۱۰۰ گرم" : "per 100 g"; }
function priceUnit(unit: string, language: "fa" | "en") { const labels: Record<string, [string, string]> = { IRR_PER_KG: ["تومان برای هر کیلوگرم", "Toman per kilogram"], IRR_PER_LITER: ["تومان برای هر لیتر", "Toman per litre"], IRR_PER_UNIT: ["تومان برای هر عدد", "Toman per unit"] }; return labels[unit]?.[language === "fa" ? 0 : 1] ?? unit; }
function formatDate(value: string, language: "fa" | "en") { return new Intl.DateTimeFormat(language === "fa" ? "fa-IR" : "en-US", { dateStyle: "short" }).format(new Date(value)); }
function nutrientName(code: string, language: "fa" | "en") { const labels: Record<string, [string, string]> = { energy_kcal: ["انرژی", "Energy"], protein_g: ["پروتئین", "Protein"], carbohydrate_g: ["کربوهیدرات", "Carbohydrate"], total_fat_g: ["چربی کل", "Total fat"], fibre_g: ["فیبر", "Fibre"], total_sugars_g: ["قند کل", "Total sugars"], saturated_fat_g: ["چربی اشباع", "Saturated fat"], calcium_mg: ["کلسیم", "Calcium"], iron_mg: ["آهن", "Iron"], zinc_mg: ["روی", "Zinc"], copper_mg: ["مس", "Copper"], sodium_mg: ["سدیم", "Sodium"], potassium_mg: ["پتاسیم", "Potassium"], magnesium_mg: ["منیزیم", "Magnesium"], vitamin_c_mg: ["ویتامین C", "Vitamin C"], vitamin_d_mcg: ["ویتامین D", "Vitamin D"], vitamin_b12_mcg: ["ویتامین B12", "Vitamin B12"], folate_dfe_mcg: ["فولات", "Folate"] }; return labels[code]?.[language === "fa" ? 0 : 1] ?? code.replaceAll("_", " "); }
function categoryLabel(category: string, language: "fa" | "en") { const labels: Record<string, [string, string]> = { poultry: ["مرغ و ماکیان", "Poultry"], grains: ["غلات", "Grains"], legumes: ["حبوبات", "Legumes"], vegetables: ["سبزیجات", "Vegetables"], starchy_vegetables: ["سبزیجات نشاسته‌ای", "Starchy vegetables"], fruit: ["میوه", "Fruit"], dairy: ["لبنیات", "Dairy"], fats: ["چربی‌ها", "Fats"], nuts_seeds: ["مغزها و دانه‌ها", "Nuts & seeds"] }; return labels[category]?.[language === "fa" ? 0 : 1] ?? category.replaceAll("_", " "); }
function fieldLabel(field: string, language: "fa" | "en") { const labels: Record<string, [string, string]> = { slug: ["شناسه انگلیسی", "Slug"], name_fa: ["نام فارسی", "Persian name"], name_en: ["نام انگلیسی", "English name"], category: ["گروه غذایی", "Category"], source_name: ["نام منبع", "Source name"], source_reference: ["لینک منبع", "Source URL"] }; return labels[field][language === "fa" ? 0 : 1]; }
