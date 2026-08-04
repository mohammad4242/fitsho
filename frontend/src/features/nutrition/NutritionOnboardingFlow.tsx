import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  BodyGoalFields,
  ExperienceFields,
  PersonalFields,
} from "../profile/ProfileFormFields";
import * as profileApi from "../profile/api";
import {
  toProfileInput,
  validateStep,
  type ProfileValidationErrors,
} from "../profile/profileValidation";
import type { ProductMode, Profile, ProfileFormValues, ProfileInput } from "../profile/types";
import * as nutritionApi from "./api";
import type {
  MedicalConditionCode,
  NutritionProfileInput,
  SafetyDecision,
  SafetyEvaluation,
  SafetyProfileInput,
} from "./types";
import type { OnboardingDraft } from "../publicOnboarding/onboardingDraft";

type FlowStep =
  | "loading"
  | "personal"
  | "body"
  | "safety"
  | "blocked"
  | "training"
  | "budget"
  | "cooking"
  | "foods"
  | "review"
  | "complete";

type Props = {
  productMode: Extract<ProductMode, "nutrition" | "both">;
  onCreateTrainingProfile: (input: ProfileInput) => Promise<Profile>;
  onComplete: () => void;
  trainingProfileExists?: boolean;
  draftMode?: boolean;
  initialDraft?: OnboardingDraft;
  onDraftChange?: (changes: Partial<OnboardingDraft>) => void;
  onDraftComplete?: (changes: Partial<OnboardingDraft>) => void;
  onExit?: () => void;
};

const emptyProfileValues: ProfileFormValues = {
  display_name: "", birth_date: "", sex: "", height_cm: "", current_weight_kg: "",
  shoulder_circumference_cm: "", waist_circumference_cm: "", hip_circumference_cm: "",
  fitness_goal: "", experience_level: "", training_days_per_week: "",
  training_location: "", home_training_setup: "", session_duration_minutes: "",
  physical_limitations: "", training_cautions: null, plan_duration_weeks: "4",
};

function draftValues(draft?: OnboardingDraft): ProfileFormValues {
  const source = draft?.training ?? draft?.shared;
  if (source === undefined) return emptyProfileValues;
  return {
    ...emptyProfileValues,
    display_name: source.display_name,
    birth_date: source.birth_date,
    sex: source.sex,
    height_cm: String(source.height_cm),
    current_weight_kg: String(source.current_weight_kg),
    fitness_goal: source.fitness_goal,
    ...(draft?.training === undefined ? {} : {
      shoulder_circumference_cm: draft.training.shoulder_circumference_cm === null ? "" : String(draft.training.shoulder_circumference_cm),
      waist_circumference_cm: draft.training.waist_circumference_cm === null ? "" : String(draft.training.waist_circumference_cm),
      hip_circumference_cm: draft.training.hip_circumference_cm === null ? "" : String(draft.training.hip_circumference_cm),
      experience_level: draft.training.experience_level,
      training_days_per_week: String(draft.training.training_days_per_week),
      training_location: draft.training.training_location,
      home_training_setup: draft.training.home_training_setup ?? "",
      session_duration_minutes: String(draft.training.session_duration_minutes),
      physical_limitations: draft.training.physical_limitations ?? "",
      training_cautions: draft.training.training_cautions,
      plan_duration_weeks: String(draft.training.plan_duration_weeks),
    }),
  };
}

const conditionOptions: Array<[MedicalConditionCode, string]> = [
  ["controlled_hypertension", "فشار خون کنترل‌شده"],
  ["lipid_disorder", "اختلال چربی خون"],
  ["type_2_diabetes_non_insulin", "دیابت نوع ۲ بدون انسولین"],
  ["stable_gastrointestinal", "مشکل پایدار گوارشی"],
  ["kidney_disease", "بیماری کلیه"],
  ["dialysis", "دیالیز"],
  ["liver_disease", "بیماری کبد"],
  ["insulin_treated_diabetes", "دیابت با درمان انسولین"],
  ["other", "بیماری یا شرایط دیگر"],
];

const splitNames = (value: string) => value.split(/[،,\n]/).map((item) => item.trim()).filter(Boolean);

export function NutritionOnboardingFlow({
  productMode,
  onCreateTrainingProfile,
  onComplete,
  trainingProfileExists = false,
  draftMode = false,
  initialDraft,
  onDraftChange,
  onDraftComplete,
  onExit,
}: Props) {
  const [step, setStep] = useState<FlowStep>(draftMode ? "personal" : "loading");
  const [values, setValues] = useState<ProfileFormValues>(() => draftValues(initialDraft));
  const [errors, setErrors] = useState<ProfileValidationErrors>({});
  const [busy, setBusy] = useState(false);
  const [requestError, setRequestError] = useState(false);
  const [decision, setDecision] = useState<SafetyDecision | SafetyEvaluation | null>(null);
  const [conditions, setConditions] = useState<MedicalConditionCode[]>([]);
  const [safetyFlags, setSafetyFlags] = useState({
    dangerous_food_reaction_history: false,
    pregnant: false,
    breastfeeding: false,
    eating_disorder_diagnosed: false,
    eating_disorder_active_symptoms: false,
    emergency_or_danger_symptoms: false,
    complex_medication_food_interaction: false,
  });
  const [medications, setMedications] = useState("");
  const [physicianRestrictions, setPhysicianRestrictions] = useState("");
  const [otherCondition, setOtherCondition] = useState("");
  const [budget, setBudget] = useState("");
  const [budgetStyle, setBudgetStyle] = useState<"strict" | "flexible">("strict");
  const [mealCount, setMealCount] = useState("3");
  const [snackCount, setSnackCount] = useState("1");
  const [startDay, setStartDay] = useState<NutritionProfileInput["preferred_plan_start_day"]>("saturday");
  const [planStyle, setPlanStyle] = useState<"economical" | "balanced" | "simple">("balanced");
  const [cooking, setCooking] = useState<CookingState>({
    skill: "basic",
    maximumTime: "45",
    frequency: "4",
    preparation: "mixed",
    refrigerator: true,
    freezer: true,
    equipment: ["stove", "refrigerator"] as NutritionProfileInput["cooking_equipment"],
    suppliedMeals: "0",
    suppliedSource: "",
  });
  const [foods, setFoods] = useState<FoodsState>({
    available: "", favourites: "", disliked: "", neverSuggest: "", refused: "",
    allergies: "", intolerances: "", cultural: "", workContext: "",
    dietaryPattern: "omnivore", variety: "medium",
    repetition: "2", leftovers: true, batchCooking: true,
    checkIn: false, checkInTime: "21:00",
  });

  useEffect(() => {
    if (draftMode) return;
    let active = true;
    void Promise.all([
      profileApi.getSharedProfile(),
      nutritionApi.getSafetyDecision(),
      nutritionApi.getNutritionProfile(),
    ]).then(([shared, savedDecision, nutrition]) => {
      if (!active) return;
      if (nutrition !== null) {
        setDecision(savedDecision);
        setStep("complete");
        return;
      }
      if (shared !== null) {
        setValues((current) => ({
          ...current,
          display_name: shared.display_name,
          birth_date: shared.birth_date,
          sex: shared.sex,
          height_cm: String(shared.height_cm),
          current_weight_kg: String(shared.current_weight_kg),
          fitness_goal: shared.fitness_goal,
        }));
      }
      setDecision(savedDecision);
      if (savedDecision !== null && !savedDecision.can_continue_onboarding) {
        setStep("blocked");
      } else if (savedDecision !== null) {
        setStep(productMode === "both" && !trainingProfileExists ? "training" : "budget");
      } else {
        setStep(shared === null ? "personal" : "safety");
      }
    }).catch(() => {
      if (active) {
        setRequestError(true);
        setStep("personal");
      }
    });
    return () => { active = false; };
  }, [draftMode, onComplete, productMode, trainingProfileExists]);

  function updateProfileValue(
    field: keyof ProfileFormValues,
    value: string | ProfileFormValues["training_cautions"],
  ) {
    setValues((current) => ({
      ...current,
      [field]: value,
      ...(field === "training_location" && value === "gym" ? { home_training_setup: "" } : {}),
    }));
    setErrors((current) => {
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  function nextFromPersonal(event: FormEvent) {
    event.preventDefault();
    const nextErrors = validateStep(values, 1, new Date());
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length === 0) setStep("body");
  }

  function saveShared(event: FormEvent) {
    event.preventDefault();
    const nextErrors = validateStep(values, 2, new Date());
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    const shared = {
      display_name: values.display_name.trim(),
      birth_date: values.birth_date,
      sex: values.sex as Exclude<typeof values.sex, "">,
      height_cm: Number(values.height_cm),
      current_weight_kg: Number(values.current_weight_kg),
      fitness_goal: values.fitness_goal as Exclude<typeof values.fitness_goal, "">,
    };
    if (draftMode) {
      onDraftChange?.({ shared });
      setStep("safety");
      return;
    }
    setBusy(true);
    setRequestError(false);
    void profileApi.saveSharedProfile(shared).then(() => setStep("safety")).catch(() => setRequestError(true)).finally(() => setBusy(false));
  }

  function safetyInput(): SafetyProfileInput {
    return {
      conditions: conditions.map((code) => ({ code, details: null })),
      medications: splitNames(medications).map((name) => ({ name, dosage: null, notes: null })),
      ...safetyFlags,
      physician_dietary_restrictions: physicianRestrictions.trim() || null,
      other_relevant_condition: otherCondition.trim() || null,
    };
  }

  function saveSafety(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setRequestError(false);
    const input = safetyInput();
    const request = draftMode
      ? nutritionApi.evaluateSafetyProfile(input)
      : nutritionApi.saveSafetyProfile(input);
    void request.then((result) => {
      if (draftMode) onDraftChange?.({ safety: input });
      setDecision(result);
      if (!result.can_continue_onboarding) setStep("blocked");
      else setStep(productMode === "both" && !trainingProfileExists ? "training" : "budget");
    }).catch(() => setRequestError(true)).finally(() => setBusy(false));
  }

  function saveTraining(event: FormEvent) {
    event.preventDefault();
    const nextErrors = validateStep(values, 3, new Date());
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    const training = toProfileInput(values);
    if (draftMode) {
      onDraftChange?.({ training });
      setStep("budget");
      return;
    }
    setBusy(true);
    setRequestError(false);
    void onCreateTrainingProfile(training)
      .then(() => setStep("budget"))
      .catch(() => setRequestError(true))
      .finally(() => setBusy(false));
  }

  const nutritionInput = useMemo<NutritionProfileInput>(() => ({
    individual_monthly_food_budget_irr: Number(budget),
    budget_style: budgetStyle,
    meals_per_day: Number(mealCount),
    snacks_per_day: Number(snackCount),
    preferred_plan_start_day: startDay,
    plan_style: planStyle,
    cooking_skill: cooking.skill,
    maximum_cooking_time_minutes: Number(cooking.maximumTime),
    cooking_frequency_per_week: Number(cooking.frequency),
    meal_preparation_preference: cooking.preparation,
    refrigerator_access: cooking.refrigerator,
    freezer_access: cooking.freezer,
    cooking_equipment: cooking.equipment,
    supplied_meals_per_week: Number(cooking.suppliedMeals),
    supplied_meal_source: cooking.suppliedSource.trim() || null,
    foods_available_at_home: splitNames(foods.available),
    favourite_foods: splitNames(foods.favourites),
    disliked_foods: splitNames(foods.disliked),
    never_suggest_foods: splitNames(foods.neverSuggest),
    refused_foods: splitNames(foods.refused),
    allergies: splitNames(foods.allergies).map((name) => ({ name, details: null })),
    intolerances: splitNames(foods.intolerances).map((name) => ({ name, details: null })),
    dietary_pattern: foods.dietaryPattern,
    religious_cultural_exclusions: splitNames(foods.cultural),
    preferred_variety: foods.variety,
    maximum_meal_repetition_per_week: Number(foods.repetition),
    accepts_leftovers: foods.leftovers,
    accepts_batch_cooking: foods.batchCooking,
    work_shift_context: foods.workContext.trim() || null,
    daily_check_in_enabled: foods.checkIn,
    preferred_check_in_time: foods.checkIn ? `${foods.checkInTime}:00` : null,
  }), [budget, budgetStyle, cooking, foods, mealCount, planStyle, snackCount, startDay]);

  function finish(event: FormEvent) {
    event.preventDefault();
    if (draftMode) {
      onDraftComplete?.({
        shared: {
          display_name: values.display_name.trim(), birth_date: values.birth_date,
          sex: values.sex as Exclude<typeof values.sex, "">, height_cm: Number(values.height_cm),
          current_weight_kg: Number(values.current_weight_kg),
          fitness_goal: values.fitness_goal as Exclude<typeof values.fitness_goal, "">,
        },
        safety: safetyInput(),
        ...(productMode === "both" ? { training: toProfileInput(values) } : {}),
        nutrition: nutritionInput,
      });
      return;
    }
    setBusy(true);
    setRequestError(false);
    void nutritionApi.saveNutritionProfile(nutritionInput)
      .then(() => {
        if (productMode === "both") onComplete();
        else setStep("complete");
      })
      .catch(() => setRequestError(true))
      .finally(() => setBusy(false));
  }

  const flowOrder: FlowStep[] = [
    "personal",
    "body",
    "safety",
    ...(productMode === "both" && !trainingProfileExists ? (["training"] as FlowStep[]) : []),
    "budget",
    "cooking",
    "foods",
    "review",
  ];
  const progressIndex = Math.max(flowOrder.indexOf(step), 0) + 1;

  if (step === "loading") return <p aria-live="polite">در حال آماده‌کردن مسیرت…</p>;
  if (step === "blocked") {
    return (
      <section className="nutrition-step safety-result-card" aria-live="polite">
        <p className="eyebrow eyebrow--accent">نتیجه ارزیابی ایمنی</p>
        <h2 className="fitsho-display">ادامه مسیر با پزشک فیتشو</h2>
        <p>{decision?.message}</p>
        <p>اطلاعات مجاز ذخیره شد و هیچ برنامه خودکاری ساخته نمی‌شود.</p>
        {draftMode && <button className="primary-button" type="button" onClick={() => onDraftComplete?.({ safety: safetyInput() })}>ادامه و ساخت حساب</button>}
        <button className="secondary-button" type="button" onClick={() => setStep("safety")}>بازگشت و اصلاح پاسخ‌ها</button>
      </section>
    );
  }
  if (step === "complete") {
    return (
      <section className="nutrition-step safety-result-card" aria-live="polite">
        <p className="eyebrow eyebrow--accent">پروفایل تغذیه</p>
        <h2 className="fitsho-display">پروفایل تغذیه‌ات ثبت شد</h2>
        <p>اطلاعات ایمنی، بودجه و ترجیحاتت ذخیره شد.</p>
        {decision?.requires_physician_review && <p>{decision.message}</p>}
        <p>در Task 2 هیچ برنامه غذایی تولید نشده است.</p>
      </section>
    );
  }

  return (
    <section className="nutrition-step">
      <p className="eyebrow eyebrow--accent">مسیر تغذیه با مربی فیتشو</p>
      <div className="nutrition-progress" aria-label="پیشرفت تکمیل پروفایل">
        <span>مرحله {progressIndex} از {flowOrder.length}</span>
        <progress value={progressIndex} max={flowOrder.length} />
      </div>
      <h2 className="fitsho-display">{stepTitle(step)}</h2>
      <p>{stepIntro(step)}</p>
      {decision?.requires_physician_review && step !== "safety" && (
        <p className="nutrition-feedback" role="status">{decision.message}</p>
      )}
      {step === "personal" && (
        <form className="profile-form" noValidate onSubmit={nextFromPersonal}>
          <PersonalFields values={values} errors={errors} disabled={busy} onChange={updateProfileValue} />
          <Actions busy={busy} onBack={draftMode ? onExit : undefined} nextLabel="ادامه" />
        </form>
      )}
      {step === "body" && (
        <form className="profile-form" noValidate onSubmit={saveShared}>
          <BodyGoalFields values={values} errors={errors} disabled={busy} onChange={updateProfileValue} />
          <button className="text-button" type="button" onClick={() => {
            updateProfileValue("shoulder_circumference_cm", "");
            updateProfileValue("waist_circumference_cm", "");
            updateProfileValue("hip_circumference_cm", "");
          }}>رد کردن اندازه‌گیری‌های اختیاری</button>
          <Actions busy={busy} onBack={() => setStep("personal")} nextLabel="ادامه" />
        </form>
      )}
      {step === "safety" && (
        <SafetyForm
          busy={busy}
          conditions={conditions}
          flags={safetyFlags}
          medications={medications}
          physicianRestrictions={physicianRestrictions}
          otherCondition={otherCondition}
          onConditions={setConditions}
          onFlags={setSafetyFlags}
          onMedications={setMedications}
          onPhysicianRestrictions={setPhysicianRestrictions}
          onOtherCondition={setOtherCondition}
          onSubmit={saveSafety}
          onBack={() => setStep("body")}
        />
      )}
      {step === "training" && (
        <form className="profile-form" noValidate onSubmit={saveTraining}>
          <ExperienceFields values={values} errors={errors} disabled={busy} onChange={updateProfileValue} />
          <button className="text-button" type="button" onClick={() => updateProfileValue("physical_limitations", "")}>رد کردن توضیحات اختیاری</button>
          <Actions busy={busy} onBack={() => setStep("safety")} nextLabel="ثبت اطلاعات تمرین و ادامه" />
        </form>
      )}
      {step === "budget" && (
        <BudgetForm
          busy={busy} budget={budget} budgetStyle={budgetStyle} mealCount={mealCount}
          snackCount={snackCount} startDay={startDay} planStyle={planStyle} onBudget={setBudget}
          onBudgetStyle={setBudgetStyle} onMealCount={setMealCount} onSnackCount={setSnackCount}
          onStartDay={setStartDay} onPlanStyle={setPlanStyle} onBack={() => setStep(productMode === "both" && !trainingProfileExists ? "training" : "safety")}
          onNext={() => setStep("cooking")}
        />
      )}
      {step === "cooking" && (
        <CookingForm busy={busy} value={cooking} onChange={setCooking} onBack={() => setStep("budget")} onNext={() => setStep("foods")} />
      )}
      {step === "foods" && (
        <FoodsForm busy={busy} value={foods} onChange={setFoods} onBack={() => setStep("cooking")} onNext={() => setStep("review")} />
      )}
      {step === "review" && (
        <form className="profile-form" onSubmit={finish}>
          <div className="nutrition-review-card">
            <strong>بودجه ماهانه: {new Intl.NumberFormat("fa-IR").format(Number(budget))} ریال</strong>
            <span>{mealCount} وعده اصلی و {snackCount} میان‌وعده در روز</span>
            <span>سیاست ایمنی: {decision?.policy_version}</span>
            <span>حساسیت ثبت‌شده: {splitNames(foods.allergies).join("، ") || "ندارد"}</span>
          </div>
          <Actions busy={busy} onBack={() => setStep("foods")} nextLabel="ثبت پروفایل تغذیه" />
        </form>
      )}
      {requestError && <p className="form-error" role="alert">درخواست انجام نشد. پاسخ‌ها حفظ شده‌اند؛ دوباره تلاش کن.</p>}
    </section>
  );
}

function stepTitle(step: FlowStep) {
  return ({
    loading: "", personal: "اول کمی با هم آشنا شویم", body: "هدفت را دقیق کنیم",
    safety: "اول ایمنی، بعد برنامه", blocked: "", training: "حالا بخش تمرین را هماهنگ کنیم",
    budget: "بودجه و وعده‌ها", cooking: "آشپزی را با زندگی تو هماهنگ می‌کنیم",
    foods: "غذاهایی که می‌خوری و نمی‌خوری", review: "یک مرور کوتاه قبل از ثبت", complete: "",
  })[step];
}

function stepIntro(step: FlowStep) {
  return ({
    loading: "", personal: "سؤال‌ها کوتاه‌اند و قدم‌به‌قدم پیش می‌رویم.",
    body: "این اطلاعات بین تمرین و تغذیه مشترک است و فقط یک‌بار ثبت می‌شود.",
    safety: "این پاسخ‌ها برای تشخیص پزشکی نیست؛ فقط مسیر ایمن برنامه را مشخص می‌کند.",
    blocked: "", training: "اطلاعات فعلی تمرینت را صفحه‌به‌صفحه نگه می‌داریم.",
    budget: "بودجه شخصی خودت را فقط به ریال وارد کن.",
    cooking: "با زمان و وسایل واقعی تو برنامه‌ریزی می‌کنیم.",
    foods: "هر مورد اختیاری را می‌توانی خالی بگذاری و رد کنی.",
    review: "بعد از ثبت، هنوز هیچ برنامه غذایی تولید نمی‌شود.", complete: "",
  })[step];
}

type Flags = SafetyProfileInput extends infer _ ? {
  dangerous_food_reaction_history: boolean; pregnant: boolean; breastfeeding: boolean;
  eating_disorder_diagnosed: boolean; eating_disorder_active_symptoms: boolean;
  emergency_or_danger_symptoms: boolean; complex_medication_food_interaction: boolean;
} : never;

function SafetyForm(props: {
  busy: boolean; conditions: MedicalConditionCode[]; flags: Flags; medications: string;
  physicianRestrictions: string; otherCondition: string;
  onConditions: (value: MedicalConditionCode[]) => void; onFlags: (value: Flags) => void;
  onMedications: (value: string) => void; onPhysicianRestrictions: (value: string) => void;
  onOtherCondition: (value: string) => void; onSubmit: (event: FormEvent) => void; onBack: () => void;
}) {
  return (
    <form className="profile-form" onSubmit={props.onSubmit}>
      <fieldset className="profile-fieldset" disabled={props.busy}>
        <legend>شرایط پزشکی و ایمنی</legend>
        <div className="profile-checkboxes">
          {conditionOptions.map(([code, label]) => (
            <label key={code}><input type="checkbox" checked={props.conditions.includes(code)}
              onChange={() => props.onConditions(props.conditions.includes(code)
                ? props.conditions.filter((item) => item !== code) : [...props.conditions, code])} />{label}</label>
          ))}
        </div>
        {([
          ["dangerous_food_reaction_history", "سابقه واکنش خطرناک غذایی"],
          ["pregnant", "بارداری"], ["breastfeeding", "شیردهی"],
          ["eating_disorder_diagnosed", "تشخیص اختلال خوردن"],
          ["eating_disorder_active_symptoms", "علائم فعال اختلال خوردن"],
          ["complex_medication_food_interaction", "تداخل پیچیده دارو و غذا"],
          ["emergency_or_danger_symptoms", "علائم خطر یا وضعیت اورژانسی"],
        ] as const).map(([field, label]) => (
          <label className="nutrition-check" key={field}><input type="checkbox" checked={props.flags[field]}
            onChange={(event) => props.onFlags({ ...props.flags, [field]: event.target.checked })} />{label}</label>
        ))}
        <TextArea label="داروهای فعلی (اختیاری، هر دارو یک خط)" value={props.medications} onChange={props.onMedications} />
        <TextArea label="محدودیت غذایی تجویزشده توسط پزشک (اختیاری)" value={props.physicianRestrictions} onChange={props.onPhysicianRestrictions} />
        <TextArea label="شرایط مرتبط دیگر (اختیاری)" value={props.otherCondition} onChange={props.onOtherCondition} />
        <button className="text-button" type="button" onClick={() => {
          props.onMedications(""); props.onPhysicianRestrictions(""); props.onOtherCondition("");
        }}>رد کردن توضیحات اختیاری</button>
      </fieldset>
      <Actions busy={props.busy} onBack={props.onBack} nextLabel="ثبت ارزیابی ایمنی" />
    </form>
  );
}

function BudgetForm(props: {
  busy: boolean; budget: string; budgetStyle: "strict" | "flexible"; mealCount: string;
  snackCount: string; startDay: NutritionProfileInput["preferred_plan_start_day"];
  planStyle: "economical" | "balanced" | "simple";
  onBudget: (value: string) => void; onBudgetStyle: (value: "strict" | "flexible") => void;
  onMealCount: (value: string) => void; onSnackCount: (value: string) => void;
  onStartDay: (value: NutritionProfileInput["preferred_plan_start_day"]) => void;
  onPlanStyle: (value: "economical" | "balanced" | "simple") => void;
  onBack: () => void; onNext: () => void;
}) {
  return (
    <form className="profile-form" onSubmit={(event) => { event.preventDefault(); if (Number(props.budget) >= 0 && props.budget !== "") props.onNext(); }}>
      <fieldset className="profile-fieldset" disabled={props.busy}>
        <legend>بودجه شخصی و تعداد وعده‌ها</legend>
        <LabeledInput label="بودجه ماهانه غذا (مبلغ به ریال)" type="number" min="0" required value={props.budget} onChange={props.onBudget} />
        <SelectField label="نوع بودجه" value={props.budgetStyle} onChange={(value) => props.onBudgetStyle(value as "strict" | "flexible")} options={[["strict", "سخت‌گیرانه"], ["flexible", "انعطاف‌پذیر"]]} />
        <LabeledInput label="وعده اصلی در روز" type="number" min="1" max="8" value={props.mealCount} onChange={props.onMealCount} />
        <LabeledInput label="میان‌وعده در روز" type="number" min="0" max="6" value={props.snackCount} onChange={props.onSnackCount} />
        <SelectField label="روز شروع برنامه" value={props.startDay} onChange={(value) => props.onStartDay(value as NutritionProfileInput["preferred_plan_start_day"])} options={[["saturday", "شنبه"], ["sunday", "یکشنبه"], ["monday", "دوشنبه"], ["tuesday", "سه‌شنبه"], ["wednesday", "چهارشنبه"], ["thursday", "پنجشنبه"], ["friday", "جمعه"]]} />
        <SelectField label="سبک برنامه" value={props.planStyle} onChange={(value) => props.onPlanStyle(value as typeof props.planStyle)} options={[["balanced", "متعادل"], ["economical", "اقتصادی"], ["simple", "ساده"]]} />
      </fieldset>
      <Actions busy={props.busy} onBack={props.onBack} nextLabel="ادامه" />
    </form>
  );
}

type CookingState = {
  skill: NutritionProfileInput["cooking_skill"]; maximumTime: string; frequency: string;
  preparation: NutritionProfileInput["meal_preparation_preference"];
  refrigerator: boolean; freezer: boolean; equipment: NutritionProfileInput["cooking_equipment"];
  suppliedMeals: string; suppliedSource: string;
};

function CookingForm(props: { busy: boolean; value: CookingState; onChange: (value: CookingState) => void; onBack: () => void; onNext: () => void }) {
  return (
    <form className="profile-form" onSubmit={(event) => { event.preventDefault(); props.onNext(); }}>
      <fieldset className="profile-fieldset" disabled={props.busy}>
        <legend>زمان، مهارت و امکانات</legend>
        <SelectField label="مهارت آشپزی" value={props.value.skill} onChange={(skill) => props.onChange({ ...props.value, skill: skill as CookingState["skill"] })} options={[["none", "آشپزی نمی‌کنم"], ["basic", "پایه"], ["confident", "مسلط"]]} />
        <SelectField label="روش آماده‌سازی ترجیحی" value={props.value.preparation} onChange={(preparation) => props.onChange({ ...props.value, preparation: preparation as CookingState["preparation"] })} options={[["daily", "روزانه"], ["batch", "چندوعده‌ای"], ["mixed", "ترکیبی"], ["no_cooking", "بدون آشپزی"]]} />
        <LabeledInput label="حداکثر زمان آشپزی (دقیقه)" type="number" min="0" max="360" value={props.value.maximumTime} onChange={(maximumTime) => props.onChange({ ...props.value, maximumTime })} />
        <LabeledInput label="دفعات آشپزی در هفته" type="number" min="0" max="7" value={props.value.frequency} onChange={(frequency) => props.onChange({ ...props.value, frequency })} />
        <label className="nutrition-check"><input type="checkbox" checked={props.value.refrigerator} onChange={(event) => props.onChange({ ...props.value, refrigerator: event.target.checked })} />دسترسی به یخچال</label>
        <label className="nutrition-check"><input type="checkbox" checked={props.value.freezer} onChange={(event) => props.onChange({ ...props.value, freezer: event.target.checked })} />دسترسی به فریزر</label>
        <div className="profile-checkboxes" aria-label="وسایل آشپزی موجود">
          {([[
            "stove", "اجاق"
          ], ["oven", "فر"], ["microwave", "مایکروویو"], ["air_fryer", "هواپز"], ["rice_cooker", "پلوپز"], ["blender", "مخلوط‌کن"], ["refrigerator", "یخچال"]] as Array<[NutritionProfileInput["cooking_equipment"][number], string]>).map(([equipment, label]) => (
            <label key={equipment}><input type="checkbox" checked={props.value.equipment.includes(equipment)} onChange={() => props.onChange({ ...props.value, equipment: props.value.equipment.includes(equipment) ? props.value.equipment.filter((item) => item !== equipment) : [...props.value.equipment, equipment] })} />{label}</label>
          ))}
        </div>
        <LabeledInput label="وعده تأمین‌شده در هفته" type="number" min="0" max="35" value={props.value.suppliedMeals} onChange={(suppliedMeals) => props.onChange({ ...props.value, suppliedMeals })} />
        <LabeledInput label="منبع وعده تأمین‌شده (اختیاری)" value={props.value.suppliedSource} onChange={(suppliedSource) => props.onChange({ ...props.value, suppliedSource })} />
        <button className="text-button" type="button" onClick={() => props.onChange({ ...props.value, suppliedSource: "" })}>رد کردن مورد اختیاری</button>
      </fieldset>
      <Actions busy={props.busy} onBack={props.onBack} nextLabel="ادامه" />
    </form>
  );
}

type FoodsState = {
  available: string; favourites: string; disliked: string; neverSuggest: string; refused: string;
  allergies: string; intolerances: string; cultural: string; workContext: string;
  dietaryPattern: NutritionProfileInput["dietary_pattern"];
  variety: NutritionProfileInput["preferred_variety"]; repetition: string; leftovers: boolean;
  batchCooking: boolean; checkIn: boolean; checkInTime: string;
};

function FoodsForm(props: { busy: boolean; value: FoodsState; onChange: (value: FoodsState) => void; onBack: () => void; onNext: () => void }) {
  const fields: Array<[keyof Pick<FoodsState, "available" | "favourites" | "disliked" | "neverSuggest" | "refused" | "allergies" | "intolerances" | "cultural" | "workContext">, string]> = [
    ["available", "مواد غذایی موجود در خانه (اختیاری)"], ["favourites", "غذاهای محبوب (اختیاری)"],
    ["disliked", "غذاهای دوست‌نداشتنی (اختیاری)"], ["neverSuggest", "دیگر هرگز پیشنهاد نشود (اختیاری)"],
    ["refused", "غذاهایی که نمی‌خوری (اختیاری)"], ["allergies", "حساسیت‌های غذایی (اختیاری، با ویرگول جدا کن)"],
    ["intolerances", "عدم تحمل غذایی (اختیاری)"], ["cultural", "محدودیت مذهبی یا فرهنگی (اختیاری)"],
    ["workContext", "شرایط کار یا شیفت (اختیاری)"],
  ];
  return (
    <form className="profile-form" onSubmit={(event) => { event.preventDefault(); props.onNext(); }}>
      <fieldset className="profile-fieldset" disabled={props.busy}>
        <legend>ترجیحات و حذف‌های قطعی</legend>
        {fields.map(([field, label]) => <LabeledInput key={field} label={label} value={props.value[field]} onChange={(value) => props.onChange({ ...props.value, [field]: value })} />)}
        <SelectField label="الگوی غذایی" value={props.value.dietaryPattern} onChange={(dietaryPattern) => props.onChange({ ...props.value, dietaryPattern: dietaryPattern as FoodsState["dietaryPattern"] })} options={[["omnivore", "همه‌چیزخوار"], ["vegetarian", "گیاه‌خوار"], ["vegan", "وگان"]]} />
        <SelectField label="تنوع ترجیحی" value={props.value.variety} onChange={(variety) => props.onChange({ ...props.value, variety: variety as FoodsState["variety"] })} options={[["low", "کم"], ["medium", "متوسط"], ["high", "زیاد"]]} />
        <LabeledInput label="حداکثر تکرار هر وعده در هفته" type="number" min="1" max="7" value={props.value.repetition} onChange={(repetition) => props.onChange({ ...props.value, repetition })} />
        <label className="nutrition-check"><input type="checkbox" checked={props.value.leftovers} onChange={(event) => props.onChange({ ...props.value, leftovers: event.target.checked })} />باقی‌مانده غذا را می‌پذیرم</label>
        <label className="nutrition-check"><input type="checkbox" checked={props.value.batchCooking} onChange={(event) => props.onChange({ ...props.value, batchCooking: event.target.checked })} />آشپزی چندوعده‌ای را می‌پذیرم</label>
        <label className="nutrition-check"><input type="checkbox" checked={props.value.checkIn} onChange={(event) => props.onChange({ ...props.value, checkIn: event.target.checked })} />یادآوری بررسی کوتاه روزانه</label>
        {props.value.checkIn && <LabeledInput label="زمان یادآوری روزانه" type="time" value={props.value.checkInTime} onChange={(checkInTime) => props.onChange({ ...props.value, checkInTime })} />}
        <button className="text-button" type="button" onClick={() => props.onChange({ ...props.value, available: "", favourites: "", disliked: "", neverSuggest: "", refused: "", allergies: "", intolerances: "", cultural: "", workContext: "" })}>رد کردن همه موارد اختیاری</button>
      </fieldset>
      <Actions busy={props.busy} onBack={props.onBack} nextLabel="مرور پاسخ‌ها" />
    </form>
  );
}

function LabeledInput(props: { label: string; value: string; onChange: (value: string) => void; type?: string; min?: string; max?: string; required?: boolean }) {
  return <div className="profile-field"><label>{props.label}<input type={props.type ?? "text"} min={props.min} max={props.max} required={props.required} value={props.value} onChange={(event) => props.onChange(event.target.value)} /></label></div>;
}

function TextArea(props: { label: string; value: string; onChange: (value: string) => void }) {
  return <div className="profile-field"><label>{props.label}<textarea value={props.value} onChange={(event) => props.onChange(event.target.value)} /></label></div>;
}

function SelectField(props: { label: string; value: string; options: Array<[string, string]>; onChange: (value: string) => void }) {
  return <div className="profile-field"><label>{props.label}<select value={props.value} onChange={(event) => props.onChange(event.target.value)}>{props.options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></div>;
}

function Actions({ busy, onBack, nextLabel }: { busy: boolean; onBack?: () => void; nextLabel: string }) {
  return <div className="profile-actions">{onBack && <button className="secondary-button" type="button" disabled={busy} onClick={onBack}>بازگشت</button>}<button className="primary-button" type="submit" disabled={busy}>{busy ? "در حال ذخیره…" : nextLabel}</button></div>;
}
