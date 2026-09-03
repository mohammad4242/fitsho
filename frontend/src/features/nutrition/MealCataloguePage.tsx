import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import foodAccent from "../../assets/landing/food.webp";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import { MealThumbnail } from "../../shared/MealThumbnail";
import { getMealCatalogue, type MealCatalogueCategory, type MealCatalogueResponse } from "./api";
import "./mealCatalogue.css";

const CATEGORIES: MealCatalogueCategory[] = [
  "breakfast",
  "lunch",
  "post_workout",
  "snack",
  "dinner",
];

export function MealCataloguePage() {
  const { i18n, t } = useTranslation();
  const [selectedCategory, setSelectedCategory] = useState<MealCatalogueCategory | undefined>(undefined);
  const [data, setData] = useState<MealCatalogueResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [retry, setRetry] = useState(0);

  const english = i18n.resolvedLanguage === "en";

  useEffect(() => {
    let active = true;
    setState("loading");
    void getMealCatalogue(selectedCategory)
      .then((response) => {
        if (!active) return;
        setData(response);
        setState("ready");
      })
      .catch(() => {
        if (active) setState("error");
      });
    return () => {
      active = false;
    };
  }, [selectedCategory, retry]);

  return (
    <div className="meal-catalogue-shell" dir={english ? "ltr" : "rtl"}>
      <MemberHeaderMedia className="member-page-background" imageSrc={foodAccent} />
      <main className="meal-catalogue-page fitsho-page">
      <header className="meal-catalogue-hero">
        <p className="eyebrow eyebrow--accent">{t("mealCatalogue.eyebrow")}</p>
        <h1 className="fitsho-display">{t("mealCatalogue.title")}</h1>
        <p className="meal-catalogue-description">{t("mealCatalogue.intro")}</p>
      </header>

      <nav
        className="meal-catalogue-filters"
        aria-label={t("mealCatalogue.categoryFilter")}
        role="tablist"
      >
        <button
          aria-selected={selectedCategory === undefined}
          className={`meal-catalogue-chip ${selectedCategory === undefined ? "is-active" : ""}`}
          onClick={() => setSelectedCategory(undefined)}
          role="tab"
          type="button"
        >
          {t("mealCatalogue.allCategories")}
        </button>
        {CATEGORIES.map((category) => (
          <button
            aria-selected={selectedCategory === category}
            className={`meal-catalogue-chip ${selectedCategory === category ? "is-active" : ""}`}
            key={category}
            onClick={() => setSelectedCategory(category)}
            role="tab"
            type="button"
          >
            {t(`mealCatalogue.categories.${category}`)}
          </button>
        ))}
      </nav>

      {state === "loading" && (
        <p className="meal-catalogue-state" role="status">
          {t("mealCatalogue.loading")}
        </p>
      )}

      {state === "error" && (
        <section className="meal-catalogue-state meal-catalogue-state--error" role="alert">
          <p>{t("mealCatalogue.loadError")}</p>
          <button type="button" onClick={() => setRetry((value) => value + 1)}>
            {t("mealCatalogue.retry")}
          </button>
        </section>
      )}

      {state === "ready" && data?.items.length === 0 && (
        <p className="meal-catalogue-state meal-catalogue-state--empty">
          {t("mealCatalogue.empty")}
        </p>
      )}

      {state === "ready" && data !== null && data.items.length > 0 && (
        <section
          aria-label={t("mealCatalogue.title")}
          className="meal-catalogue-grid"
          role="list"
        >
          {data.items.map((meal) => {
            const name = english ? meal.name_en : meal.name_fa;
            return (
              <article className="meal-product-card" key={meal.id} role="listitem">
                <div className="meal-product-card__media">
                  <MealThumbnail
                    alt={name}
                    className="meal-product-card__image"
                    fallbackLabel={t("mealCatalogue.imageFallback", { name })}
                    imageUrl={meal.image_url}
                  />
                </div>
                <div className="meal-product-card__body">
                  <span className="meal-product-card__category">
                    {t(`mealCatalogue.categories.${meal.category}`)}
                  </span>
                  <h2 className="meal-product-card__title">{name}</h2>
                </div>
              </article>
            );
          })}
        </section>
      )}
    </main>
  </div>
  );
}
