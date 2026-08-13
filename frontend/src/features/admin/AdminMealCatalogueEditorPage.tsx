import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import foodAccent from "../../assets/landing/food.webp";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import type { AdminFoodCatalogueItem } from "../nutrition/api";
import {
  createAdminMeal,
  getAdminFoodCatalogue,
  getAdminMeal,
  previewAdminPreparedRecipe,
  updateAdminMeal,
} from "./api";
import type {
  AdminMealIngredientWrite,
  AdminMealWrite,
  AdminPreparedRecipe,
  MealCategory,
  MealIngredientRole,
  PreparedRecipePreview,
} from "./types";
import "./admin.css";

const categories: MealCategory[] = ["breakfast", "lunch", "post_workout", "snack", "dinner"];
const roles: Array<MealIngredientRole | ""> = ["", "protein", "carbohydrate", "fat", "fibre", "micronutrient_source"];
type IngredientForm = AdminMealIngredientWrite & { food_slug: string; food_name_fa: string; food_name_en: string };
type RecipeIngredientForm = AdminPreparedRecipe["ingredients"][number];
type MealForm = Omit<AdminMealWrite, "items" | "prepared_recipe" | "calculation_mode"> & { calculation_mode: "simple" | "prepared_recipe"; items: IngredientForm[]; prepared_recipe: AdminPreparedRecipe | null };

export function AdminMealCatalogueEditorPage() {
  const { i18n, t } = useTranslation();
  const { mealId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [form, setForm] = useState<MealForm>(() => emptyMeal(searchParams.get("category")));
  const [state, setState] = useState<"loading" | "ready" | "missing">(mealId ? "loading" : "ready");
  const [pickerTarget, setPickerTarget] = useState<"meal" | "recipe" | null>(null);
  const [search, setSearch] = useState("");
  const [foods, setFoods] = useState<AdminFoodCatalogueItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreparedRecipePreview | null>(null);
  const english = i18n.resolvedLanguage === "en";

  useEffect(() => {
    if (!mealId) return;
    let active = true;
    void getAdminMeal(mealId).then((meal) => {
      if (!active) return;
      setForm({ ...meal, calculation_mode: meal.calculation_mode ?? "simple", items: meal.items.map((item) => ({ ...item })), prepared_recipe: meal.prepared_recipe ? { ...meal.prepared_recipe, ingredients: meal.prepared_recipe.ingredients.map((item) => ({ ...item })) } : null });
      setState("ready");
    }).catch(() => { if (active) setState("missing"); });
    return () => { active = false; };
  }, [mealId]);

  useEffect(() => {
    if (!pickerTarget || search.trim().length < 2) { setFoods([]); return; }
    let active = true;
    void getAdminFoodCatalogue({ query: search.trim(), pageSize: 20 })
      .then((result) => { if (active) setFoods(result.items); })
      .catch(() => { if (active) setFoods([]); });
    return () => { active = false; };
  }, [pickerTarget, search]);

  useEffect(() => {
    const recipe = form.prepared_recipe;
    if (!recipe || recipe.ingredients.length === 0 || recipe.cooked_yield.final_cooked_yield_grams <= 0 || !recipe.source_name || !recipe.source_reference || !recipe.cooked_yield.source_name || !recipe.cooked_yield.source_reference) { setPreview(null); return; }
    const timer = window.setTimeout(() => {
      void previewAdminPreparedRecipe(recipePayload(recipe)).then(setPreview).catch(() => setPreview(null));
    }, 150);
    return () => window.clearTimeout(timer);
  }, [form.prepared_recipe]);

  function patchItem(index: number, patch: Partial<IngredientForm>) {
    setForm((current) => ({ ...current, items: current.items.map((item, position) => position === index ? { ...item, ...patch } : item) }));
  }

  function selectFood(food: AdminFoodCatalogueItem) {
    if (pickerTarget === "recipe") {
      setForm((current) => {
        const recipe = current.prepared_recipe;
        if (!recipe || recipe.ingredients.some((item) => item.food_id === food.id)) return current;
        const ingredient: RecipeIngredientForm = { food_id: food.id, food_slug: food.slug, food_name_fa: food.name_fa, food_name_en: food.name_en, reference_grams: 100, min_grams: 50, max_grams: 200, is_required: true };
        return { ...current, prepared_recipe: { ...recipe, ingredients: [...recipe.ingredients, ingredient] } };
      });
      setPickerTarget(null);
      setSearch("");
      return;
    }
    if (form.items.some((item) => item.food_id === food.id)) { setPickerTarget(null); return; }
    setForm((current) => ({
      ...current,
      items: [...current.items, {
        food_id: food.id,
        food_slug: food.slug,
        food_name_fa: food.name_fa,
        food_name_en: food.name_en,
        reference_grams: 100,
        min_grams: 50,
        max_grams: 200,
        is_required: true,
        functional_role: "protein",
      }],
    }));
    setPickerTarget(null);
    setSearch("");
  }

  async function save() {
    const recipeInvalid = form.calculation_mode === "prepared_recipe" && (!form.prepared_recipe || form.prepared_recipe.ingredients.length === 0 || form.prepared_recipe.cooked_yield.final_cooked_yield_grams <= 0 || form.prepared_recipe.ingredients.some((item) => item.min_grams < 0 || item.min_grams > item.reference_grams || item.reference_grams > item.max_grams || (item.is_required && item.min_grams <= 0)));
    if ((form.calculation_mode === "simple" && form.items.length === 0) || form.items.some((item) => item.min_grams <= 0 || item.min_grams > item.reference_grams || item.reference_grams > item.max_grams) || recipeInvalid) {
      setError(t("admin.mealEditor.boundsError"));
      return;
    }
    setSaving(true);
    setError(null);
    const payload: AdminMealWrite = {
      ...form,
      items: form.items.map(({ food_slug: _slug, food_name_fa: _fa, food_name_en: _en, ...item }) => item),
      prepared_recipe: form.prepared_recipe ? recipePayload(form.prepared_recipe) : null,
    };
    try {
      const saved = mealId ? await updateAdminMeal(mealId, payload) : await createAdminMeal(payload);
      navigate(`/admin/nutrition-meals/${saved.id}/edit`, { replace: true });
    } catch {
      setError(t("admin.mealEditor.saveError"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="admin-page">
      <MemberHeaderMedia imageSrc={foodAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="admin-main admin-main--template-editor admin-main--meal-editor">
        <header className="admin-form-header">
          <div><p className="eyebrow eyebrow--accent">{t("admin.mealEditor.eyebrow")}</p><h1>{mealId ? t("admin.mealEditor.titleEdit") : t("admin.mealEditor.titleNew")}</h1><p>{t("admin.mealEditor.intro")}</p></div>
          <Link to="/admin/nutrition-meals">{t("admin.mealEditor.back")}</Link>
        </header>
        {state === "loading" && <p className="admin-status" role="status">{t("admin.mealEditor.loading")}</p>}
        {state === "missing" && <p className="admin-status" role="alert">{t("admin.mealEditor.missing")}</p>}
        {state === "ready" && (
          <form className="admin-template-editor admin-meal-editor" noValidate onSubmit={(event) => { event.preventDefault(); void save(); }}>
            {error && <p className="admin-form-alert" role="alert">{error}</p>}
            <section>
              <h2>{t("admin.mealEditor.identity")}</h2>
              <div className="admin-template-editor-grid">
                <TextInput disabled={Boolean(mealId)} label={t("admin.mealEditor.code")} value={form.code} onChange={(code) => setForm((current) => ({ ...current, code: code.toUpperCase() }))} />
                <TextInput label={t("admin.mealEditor.nameFa")} value={form.name_fa} onChange={(name_fa) => setForm((current) => ({ ...current, name_fa }))} />
                <TextInput label={t("admin.mealEditor.nameEn")} value={form.name_en} onChange={(name_en) => setForm((current) => ({ ...current, name_en }))} />
                <label>{t("admin.mealEditor.category")}<select aria-label={t("admin.mealEditor.category")} value={form.category} onChange={(event) => setForm((current) => ({ ...current, category: event.target.value as MealCategory }))}>{categories.map((category) => <option key={category} value={category}>{t(`admin.meals.categories.${category}`)}</option>)}</select></label>
                <label>{t("admin.mealEditor.status")}<select aria-label={t("admin.mealEditor.status")} value={form.verification_status} onChange={(event) => setForm((current) => ({ ...current, verification_status: event.target.value as AdminMealWrite["verification_status"] }))}><option value="draft">{t("admin.meals.status.draft")}</option><option value="verified">{t("admin.meals.status.verified")}</option><option value="retired">{t("admin.meals.status.retired")}</option></select></label>
                <label className="admin-meal-required"><input aria-label={t("admin.mealEditor.preparedToggle")} checked={form.calculation_mode === "prepared_recipe"} onChange={(event) => setForm((current) => ({ ...current, calculation_mode: event.target.checked ? "prepared_recipe" : "simple", verification_status: event.target.checked ? "draft" : current.verification_status, prepared_recipe: event.target.checked ? current.prepared_recipe ?? emptyRecipe() : null }))} type="checkbox" />{t("admin.mealEditor.preparedToggle")}</label>
              </div>
            </section>
            {form.prepared_recipe && <RecipeEditor english={english} preview={preview} recipe={form.prepared_recipe} setRecipe={(prepared_recipe) => setForm((current) => ({ ...current, prepared_recipe }))} onPickFood={() => setPickerTarget("recipe")} />}
            <section className="admin-meal-editor-items">
              <h2>{t("admin.mealEditor.ingredients")}</h2>
              {form.items.map((item, index) => {
                const name = english ? item.food_name_en : item.food_name_fa;
                return <article className="admin-meal-editor-item" key={item.food_id}><header><strong>{name}</strong><button type="button" onClick={() => setForm((current) => ({ ...current, items: current.items.filter((_, position) => position !== index) }))}>{t("admin.mealEditor.remove")}</button></header><div className="admin-template-editor-grid admin-template-editor-grid--slot"><NumberInput label={t("admin.mealEditor.referenceAria", { name })} value={item.reference_grams} onChange={(reference_grams) => patchItem(index, { reference_grams })} /><NumberInput label={t("admin.mealEditor.minAria", { name })} value={item.min_grams} onChange={(min_grams) => patchItem(index, { min_grams })} /><NumberInput label={t("admin.mealEditor.maxAria", { name })} value={item.max_grams} onChange={(max_grams) => patchItem(index, { max_grams })} /><label>{t("admin.mealEditor.roleAria", { name })}<select aria-label={t("admin.mealEditor.roleAria", { name })} value={item.functional_role ?? ""} onChange={(event) => patchItem(index, { functional_role: (event.target.value || null) as MealIngredientRole | null })}>{roles.map((role) => <option key={role || "none"} value={role}>{role ? t(`admin.meals.roles.${role}`) : t("admin.meals.roles.none")}</option>)}</select></label><label className="admin-meal-required"><input aria-label={t("admin.mealEditor.requiredAria", { name })} checked={item.is_required} onChange={(event) => patchItem(index, { is_required: event.target.checked })} type="checkbox" />{t("admin.mealEditor.required")}</label></div></article>;
              })}
              <button className="admin-template-editor-add" onClick={() => setPickerTarget("meal")} type="button">{t("admin.mealEditor.addFood")}</button>
            </section>
            {pickerTarget && <section className="admin-template-exercise-picker" aria-label={t("admin.mealEditor.foodPicker")}><header><h2>{t("admin.mealEditor.foodPicker")}</h2><button type="button" onClick={() => setPickerTarget(null)}>{t("admin.mealEditor.close")}</button></header><input autoFocus onChange={(event) => setSearch(event.target.value)} placeholder={t("admin.mealEditor.searchPlaceholder")} value={search} /><div>{foods.map((food) => <button key={food.id} onClick={() => selectFood(food)} type="button">{t("admin.mealEditor.selectFood", { name: english ? food.name_en : food.name_fa })}</button>)}</div></section>}
            <footer className="admin-template-editor-actions"><span>{t("admin.mealEditor.boundsHint")}</span><button className="admin-primary-link" disabled={saving} type="submit">{saving ? t("admin.mealEditor.saving") : t("admin.mealEditor.save")}</button></footer>
          </form>
        )}
      </main>
    </div>
  );
}

function emptyMeal(rawCategory: string | null): MealForm {
  const category = categories.includes(rawCategory as MealCategory) ? rawCategory as MealCategory : "breakfast";
  return { code: "", name_fa: "", name_en: "", category, verification_status: "draft", calculation_mode: "simple", items: [], prepared_recipe: null };
}

function emptyRecipe(): AdminPreparedRecipe {
  return {
    verification_status: "draft",
    source_name: "",
    source_reference: "",
    notes: null,
    cooked_yield: { method: "proportional_reference_batch", final_cooked_yield_grams: 0, source_name: "", source_reference: "", notes: null },
    ingredients: [],
    ratios: [],
    data_gaps: [],
  };
}

function recipePayload(recipe: AdminPreparedRecipe): NonNullable<AdminMealWrite["prepared_recipe"]> {
  return {
    verification_status: recipe.verification_status,
    source_name: recipe.source_name,
    source_reference: recipe.source_reference,
    notes: recipe.notes,
    cooked_yield: {
      method: recipe.cooked_yield.method,
      final_cooked_yield_grams: recipe.cooked_yield.final_cooked_yield_grams,
      source_name: recipe.cooked_yield.source_name,
      source_reference: recipe.cooked_yield.source_reference,
      notes: recipe.cooked_yield.notes,
    },
    ingredients: recipe.ingredients.map(({ food_slug: _slug, food_name_fa: _fa, food_name_en: _en, ...item }) => item),
    ratios: recipe.ratios,
    data_gaps: recipe.data_gaps,
  };
}

function RecipeEditor({ english, preview, recipe, setRecipe, onPickFood }: { english: boolean; preview: PreparedRecipePreview | null; recipe: AdminPreparedRecipe; setRecipe: (recipe: AdminPreparedRecipe) => void; onPickFood: () => void }) {
  const { t } = useTranslation();
  const patchIngredient = (index: number, patch: Partial<RecipeIngredientForm>) => setRecipe({ ...recipe, ingredients: recipe.ingredients.map((item, position) => position === index ? { ...item, ...patch } : item) });
  const setSource = (field: "source_name" | "source_reference", value: string) => setRecipe({ ...recipe, [field]: value, cooked_yield: { ...recipe.cooked_yield, [field]: value } });
  const addRatio = () => {
    if (recipe.ingredients.length < 2) return;
    setRecipe({ ...recipe, ratios: [...recipe.ratios, { numerator_food_id: recipe.ingredients[0]!.food_id, denominator_food_id: recipe.ingredients[1]!.food_id, min_ratio: 0.1, max_ratio: 10 }] });
  };
  const addGap = () => setRecipe({ ...recipe, verification_status: "draft", data_gaps: [...recipe.data_gaps, { ingredient_name_fa: "", ingredient_name_en: "", message_fa: "در کاتالوگ مواد غذایی وجود ندارد", message_en: "Does not exist in Food Catalogue" }] });
  const patchGap = (index: number, field: "ingredient_name_fa" | "ingredient_name_en", value: string) => setRecipe({ ...recipe, data_gaps: recipe.data_gaps.map((gap, position) => position === index ? { ...gap, [field]: value, message_fa: `${field === "ingredient_name_fa" ? value : gap.ingredient_name_fa} در کاتالوگ مواد غذایی وجود ندارد`, message_en: `${field === "ingredient_name_en" ? value : gap.ingredient_name_en} does not exist in Food Catalogue` } : gap) });
  return <section className="admin-meal-editor-items admin-prepared-recipe"><h2>{t("admin.mealEditor.recipeTitle")}</h2><div className="admin-template-editor-grid"><TextInput label={t("admin.mealEditor.sourceName")} value={recipe.source_name} onChange={(value) => setSource("source_name", value)} /><TextInput label={t("admin.mealEditor.sourceReference")} value={recipe.source_reference} onChange={(value) => setSource("source_reference", value)} /><NumberInput label={t("admin.mealEditor.yieldGrams")} value={recipe.cooked_yield.final_cooked_yield_grams} onChange={(final_cooked_yield_grams) => setRecipe({ ...recipe, cooked_yield: { ...recipe.cooked_yield, final_cooked_yield_grams } })} /></div>{recipe.ingredients.map((item, index) => { const name = english ? item.food_name_en : item.food_name_fa; return <article className="admin-meal-editor-item" key={item.food_id}><header><strong>{name}</strong><button type="button" onClick={() => setRecipe({ ...recipe, ingredients: recipe.ingredients.filter((_, position) => position !== index), ratios: recipe.ratios.filter((ratio) => ratio.numerator_food_id !== item.food_id && ratio.denominator_food_id !== item.food_id) })}>{t("admin.mealEditor.remove")}</button></header><div className="admin-template-editor-grid"><NumberInput label={t("admin.mealEditor.referenceAria", { name })} value={item.reference_grams} onChange={(reference_grams) => patchIngredient(index, { reference_grams })} /><NumberInput label={t("admin.mealEditor.minAria", { name })} value={item.min_grams} onChange={(min_grams) => patchIngredient(index, { min_grams })} /><NumberInput label={t("admin.mealEditor.maxAria", { name })} value={item.max_grams} onChange={(max_grams) => patchIngredient(index, { max_grams })} /><label className="admin-meal-required"><input checked={item.is_required} onChange={(event) => patchIngredient(index, { is_required: event.target.checked })} type="checkbox" />{t("admin.mealEditor.required")}</label></div></article>; })}<button className="admin-template-editor-add" onClick={onPickFood} type="button">{t("admin.mealEditor.recipeIngredient")}</button><button className="admin-template-editor-add" disabled={recipe.ingredients.length < 2} onClick={addRatio} type="button">{t("admin.mealEditor.addRatio")}</button>{recipe.ratios.map((ratio, index) => <div className="admin-template-editor-grid" key={`${ratio.numerator_food_id}-${ratio.denominator_food_id}-${index}`}><label>Ratio numerator<select value={ratio.numerator_food_id} onChange={(event) => setRecipe({ ...recipe, ratios: recipe.ratios.map((item, position) => position === index ? { ...item, numerator_food_id: event.target.value } : item) })}>{recipe.ingredients.map((item) => <option key={item.food_id} value={item.food_id}>{english ? item.food_name_en : item.food_name_fa}</option>)}</select></label><label>Ratio denominator<select value={ratio.denominator_food_id} onChange={(event) => setRecipe({ ...recipe, ratios: recipe.ratios.map((item, position) => position === index ? { ...item, denominator_food_id: event.target.value } : item) })}>{recipe.ingredients.map((item) => <option key={item.food_id} value={item.food_id}>{english ? item.food_name_en : item.food_name_fa}</option>)}</select></label><NumberInput label="Minimum ratio" value={ratio.min_ratio} onChange={(min_ratio) => setRecipe({ ...recipe, ratios: recipe.ratios.map((item, position) => position === index ? { ...item, min_ratio } : item) })} /><NumberInput label="Maximum ratio" value={ratio.max_ratio} onChange={(max_ratio) => setRecipe({ ...recipe, ratios: recipe.ratios.map((item, position) => position === index ? { ...item, max_ratio } : item) })} /></div>)}<button className="admin-template-editor-add" onClick={addGap} type="button">{t("admin.mealEditor.addGap")}</button>{recipe.data_gaps.map((gap, index) => <article className="admin-recipe-gap" key={index}><div className="admin-template-editor-grid"><TextInput label={t("admin.mealEditor.gapNameFa")} value={gap.ingredient_name_fa} onChange={(value) => patchGap(index, "ingredient_name_fa", value)} /><TextInput label={t("admin.mealEditor.gapNameEn")} value={gap.ingredient_name_en} onChange={(value) => patchGap(index, "ingredient_name_en", value)} /></div><p>{english ? gap.message_en : gap.message_fa}</p></article>)}{preview && <aside className="admin-recipe-preview"><h3>{t("admin.mealEditor.preview")}</h3><strong>{formatEstimate(preview.nutrients_per_100g.energy_kcal ?? 0)} kcal / 100 g</strong>{Object.entries(preview.nutrients_per_100g).filter(([code]) => code !== "energy_kcal").map(([code, value]) => <span key={code}>{code}: {formatEstimate(value)}</span>)}{preview.estimated_cost_irr_per_100g !== null && <span>{formatEstimate(preview.estimated_cost_irr_per_100g)} IRR / 100 g</span>}</aside>}</section>;
}

function TextInput({ disabled = false, label, value, onChange }: { disabled?: boolean; label: string; value: string; onChange: (value: string) => void }) {
  return <label>{label}<input aria-label={label} disabled={disabled} required value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

function NumberInput({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return <label>{label}<input aria-label={label} min="0.1" step="0.1" type="number" value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>;
}

function formatEstimate(value: number): string {
  return String(Math.round((value + Number.EPSILON) * 1000) / 1000);
}
