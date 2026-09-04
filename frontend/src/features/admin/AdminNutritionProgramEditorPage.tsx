import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";

import foodAccent from "../../assets/landing/food.webp";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import {
  createAdminNutritionProgram,
  getAdminMealCatalogue,
  getAdminNutritionProgram,
  updateAdminNutritionProgram,
} from "./api";
import type {
  AdminMealCatalogueItem,
  AdminNutritionProgram,
  AdminNutritionProgramWrite,
  MealCategory,
  NutritionBudgetTier,
  NutritionDietStyle,
} from "./types";
import "./admin.css";

const requiredCategories: MealCategory[] = ["breakfast", "lunch", "snack", "dinner"];
const allCategories: MealCategory[] = [...requiredCategories, "post_workout"];
const dietStyles: NutritionDietStyle[] = ["economy", "balanced_iranian", "high_protein_gym", "quick_easy", "premium_varied"];
const budgetTiers: NutritionBudgetTier[] = ["economy", "normal", "varied"];

type DayForm = { day_number: number; post_workout_enabled: boolean; free_meal: boolean; meals: Record<MealCategory, string> };
type ProgramForm = Omit<AdminNutritionProgramWrite, "days"> & { days: DayForm[] };

export function AdminNutritionProgramEditorPage() {
  const { t } = useTranslation();
  const { programId } = useParams();
  const navigate = useNavigate();
  const [form, setForm] = useState<ProgramForm>(emptyProgram());
  const [mealOptions, setMealOptions] = useState<Record<MealCategory, AdminMealCatalogueItem[]>>(emptyMealOptions());
  const [state, setState] = useState<"loading" | "ready" | "missing">("loading");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const mealsRequest = Promise.all(allCategories.map(async (category) => {
      const page = await getAdminMealCatalogue(category);
      return [category, page.items.filter((meal) => meal.verification_status === "verified")] as const;
    }));
    const programRequest = programId ? getAdminNutritionProgram(programId) : Promise.resolve(null);
    void Promise.all([mealsRequest, programRequest])
      .then(([options, program]) => {
        if (!active) return;
        setMealOptions(Object.fromEntries(options) as Record<MealCategory, AdminMealCatalogueItem[]>);
        if (program !== null) setForm(formFromProgram(program));
        setState("ready");
      })
      .catch(() => { if (active) setState("missing"); });
    return () => { active = false; };
  }, [programId]);

  function patchDay(dayNumber: number, patch: Partial<DayForm>) {
    setForm((current) => ({ ...current, days: current.days.map((day) => day.day_number === dayNumber ? { ...day, ...patch } : day) }));
  }

  function setMeal(dayNumber: number, category: MealCategory, mealId: string) {
    setForm((current) => ({ ...current, days: current.days.map((day) => day.day_number === dayNumber ? { ...day, meals: { ...day.meals, [category]: mealId } } : day) }));
  }

  function setGlobalPostWorkout(enabled: boolean) {
    setForm((current) => ({
      ...current,
      post_workout_enabled: enabled,
      days: enabled ? current.days : current.days.map((day) => ({ ...day, post_workout_enabled: false, meals: { ...day.meals, post_workout: "" } })),
    }));
  }

  async function save() {
    const missingRequired = form.days.some((day) => requiredCategories.some((category) => category !== "lunch" || !day.free_meal ? !day.meals[category] : false) || (day.post_workout_enabled && !day.meals.post_workout));
    if (missingRequired) { setError(t("admin.nutritionProgramEditor.mealRequired")); return; }
    const payload: AdminNutritionProgramWrite = {
      code: form.code,
      name_fa: form.name_fa,
      name_en: form.name_en,
      description_fa: form.description_fa,
      description_en: form.description_en,
      diet_style: form.diet_style,
      budget_tier_hint: form.budget_tier_hint ?? "normal",
      post_workout_enabled: form.post_workout_enabled,
      days: form.days.map((day) => ({
        day_number: day.day_number,
        post_workout_enabled: day.post_workout_enabled,
        slots: [
          ...requiredCategories.map((category) => category === "lunch" && day.free_meal ? ({ kind: "free_meal" as const, category, meal_id: null }) : ({ category, meal_id: day.meals[category] })),
          ...(day.post_workout_enabled ? [{ category: "post_workout" as const, meal_id: day.meals.post_workout }] : []),
        ],
      })),
    };
    setSaving(true);
    setError(null);
    try {
      const saved = programId ? await updateAdminNutritionProgram(programId, payload) : await createAdminNutritionProgram(payload);
      navigate(`/admin/nutrition-programs/${saved.id}/edit`, { replace: true });
    } catch {
      setError(t("admin.nutritionProgramEditor.saveError"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="admin-page">
      <MemberHeaderMedia imageSrc={foodAccent} className="member-page-background" />
      <AuthenticatedHeader />
      <main className="admin-main admin-main--template-editor admin-main--nutrition-program-editor">
        <header className="admin-form-header">
          <div><p className="eyebrow eyebrow--accent">{t("admin.nutritionProgramEditor.eyebrow")}</p><h1>{programId ? t("admin.nutritionProgramEditor.titleEdit") : t("admin.nutritionProgramEditor.titleNew")}</h1><p>{t("admin.nutritionProgramEditor.intro")}</p></div>
          <Link to="/admin/nutrition-programs">{t("admin.nutritionProgramEditor.back")}</Link>
        </header>
        {state === "loading" && <p className="admin-status" role="status">{t("admin.nutritionProgramEditor.loading")}</p>}
        {state === "missing" && <p className="admin-status" role="alert">{t("admin.nutritionProgramEditor.missing")}</p>}
        {state === "ready" && (
          <form className="admin-template-editor admin-program-editor" noValidate onSubmit={(event) => { event.preventDefault(); void save(); }}>
            {error && <p className="admin-form-alert" role="alert">{error}</p>}
            <section>
              <h2>{t("admin.nutritionProgramEditor.identity")}</h2>
              <div className="admin-template-editor-grid">
                <TextInput label={t("admin.nutritionProgramEditor.nameFa")} value={form.name_fa} onChange={(name_fa) => setForm((current) => ({ ...current, name_fa }))} />
                <TextInput label={t("admin.nutritionProgramEditor.nameEn")} value={form.name_en} onChange={(name_en) => setForm((current) => ({ ...current, name_en }))} />
                <TextArea label={t("admin.nutritionProgramEditor.descriptionFa")} value={form.description_fa} onChange={(description_fa) => setForm((current) => ({ ...current, description_fa }))} />
                <TextArea label={t("admin.nutritionProgramEditor.descriptionEn")} value={form.description_en} onChange={(description_en) => setForm((current) => ({ ...current, description_en }))} />
                <label>{t("admin.nutritionProgramEditor.dietStyle")}<select value={form.diet_style} onChange={(event) => setForm((current) => ({ ...current, diet_style: event.target.value as NutritionDietStyle }))}>{dietStyles.map((style) => <option key={style} value={style}>{t(`admin.nutritionPrograms.dietStyles.${style}`)}</option>)}</select></label>
                <label>{t("admin.nutritionProgramEditor.budgetTierHint")}<select value={form.budget_tier_hint ?? "normal"} onChange={(event) => setForm((current) => ({ ...current, budget_tier_hint: event.target.value as NutritionBudgetTier }))}>{budgetTiers.map((tier) => <option key={tier} value={tier}>{t(`admin.nutritionPrograms.budgetTiers.${tier}`)}</option>)}</select></label>
                <label className="admin-program-toggle"><input aria-label={t("admin.nutritionProgramEditor.globalPostWorkout")} checked={form.post_workout_enabled} type="checkbox" onChange={(event) => setGlobalPostWorkout(event.target.checked)} />{t("admin.nutritionProgramEditor.globalPostWorkout")}</label>
              </div>
            </section>

            <section>
              <h2>{t("admin.nutritionProgramEditor.week")}</h2>
              <div className="admin-program-editor-week">
                {form.days.map((day) => (
                  <fieldset className="admin-program-editor-day" aria-label={t("admin.nutritionPrograms.day", { number: day.day_number })} key={day.day_number}>
                    <legend>{t("admin.nutritionPrograms.day", { number: day.day_number })}</legend>
                    {requiredCategories.map((category) => category === "lunch" && day.free_meal ? <p key={category}><strong>وعده آزاد</strong></p> : <MealSelect key={category} category={category} dayNumber={day.day_number} meals={mealOptions[category]} value={day.meals[category]} onChange={(mealId) => setMeal(day.day_number, category, mealId)} />)}
                    {day.day_number === 7 && <label className="admin-program-toggle"><input type="checkbox" checked={day.free_meal} onChange={(event) => patchDay(day.day_number, { free_meal: event.target.checked })} />وعده آزاد</label>}
                    {form.post_workout_enabled && <label className="admin-program-toggle"><input aria-label={t("admin.nutritionProgramEditor.dailyPostWorkoutAria", { number: day.day_number })} checked={day.post_workout_enabled} type="checkbox" onChange={(event) => patchDay(day.day_number, { post_workout_enabled: event.target.checked, meals: event.target.checked ? day.meals : { ...day.meals, post_workout: "" } })} />{t("admin.nutritionProgramEditor.dailyPostWorkout")}</label>}
                    {form.post_workout_enabled && day.post_workout_enabled && <MealSelect category="post_workout" dayNumber={day.day_number} meals={mealOptions.post_workout} value={day.meals.post_workout} onChange={(mealId) => setMeal(day.day_number, "post_workout", mealId)} />}
                  </fieldset>
                ))}
              </div>
            </section>
            <footer className="admin-template-editor-actions"><span>{t("admin.nutritionProgramEditor.structureHint")}</span><button className="admin-primary-link" disabled={saving} type="submit">{saving ? t("admin.nutritionProgramEditor.saving") : t("admin.nutritionProgramEditor.save")}</button></footer>
          </form>
        )}
      </main>
    </div>
  );
}

function MealSelect({ category, dayNumber, meals, value, onChange }: { category: MealCategory; dayNumber: number; meals: AdminMealCatalogueItem[]; value: string; onChange: (value: string) => void }) {
  const { t } = useTranslation();
  const label = t("admin.nutritionProgramEditor.mealAria", { category: t(`admin.meals.categories.${category}`), number: dayNumber });
  return <label>{t(`admin.meals.categories.${category}`)}<select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}><option value="">{t("admin.nutritionProgramEditor.chooseMeal")}</option>{meals.map((meal) => <option key={meal.id} value={meal.id}>{meal.code} — {meal.name_fa} · {meal.name_en}</option>)}</select></label>;
}

function emptyProgram(): ProgramForm {
  return {
    code: null, name_fa: "", name_en: "", description_fa: "", description_en: "", diet_style: "balanced_iranian", budget_tier_hint: "normal", post_workout_enabled: false,
    days: Array.from({ length: 7 }, (_, index) => ({ day_number: index + 1, post_workout_enabled: false, free_meal: false, meals: { breakfast: "", lunch: "", snack: "", dinner: "", post_workout: "" } })),
  };
}

function emptyMealOptions(): Record<MealCategory, AdminMealCatalogueItem[]> {
  return { breakfast: [], lunch: [], snack: [], dinner: [], post_workout: [] };
}

function formFromProgram(program: AdminNutritionProgram): ProgramForm {
  return {
    code: program.code, name_fa: program.name_fa, name_en: program.name_en, description_fa: program.description_fa, description_en: program.description_en,
    diet_style: program.diet_style, budget_tier_hint: program.budget_tier_hint ?? "normal", post_workout_enabled: program.post_workout_enabled,
    days: program.days.map((day) => ({
      day_number: day.day_number,
      post_workout_enabled: day.post_workout_enabled,
      free_meal: day.slots.some((slot) => slot.kind === "free_meal"),
      meals: { breakfast: "", lunch: "", snack: "", dinner: "", post_workout: "", ...Object.fromEntries(day.slots.filter((slot) => slot.meal !== null).map((slot) => [slot.category, slot.meal!.id])) },
    })),
  };
}


function TextInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label>{label}<input aria-label={label} required value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label>{label}<textarea aria-label={label} required value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}
