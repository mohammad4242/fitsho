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
  updateAdminMeal,
} from "./api";
import type {
  AdminMealIngredientWrite,
  AdminMealWrite,
  MealCategory,
  MealIngredientRole,
} from "./types";
import "./admin.css";

const categories: MealCategory[] = ["breakfast", "lunch", "post_workout", "snack", "dinner"];
const roles: Array<MealIngredientRole | ""> = ["", "protein", "carbohydrate", "fat", "fibre", "micronutrient_source"];
type IngredientForm = AdminMealIngredientWrite & { food_slug: string; food_name_fa: string; food_name_en: string };
type MealForm = Omit<AdminMealWrite, "items"> & { items: IngredientForm[] };

export function AdminMealCatalogueEditorPage() {
  const { i18n, t } = useTranslation();
  const { mealId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [form, setForm] = useState<MealForm>(() => emptyMeal(searchParams.get("category")));
  const [state, setState] = useState<"loading" | "ready" | "missing">(mealId ? "loading" : "ready");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [foods, setFoods] = useState<AdminFoodCatalogueItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const english = i18n.resolvedLanguage === "en";

  useEffect(() => {
    if (!mealId) return;
    let active = true;
    void getAdminMeal(mealId).then((meal) => {
      if (!active) return;
      setForm({ ...meal, items: meal.items.map((item) => ({ ...item })) });
      setState("ready");
    }).catch(() => { if (active) setState("missing"); });
    return () => { active = false; };
  }, [mealId]);

  useEffect(() => {
    if (!pickerOpen || search.trim().length < 2) { setFoods([]); return; }
    let active = true;
    void getAdminFoodCatalogue({ query: search.trim(), pageSize: 20 })
      .then((result) => { if (active) setFoods(result.items); })
      .catch(() => { if (active) setFoods([]); });
    return () => { active = false; };
  }, [pickerOpen, search]);

  function patchItem(index: number, patch: Partial<IngredientForm>) {
    setForm((current) => ({ ...current, items: current.items.map((item, position) => position === index ? { ...item, ...patch } : item) }));
  }

  function selectFood(food: AdminFoodCatalogueItem) {
    if (form.items.some((item) => item.food_id === food.id)) { setPickerOpen(false); return; }
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
    setPickerOpen(false);
    setSearch("");
  }

  async function save() {
    if (form.items.length === 0 || form.items.some((item) => item.min_grams <= 0 || item.min_grams > item.reference_grams || item.reference_grams > item.max_grams)) {
      setError(t("admin.mealEditor.boundsError"));
      return;
    }
    setSaving(true);
    setError(null);
    const payload: AdminMealWrite = {
      ...form,
      items: form.items.map(({ food_slug: _slug, food_name_fa: _fa, food_name_en: _en, ...item }) => item),
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
                <TextInput label={t("admin.mealEditor.nameFa")} value={form.name_fa} onChange={(name_fa) => setForm((current) => ({ ...current, name_fa }))} />
                <TextInput label={t("admin.mealEditor.nameEn")} value={form.name_en} onChange={(name_en) => setForm((current) => ({ ...current, name_en }))} />
                <label>{t("admin.mealEditor.category")}<select aria-label={t("admin.mealEditor.category")} value={form.category} onChange={(event) => setForm((current) => ({ ...current, category: event.target.value as MealCategory }))}>{categories.map((category) => <option key={category} value={category}>{t(`admin.meals.categories.${category}`)}</option>)}</select></label>
                <label>{t("admin.mealEditor.status")}<select aria-label={t("admin.mealEditor.status")} value={form.verification_status} onChange={(event) => setForm((current) => ({ ...current, verification_status: event.target.value as AdminMealWrite["verification_status"] }))}><option value="draft">{t("admin.meals.status.draft")}</option><option value="verified">{t("admin.meals.status.verified")}</option><option value="retired">{t("admin.meals.status.retired")}</option></select></label>
              </div>
            </section>
            <section className="admin-meal-editor-items">
              <h2>{t("admin.mealEditor.ingredients")}</h2>
              {form.items.map((item, index) => {
                const name = english ? item.food_name_en : item.food_name_fa;
                return <article className="admin-meal-editor-item" key={item.food_id}><header><strong>{name}</strong><button type="button" onClick={() => setForm((current) => ({ ...current, items: current.items.filter((_, position) => position !== index) }))}>{t("admin.mealEditor.remove")}</button></header><div className="admin-template-editor-grid admin-template-editor-grid--slot"><NumberInput label={t("admin.mealEditor.referenceAria", { name })} value={item.reference_grams} onChange={(reference_grams) => patchItem(index, { reference_grams })} /><NumberInput label={t("admin.mealEditor.minAria", { name })} value={item.min_grams} onChange={(min_grams) => patchItem(index, { min_grams })} /><NumberInput label={t("admin.mealEditor.maxAria", { name })} value={item.max_grams} onChange={(max_grams) => patchItem(index, { max_grams })} /><label>{t("admin.mealEditor.roleAria", { name })}<select aria-label={t("admin.mealEditor.roleAria", { name })} value={item.functional_role ?? ""} onChange={(event) => patchItem(index, { functional_role: (event.target.value || null) as MealIngredientRole | null })}>{roles.map((role) => <option key={role || "none"} value={role}>{role ? t(`admin.meals.roles.${role}`) : t("admin.meals.roles.none")}</option>)}</select></label><label className="admin-meal-required"><input aria-label={t("admin.mealEditor.requiredAria", { name })} checked={item.is_required} onChange={(event) => patchItem(index, { is_required: event.target.checked })} type="checkbox" />{t("admin.mealEditor.required")}</label></div></article>;
              })}
              <button className="admin-template-editor-add" onClick={() => setPickerOpen(true)} type="button">{t("admin.mealEditor.addFood")}</button>
            </section>
            {pickerOpen && <section className="admin-template-exercise-picker" aria-label={t("admin.mealEditor.foodPicker")}><header><h2>{t("admin.mealEditor.foodPicker")}</h2><button type="button" onClick={() => setPickerOpen(false)}>{t("admin.mealEditor.close")}</button></header><input autoFocus onChange={(event) => setSearch(event.target.value)} placeholder={t("admin.mealEditor.searchPlaceholder")} value={search} /><div>{foods.map((food) => <button key={food.id} onClick={() => selectFood(food)} type="button">{t("admin.mealEditor.selectFood", { name: english ? food.name_en : food.name_fa })}</button>)}</div></section>}
            <footer className="admin-template-editor-actions"><span>{t("admin.mealEditor.boundsHint")}</span><button className="admin-primary-link" disabled={saving} type="submit">{saving ? t("admin.mealEditor.saving") : t("admin.mealEditor.save")}</button></footer>
          </form>
        )}
      </main>
    </div>
  );
}

function emptyMeal(rawCategory: string | null): MealForm {
  const category = categories.includes(rawCategory as MealCategory) ? rawCategory as MealCategory : "breakfast";
  return { name_fa: "", name_en: "", category, verification_status: "draft", items: [] };
}

function TextInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label>{label}<input aria-label={label} required value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

function NumberInput({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return <label>{label}<input aria-label={label} min="0.1" step="0.1" type="number" value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>;
}
