import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import foodAccent from "../../assets/landing/food.webp";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import { MealThumbnail } from "../../shared/MealThumbnail";
import { getAdminMealCatalogue, uploadAdminMealImage } from "./api";
import type { AdminMealCatalogueItem, AdminMealCatalogueResponse, MealCategory } from "./types";
import "./admin.css";

const categories: MealCategory[] = ["breakfast", "lunch", "post_workout", "snack", "dinner"];

export function AdminMealCataloguePage() {
  const { i18n, t } = useTranslation();
  const [category, setCategory] = useState<MealCategory>("breakfast");
  const [page, setPage] = useState<AdminMealCatalogueResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [retry, setRetry] = useState(0);
  const [imageMeal, setImageMeal] = useState<AdminMealCatalogueItem | null>(null);
  const english = i18n.resolvedLanguage === "en";
  const number = new Intl.NumberFormat(english ? "en" : "fa-IR", { maximumFractionDigits: 1 });

  useEffect(() => {
    let active = true;
    setState("loading");
    void getAdminMealCatalogue(category)
      .then((result) => {
        if (!active) return;
        setPage(result);
        setState("ready");
      })
      .catch(() => { if (active) setState("error"); });
    return () => { active = false; };
  }, [category, retry]);

  return (
    <div className="admin-page">
      <MemberHeaderMedia imageSrc={foodAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="admin-main admin-main--templates admin-main--meal-catalogue">
        <header className="admin-hero">
          <div>
            <p className="eyebrow eyebrow--accent">{t("admin.meals.eyebrow")}</p>
            <h1 className="fitsho-display">{t("admin.meals.title")}</h1>
            <p>{t("admin.meals.intro")}</p>
          </div>
        </header>

        <div className="admin-template-filters">
          <div className="admin-template-filter-group">
            <span>{t("admin.meals.categoryFilter")}</span>
            <div className="admin-template-tabs admin-meal-category-tabs" role="tablist" aria-label={t("admin.meals.categoryFilter")}>
              {categories.map((item) => (
                <button
                  aria-selected={item === category}
                  key={item}
                  onClick={() => setCategory(item)}
                  role="tab"
                  type="button"
                >
                  {t(`admin.meals.categories.${item}`)}
                </button>
              ))}
            </div>
          </div>
        </div>

        {state === "loading" && <p className="admin-status" role="status">{t("admin.meals.loading")}</p>}
        {state === "error" && <div className="admin-status" role="alert"><p>{t("admin.meals.loadError")}</p><button type="button" onClick={() => setRetry((value) => value + 1)}>{t("common.retry")}</button></div>}
        {state === "ready" && page?.items.length === 0 && <p className="admin-status">{t("admin.meals.empty")}</p>}
        {state === "ready" && page !== null && page.items.length > 0 && (
          <section className="admin-template-list admin-meal-list" role="tabpanel">
            {page.items.map((meal) => (
              <article className="admin-template-card admin-meal-card" key={meal.id}>
                <header>
                  <div className="admin-meal-card__identity">
                    <MealThumbnail
                      alt={english ? meal.name_en : meal.name_fa}
                      className="admin-meal-card__image"
                      fallbackLabel={t("admin.meals.imageFallback", { name: english ? meal.name_en : meal.name_fa })}
                      imageUrl={meal.image_url}
                    />
                    <div>
                    <p className="eyebrow">{meal.code} · {t(`admin.meals.categories.${meal.category}`)}</p>
                    <h2>{english ? meal.name_en : meal.name_fa}</h2>
                    </div>
                  </div>
                  <span className={`admin-meal-status admin-meal-status--${meal.verification_status}`}>
                    {t(`admin.meals.status.${meal.verification_status}`)}
                  </span>
                </header>
                <ul className="admin-meal-ingredients">
                  {meal.items.map((item) => (
                    <li key={item.food_id}>
                      <div><strong>{english ? item.food_name_en : item.food_name_fa}</strong><small>{item.functional_role ? t(`admin.meals.roles.${item.functional_role}`) : t("admin.meals.roles.none")}</small></div>
                      <span>{t("admin.meals.bounds", { min: number.format(item.min_grams), max: number.format(item.max_grams) })}</span>
                      <span>{item.is_required ? t("admin.meals.required") : t("admin.meals.optional")}</span>
                    </li>
                  ))}
                </ul>
                <footer>
                  <Link aria-label={t("admin.meals.editAria", { name: english ? meal.name_en : meal.name_fa })} to={`/admin/nutrition-meals/${meal.id}/edit`}>{t("admin.meals.edit")}</Link>
                  <button aria-label={t("admin.meals.imageActionAria", { action: t(meal.image_url ? "admin.meals.replaceImage" : "admin.meals.uploadImage"), name: english ? meal.name_en : meal.name_fa })} type="button" onClick={() => setImageMeal(meal)}>{t(meal.image_url ? "admin.meals.replaceImage" : "admin.meals.uploadImage")}</button>
                  <span>{t("admin.meals.referenceNote")}</span>
                </footer>
              </article>
            ))}
          </section>
        )}
        {state === "ready" && <div className="admin-template-add-program"><Link className="admin-primary-link" to={`/admin/nutrition-meals/new?category=${category}`}>{t("admin.meals.add")}</Link></div>}
      </main>
      {imageMeal && (
        <MealImageDialog
          meal={imageMeal}
          onClose={() => setImageMeal(null)}
          onSaved={(imageUrl) => {
            setPage((current) => current === null ? current : {
              ...current,
              items: current.items.map((meal) => meal.id === imageMeal.id ? { ...meal, image_url: imageUrl } : meal),
            });
            setImageMeal(null);
          }}
        />
      )}
    </div>
  );
}

function MealImageDialog({ meal, onClose, onSaved }: {
  meal: AdminMealCatalogueItem;
  onClose: () => void;
  onSaved: (imageUrl: string) => void;
}) {
  const { i18n, t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);
  const name = i18n.resolvedLanguage === "en" ? meal.name_en : meal.name_fa;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setSaving(true);
    setError(false);
    try {
      const saved = await uploadAdminMealImage(meal.id, file);
      onSaved(saved.image_url);
    } catch {
      setError(true);
      setSaving(false);
    }
  }

  return (
    <div className="admin-meal-image-dialog" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section aria-label={t("admin.meals.imageDialog", { name })} role="dialog" aria-modal="true">
        <header><h2>{t(meal.image_url ? "admin.meals.replaceImage" : "admin.meals.uploadImage")}</h2><button aria-label={t("admin.meals.closeImage")} type="button" onClick={onClose}>×</button></header>
        <p>{t("admin.meals.imageHint")}</p>
        <form onSubmit={(event) => void submit(event)}>
          <label>{t("admin.meals.imageInput")}<input accept="image/gif,image/jpeg,image/png,image/webp" type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
          {file && <small>{file.name}</small>}
          {error && <p role="alert">{t("admin.meals.imageError")}</p>}
          <button disabled={saving || !file} type="submit">{saving ? t("admin.meals.savingImage") : t("admin.meals.saveImage")}</button>
        </form>
      </section>
    </div>
  );
}
