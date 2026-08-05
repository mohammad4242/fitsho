import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

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
import type { OnboardingDraft, PreAccountNutritionBasics } from "../publicOnboarding/onboardingDraft";
import { GuidedSharedProfileQuestions } from "../publicOnboarding/GuidedSharedProfileQuestions";
import { GuidedTrainingQuestions } from "../publicOnboarding/GuidedTrainingQuestions";

type FlowStep =
  | "loading"
  | "personal"
  | "body"
  | "safety"
  | "pre_account"
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
  initialNutritionBasics?: PreAccountNutritionBasics;
  onNutritionComplete?: () => void;
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

const conditionOptions: Array<[MedicalConditionCode, string, string]> = [
  ["controlled_hypertension", "فشار خون کنترل‌شده", "Controlled high blood pressure"],
  ["lipid_disorder", "اختلال چربی خون", "Lipid disorder"],
  ["type_2_diabetes_non_insulin", "دیابت نوع ۲ بدون انسولین", "Type 2 diabetes without insulin"],
  ["stable_gastrointestinal", "مشکل پایدار گوارشی", "Stable gastrointestinal condition"],
  ["kidney_disease", "بیماری کلیه", "Kidney disease"],
  ["dialysis", "دیالیز", "Dialysis"],
  ["liver_disease", "بیماری کبد", "Liver disease"],
  ["insulin_treated_diabetes", "دیابت با درمان انسولین", "Insulin-treated diabetes"],
  ["other", "بیماری یا شرایط دیگر", "Other condition"],
];

const splitNames = (value: string) => value.split(/[،,\n]/).map((item) => item.trim()).filter(Boolean);

const flowCopy = {
  fa: {
    loading: "در حال آماده‌کردن مسیرت…", eyebrow: "مسیر تغذیه با مربی فیتشو", progress: "پیشرفت تکمیل پروفایل",
    error: "درخواست انجام نشد. پاسخ‌ها حفظ شده‌اند؛ دوباره تلاش کن.",
  },
  en: {
    loading: "Preparing your path…", eyebrow: "Nutrition with your Fitsho coach", progress: "Profile setup progress",
    error: "The request could not be completed. Your answers are saved; please try again.",
  },
} as const;

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
  initialNutritionBasics,
  onNutritionComplete,
}: Props) {
  const { i18n } = useTranslation();
  const language = i18n.resolvedLanguage === "en" ? "en" : "fa";
  const copy = flowCopy[language];
  const [step, setStep] = useState<FlowStep>(draftMode ? "personal" : "loading");
  const [values, setValues] = useState<ProfileFormValues>(() => draftValues(initialDraft));
  const [, setErrors] = useState<ProfileValidationErrors>({});
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
  const [budget, setBudget] = useState(() => initialNutritionBasics === undefined ? "" : String(initialNutritionBasics.individual_monthly_food_budget_irr));
  const [budgetStyle, setBudgetStyle] = useState<"strict" | "flexible">(() => initialNutritionBasics?.budget_style ?? "strict");
  const [mealCount, setMealCount] = useState("3");
  const [snackCount, setSnackCount] = useState("1");
  const [startDay, setStartDay] = useState<NutritionProfileInput["preferred_plan_start_day"]>("saturday");
  const [planStyle, setPlanStyle] = useState<"economical" | "balanced" | "simple">(() => initialNutritionBasics?.plan_style ?? "balanced");
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
    allergies: initialNutritionBasics?.allergies.map((item) => item.name).join(", ") ?? "", intolerances: initialNutritionBasics?.intolerances.map((item) => item.name).join(", ") ?? "", cultural: "", workContext: "",
    dietaryPattern: initialNutritionBasics?.dietary_pattern ?? "omnivore", variety: "medium",
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

  function saveShared() {
    const nextErrors = { ...validateStep(values, 1, new Date()), ...validateStep(values, 2, new Date()) };
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
      if (productMode === "both" && !trainingProfileExists) setStep("training");
      else setStep("pre_account");
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

  function saveSafety() {
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

  function saveTraining() {
    const nextErrors = validateStep(values, 3, new Date());
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    const training = toProfileInput(values);
    if (draftMode) {
      onDraftChange?.({ training });
      setStep("pre_account");
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
        onNutritionComplete?.();
        if (productMode === "both") onComplete();
        else setStep("complete");
      })
      .catch(() => setRequestError(true))
      .finally(() => setBusy(false));
  }

  const flowOrder: FlowStep[] = [
    "personal",
    "safety",
    ...(productMode === "both" && !trainingProfileExists ? (["training"] as FlowStep[]) : []),
    "budget",
    "cooking",
    "foods",
    "review",
  ];
  const progressIndex = Math.max(flowOrder.indexOf(step), 0) + 1;
  const guidedStep = step !== "review";

  if (step === "loading") return <p aria-live="polite">{copy.loading}</p>;
  if (step === "blocked") {
    return (
      <section className="nutrition-step safety-result-card" aria-live="polite">
        <p className="eyebrow eyebrow--accent">{language === "en" ? "Safety assessment result" : "نتیجه ارزیابی ایمنی"}</p>
        <h2 className="fitsho-display">{language === "en" ? "Continue with a Fitsho physician" : "ادامه مسیر با پزشک فیتشو"}</h2>
        <p>{language === "en" ? "For your safety, this path needs review by a Fitsho physician." : decision?.message}</p>
        <p>{language === "en" ? "Allowed information is saved and no automatic plan will be created." : "اطلاعات مجاز ذخیره شد و هیچ برنامه خودکاری ساخته نمی‌شود."}</p>
        {draftMode && <button className="primary-button" type="button" onClick={() => onDraftComplete?.({ safety: safetyInput() })}>{language === "en" ? "Continue to account setup" : "ادامه و ساخت حساب"}</button>}
        <button className="secondary-button" type="button" onClick={() => setStep("safety")}>{language === "en" ? "Back and edit answers" : "بازگشت و اصلاح پاسخ‌ها"}</button>
      </section>
    );
  }
  if (step === "complete") {
    return (
      <section className="nutrition-step safety-result-card" aria-live="polite">
        <p className="eyebrow eyebrow--accent">{language === "en" ? "Nutrition profile" : "پروفایل تغذیه"}</p>
        <h2 className="fitsho-display">{language === "en" ? "Your nutrition profile is saved" : "پروفایل تغذیه‌ات ثبت شد"}</h2>
        <p>{language === "en" ? "Your safety, budget, and preference information is saved." : "اطلاعات ایمنی، بودجه و ترجیحاتت ذخیره شد."}</p>
        {decision?.requires_physician_review && <p>{language === "en" ? "A Fitsho physician will review your nutrition path." : decision.message}</p>}
        <p>{language === "en" ? "No meal plan has been generated yet." : "هنوز هیچ برنامه غذایی تولید نشده است."}</p>
      </section>
    );
  }

  return (
    <section className="nutrition-step" dir={language === "fa" ? "rtl" : "ltr"}>
      {!guidedStep && <><p className="eyebrow eyebrow--accent">{copy.eyebrow}</p>
      <div className="nutrition-progress" aria-label={copy.progress}>
        <span>{language === "en" ? `Step ${progressIndex} of ${flowOrder.length}` : `مرحله ${progressIndex} از ${flowOrder.length}`}</span>
        <progress value={progressIndex} max={flowOrder.length} />
      </div>
      <h2 className="fitsho-display">{stepTitle(step, language)}</h2>
      <p>{stepIntro(step, language)}</p></>}
      {decision?.requires_physician_review && step !== "safety" && (
        <p className="nutrition-feedback" role="status">{language === "en" ? "A Fitsho physician review is required for your nutrition path." : decision.message}</p>
      )}
      {step === "personal" && (
        <GuidedSharedProfileQuestions values={values} onChange={(field, value) => updateProfileValue(field, value)} onBack={onExit ?? (() => undefined)} onComplete={saveShared} />
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
          onComplete={saveSafety}
          onBack={() => setStep("personal")}
        />
      )}
      {step === "pre_account" && <PreAccountNutritionQuestions
        busy={busy} conditions={conditions} flags={safetyFlags} foods={foods} budget={budget} planStyle={planStyle}
        onConditions={setConditions} onFlags={setSafetyFlags} onFoods={setFoods} onBudget={setBudget} onPlanStyle={setPlanStyle}
        onBack={() => setStep(productMode === "both" ? "training" : "personal")}
        onComplete={() => onDraftComplete?.({ safety: safetyInput(), nutritionBasics: {
          individual_monthly_food_budget_irr: Number(budget), budget_style: budgetStyle, plan_style: planStyle,
          allergies: splitNames(foods.allergies).map((name) => ({ name, details: null })), intolerances: splitNames(foods.intolerances).map((name) => ({ name, details: null })), dietary_pattern: foods.dietaryPattern,
        } })}
      />}
      {step === "training" && (
        <GuidedTrainingQuestions values={values} onChange={updateProfileValue} onBack={() => setStep("safety")} onComplete={saveTraining} />
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
            <strong>{language === "en" ? `Monthly budget: ${new Intl.NumberFormat("en-US").format(Number(budget))} IRR` : `بودجه ماهانه: ${new Intl.NumberFormat("fa-IR").format(Number(budget))} ریال`}</strong>
            <span>{language === "en" ? `${mealCount} meals and ${snackCount} snacks per day` : `${mealCount} وعده اصلی و ${snackCount} میان‌وعده در روز`}</span>
            <span>{language === "en" ? "Safety policy" : "سیاست ایمنی"}: {decision?.policy_version}</span>
            <span>{language === "en" ? `Allergies: ${splitNames(foods.allergies).join(", ") || "None"}` : `حساسیت ثبت‌شده: ${splitNames(foods.allergies).join("، ") || "ندارد"}`}</span>
          </div>
          <Actions busy={busy} onBack={() => setStep("foods")} nextLabel={language === "en" ? "Save nutrition profile" : "ثبت پروفایل تغذیه"} />
        </form>
      )}
      {requestError && <p className="form-error" role="alert">{copy.error}</p>}
    </section>
  );
}

function stepTitle(step: FlowStep, language: "fa" | "en") {
  const fa = {
    loading: "", personal: "اول کمی با هم آشنا شویم", body: "هدفت را دقیق کنیم",
    safety: "اول ایمنی، بعد برنامه", blocked: "", training: "حالا بخش تمرین را هماهنگ کنیم", pre_account: "چند سؤال کوتاه تغذیه",
    budget: "بودجه و وعده‌ها", cooking: "آشپزی را با زندگی تو هماهنگ می‌کنیم",
    foods: "غذاهایی که می‌خوری و نمی‌خوری", review: "یک مرور کوتاه قبل از ثبت", complete: "",
  };
  const en = {
    loading: "", personal: "Let’s get to know each other", body: "Let’s define your goal",
    safety: "Safety first, then your plan", blocked: "", training: "Let’s align your training", pre_account: "A few quick nutrition questions",
    budget: "Budget and meals", cooking: "Let’s fit cooking into your life",
    foods: "Foods you eat and avoid", review: "A quick review before saving", complete: "",
  };
  return (language === "en" ? en : fa)[step];
}

function stepIntro(step: FlowStep, language: "fa" | "en") {
  const fa = {
    loading: "", personal: "سؤال‌ها کوتاه‌اند و قدم‌به‌قدم پیش می‌رویم.",
    body: "این اطلاعات بین تمرین و تغذیه مشترک است و فقط یک‌بار ثبت می‌شود.",
    safety: "این پاسخ‌ها برای تشخیص پزشکی نیست؛ فقط مسیر ایمن برنامه را مشخص می‌کند.",
    blocked: "", training: "اطلاعات فعلی تمرینت را صفحه‌به‌صفحه نگه می‌داریم.", pre_account: "بعد از ساخت حساب، فقط جزئیات باقی‌ماندهٔ پروفایل را کامل می‌کنیم.",
    budget: "بودجه شخصی خودت را فقط به ریال وارد کن.",
    cooking: "با زمان و وسایل واقعی تو برنامه‌ریزی می‌کنیم.",
    foods: "هر مورد اختیاری را می‌توانی خالی بگذاری و رد کنی.",
    review: "بعد از ثبت، هنوز هیچ برنامه غذایی تولید نمی‌شود.", complete: "",
  };
  const en = {
    loading: "", personal: "The questions are short; we’ll take them one step at a time.",
    body: "Training and nutrition share this information, so we only ask once.",
    safety: "These answers do not provide a diagnosis; they only help keep your plan safe.",
    blocked: "", training: "We’ll keep your current training details one screen at a time.", pre_account: "After account setup, you will only complete the remaining profile details.",
    budget: "Enter your personal food budget in IRR.",
    cooking: "We’ll plan around your real time and equipment.",
    foods: "Every optional answer can be left blank and skipped.",
    review: "Saving this does not generate a meal plan yet.", complete: "",
  };
  return (language === "en" ? en : fa)[step];
}

type Flags = SafetyProfileInput extends infer _ ? {
  dangerous_food_reaction_history: boolean; pregnant: boolean; breastfeeding: boolean;
  eating_disorder_diagnosed: boolean; eating_disorder_active_symptoms: boolean;
  emergency_or_danger_symptoms: boolean; complex_medication_food_interaction: boolean;
} : never;

function useLocalizer() {
  const { i18n } = useTranslation();
  return (fa: string, en: string) => i18n.resolvedLanguage === "en" ? en : fa;
}

function NutritionQuestionFrame(props: {
  busy: boolean;
  current: number;
  total: number;
  title: string;
  stage: 0 | 1 | 2;
  optional?: boolean;
  nextLabel?: string;
  onBack: () => void;
  onSubmit: () => void;
  children: ReactNode;
}) {
  const l = useLocalizer();
  const stages = [l("ایمنی", "Safety"), l("سبک زندگی", "Routine"), l("غذاها", "Food")];
  return (
    <section className="guided-question nutrition-question" aria-labelledby="nutrition-question-title">
      <ol className="guided-stage-track" aria-label={l("بخش‌های تغذیه", "Nutrition sections")}>
        {stages.map((stage, index) => (
          <li className={index < props.stage ? "is-complete" : index === props.stage ? "is-active" : ""} key={stage}>
            <span aria-hidden="true">{index < props.stage ? "✓" : index + 1}</span>{stage}
          </li>
        ))}
      </ol>
      <div className="public-onboarding-progress" aria-label={l("پیشرفت سؤال‌های تغذیه", "Nutrition questions progress")}>
        <span>{l(`سؤال ${props.current + 1} از ${props.total}`, `Question ${props.current + 1} of ${props.total}`)}</span>
        <progress value={props.current + 1} max={props.total} />
      </div>
      <h1 className="fitsho-display" id="nutrition-question-title">{props.title}</h1>
      <form className="guided-question__form" onSubmit={(event) => { event.preventDefault(); props.onSubmit(); }}>
        <fieldset className="nutrition-question__control" disabled={props.busy}>{props.children}</fieldset>
        {props.optional && <button className="text-button" type="submit">{l("رد کردن این سؤال", "Skip this question")}</button>}
        <Actions busy={props.busy} onBack={props.onBack} nextLabel={props.nextLabel ?? l("ادامه", "Continue")} />
      </form>
    </section>
  );
}

function SafetyForm(props: {
  busy: boolean; conditions: MedicalConditionCode[]; flags: Flags; medications: string;
  physicianRestrictions: string; otherCondition: string;
  onConditions: (value: MedicalConditionCode[]) => void; onFlags: (value: Flags) => void;
  onMedications: (value: string) => void; onPhysicianRestrictions: (value: string) => void;
  onOtherCondition: (value: string) => void; onComplete: () => void; onBack: () => void;
}) {
  const l = useLocalizer();
  const [question, setQuestion] = useState(0);
  const titles = [
    l("آیا شرایط پزشکی مشخصی داری؟", "Do you have any medical conditions?"),
    l("کدام موارد ایمنی دربارهٔ تو صدق می‌کند؟", "Do any of these safety considerations apply?"),
    l("در حال حاضر چه داروهایی مصرف می‌کنی؟", "Which medications do you currently take?"),
    l("پزشک محدودیت غذایی خاصی برایت تعیین کرده؟", "Has a physician prescribed dietary restrictions?"),
    l("شرایط دیگری هست که مربی باید بداند؟", "Is there anything else your coach should know?"),
  ];
  const advance = () => question === titles.length - 1 ? props.onComplete() : setQuestion((current) => current + 1);
  const back = () => question === 0 ? props.onBack() : setQuestion((current) => current - 1);
  return (
    <NutritionQuestionFrame busy={props.busy} current={question} total={titles.length} title={titles[question]} stage={0}
      optional={question >= 2} nextLabel={question === titles.length - 1 ? l("ثبت ارزیابی ایمنی", "Save safety assessment") : undefined}
      onBack={back} onSubmit={advance}>
        {question === 0 && <div className="profile-checkboxes">
          {conditionOptions.map(([code, fa, en]) => (
            <label key={code}><input type="checkbox" checked={props.conditions.includes(code)}
              onChange={() => props.onConditions(props.conditions.includes(code)
                ? props.conditions.filter((item) => item !== code) : [...props.conditions, code])} />{l(fa, en)}</label>
          ))}
        </div>}
        {question === 1 && <div className="profile-checkboxes">{([
          ["dangerous_food_reaction_history", "سابقه واکنش خطرناک غذایی", "History of dangerous food reaction"],
          ["pregnant", "بارداری", "Pregnant"], ["breastfeeding", "شیردهی", "Breastfeeding"],
          ["eating_disorder_diagnosed", "تشخیص اختلال خوردن", "Diagnosed eating disorder"],
          ["eating_disorder_active_symptoms", "علائم فعال اختلال خوردن", "Active eating-disorder symptoms"],
          ["complex_medication_food_interaction", "تداخل پیچیده دارو و غذا", "Complex medication-food interaction"],
          ["emergency_or_danger_symptoms", "علائم خطر یا وضعیت اورژانسی", "Emergency or danger symptoms"],
        ] as const).map(([field, fa, en]) => (
          <label className="nutrition-check" key={field}><input type="checkbox" checked={props.flags[field]}
            onChange={(event) => props.onFlags({ ...props.flags, [field]: event.target.checked })} />{l(fa, en)}</label>
        ))}</div>}
        {question === 2 && <TextArea label={l("داروهای فعلی (اختیاری، هر دارو یک خط)", "Current medications (optional, one per line)")} value={props.medications} onChange={props.onMedications} />}
        {question === 3 && <TextArea label={l("محدودیت غذایی تجویزشده توسط پزشک (اختیاری)", "Physician-prescribed dietary restrictions (optional)")} value={props.physicianRestrictions} onChange={props.onPhysicianRestrictions} />}
        {question === 4 && <TextArea label={l("شرایط مرتبط دیگر (اختیاری)", "Other relevant conditions (optional)")} value={props.otherCondition} onChange={props.onOtherCondition} />}
    </NutritionQuestionFrame>
  );
}

function PreAccountNutritionQuestions(props: {
  busy: boolean; conditions: MedicalConditionCode[]; flags: Flags; foods: FoodsState; budget: string;
  planStyle: "economical" | "balanced" | "simple";
  onConditions: (value: MedicalConditionCode[]) => void; onFlags: (value: Flags) => void;
  onFoods: (value: FoodsState) => void; onBudget: (value: string) => void;
  onPlanStyle: (value: "economical" | "balanced" | "simple") => void; onBack: () => void; onComplete: () => void;
}) {
  const l = useLocalizer();
  const [question, setQuestion] = useState(0);
  const titles = [
    l("آیا شرایط پزشکی مشخصی داری؟", "Do you have any medical conditions?"),
    l("کدام موارد ایمنی دربارهٔ تو صدق می‌کند؟", "Do any of these safety considerations apply?"),
    l("حساسیت یا عدم‌تحمل غذایی داری؟", "Do you have food allergies or intolerances?"),
    l("بودجه ماهانه غذای تو چقدر است؟", "What is your monthly food budget?"),
    l("چه سبک غذایی را ترجیح می‌دهی؟", "Which food style do you prefer?"),
  ];
  const advance = () => question === titles.length - 1 ? props.onComplete() : setQuestion((current) => current + 1);
  const back = () => question === 0 ? props.onBack() : setQuestion((current) => current - 1);
  return <NutritionQuestionFrame busy={props.busy} current={question} total={titles.length} title={titles[question]} stage={question < 2 ? 0 : question < 4 ? 1 : 2} optional={question === 2} nextLabel={question === titles.length - 1 ? l("ادامه و ساخت حساب", "Continue to account setup") : undefined} onBack={back} onSubmit={advance}>
    {question === 0 && <div className="profile-checkboxes">{conditionOptions.map(([code, fa, en]) => <label key={code}><input type="checkbox" checked={props.conditions.includes(code)} onChange={() => props.onConditions(props.conditions.includes(code) ? props.conditions.filter((item) => item !== code) : [...props.conditions, code])} />{l(fa, en)}</label>)}</div>}
    {question === 1 && <div className="profile-checkboxes">{([
      ["dangerous_food_reaction_history", "سابقه واکنش خطرناک غذایی", "History of dangerous food reaction"], ["pregnant", "بارداری", "Pregnant"], ["breastfeeding", "شیردهی", "Breastfeeding"], ["eating_disorder_diagnosed", "تشخیص اختلال خوردن", "Diagnosed eating disorder"], ["eating_disorder_active_symptoms", "علائم فعال اختلال خوردن", "Active eating-disorder symptoms"], ["complex_medication_food_interaction", "تداخل پیچیده دارو و غذا", "Complex medication-food interaction"], ["emergency_or_danger_symptoms", "علائم خطر یا وضعیت اورژانسی", "Emergency or danger symptoms"],
    ] as const).map(([field, fa, en]) => <label className="nutrition-check" key={field}><input type="checkbox" checked={props.flags[field]} onChange={(event) => props.onFlags({ ...props.flags, [field]: event.target.checked })} />{l(fa, en)}</label>)}</div>}
    {question === 2 && <><TextArea label={l("حساسیت‌های غذایی (اختیاری، با ویرگول جدا کن)", "Food allergies (optional, comma separated)")} value={props.foods.allergies} onChange={(allergies) => props.onFoods({ ...props.foods, allergies })} /><TextArea label={l("عدم‌تحمل‌های غذایی (اختیاری، با ویرگول جدا کن)", "Food intolerances (optional, comma separated)")} value={props.foods.intolerances} onChange={(intolerances) => props.onFoods({ ...props.foods, intolerances })} /></>}
    {question === 3 && <LabeledInput label={l("بودجه ماهانه غذا (مبلغ به ریال)", "Monthly food budget (IRR)")} type="number" min="0" required value={props.budget} onChange={props.onBudget} />}
    {question === 4 && <SelectField label={l("سبک غذا", "Food style")} value={props.foods.dietaryPattern} onChange={(dietaryPattern) => props.onFoods({ ...props.foods, dietaryPattern: dietaryPattern as FoodsState["dietaryPattern"] })} options={[["omnivore", l("همه‌چیزخوار", "Omnivore")], ["vegetarian", l("گیاه‌خوار", "Vegetarian")], ["vegan", l("وگان", "Vegan")]]} />}
  </NutritionQuestionFrame>;
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
  const l = useLocalizer();
  const [question, setQuestion] = useState(0);
  const titles = [
    l("بودجه ماهانه غذای تو چقدر است؟", "What is your monthly food budget?"),
    l("بودجه را چقدر سخت‌گیرانه رعایت کنیم؟", "How strictly should we follow your budget?"),
    l("روزانه چند وعده اصلی می‌خوری؟", "How many main meals do you eat each day?"),
    l("روزانه چند میان‌وعده می‌خواهی؟", "How many snacks would you like each day?"),
    l("برنامه غذایی از چه روزی شروع شود؟", "Which day should your plan start?"),
    l("چه سبک برنامه‌ای برایت مناسب‌تر است؟", "Which plan style suits you best?"),
  ];
  const advance = () => question === titles.length - 1 ? props.onNext() : setQuestion((current) => current + 1);
  const back = () => question === 0 ? props.onBack() : setQuestion((current) => current - 1);
  return (
    <NutritionQuestionFrame busy={props.busy} current={question} total={titles.length} title={titles[question]} stage={1}
      onBack={back} onSubmit={advance}>
      {question === 0 && <LabeledInput label={l("بودجه ماهانه غذا (مبلغ به ریال)", "Monthly food budget (IRR)")} type="number" min="0" required value={props.budget} onChange={props.onBudget} />}
      {question === 1 && <SelectField label={l("نوع بودجه", "Budget style")} value={props.budgetStyle} onChange={(value) => props.onBudgetStyle(value as "strict" | "flexible")} options={[["strict", l("سخت‌گیرانه", "Strict")], ["flexible", l("انعطاف‌پذیر", "Flexible")]]} />}
      {question === 2 && <LabeledInput label={l("وعده اصلی در روز", "Meals per day")} type="number" min="1" max="8" required value={props.mealCount} onChange={props.onMealCount} />}
      {question === 3 && <LabeledInput label={l("میان‌وعده در روز", "Snacks per day")} type="number" min="0" max="6" required value={props.snackCount} onChange={props.onSnackCount} />}
      {question === 4 && <SelectField label={l("روز شروع برنامه", "Plan start day")} value={props.startDay} onChange={(value) => props.onStartDay(value as NutritionProfileInput["preferred_plan_start_day"])} options={[["saturday", l("شنبه", "Saturday")], ["sunday", l("یکشنبه", "Sunday")], ["monday", l("دوشنبه", "Monday")], ["tuesday", l("سه‌شنبه", "Tuesday")], ["wednesday", l("چهارشنبه", "Wednesday")], ["thursday", l("پنجشنبه", "Thursday")], ["friday", l("جمعه", "Friday")]]} />}
      {question === 5 && <SelectField label={l("سبک برنامه", "Plan style")} value={props.planStyle} onChange={(value) => props.onPlanStyle(value as typeof props.planStyle)} options={[["balanced", l("متعادل", "Balanced")], ["economical", l("اقتصادی", "Economical")], ["simple", l("ساده", "Simple")]]} />}
    </NutritionQuestionFrame>
  );
}

type CookingState = {
  skill: NutritionProfileInput["cooking_skill"]; maximumTime: string; frequency: string;
  preparation: NutritionProfileInput["meal_preparation_preference"];
  refrigerator: boolean; freezer: boolean; equipment: NutritionProfileInput["cooking_equipment"];
  suppliedMeals: string; suppliedSource: string;
};

function CookingForm(props: { busy: boolean; value: CookingState; onChange: (value: CookingState) => void; onBack: () => void; onNext: () => void }) {
  const l = useLocalizer();
  const [question, setQuestion] = useState(0);
  const titles = [
    l("چقدر با آشپزی راحتی؟", "How comfortable are you with cooking?"),
    l("ترجیح می‌دهی غذاها چطور آماده شوند؟", "How do you prefer to prepare meals?"),
    l("برای هر بار آشپزی چقدر زمان داری؟", "How much time can you spend cooking?"),
    l("چند بار در هفته آشپزی می‌کنی؟", "How often do you cook each week?"),
    l("به یخچال و فریزر دسترسی داری؟", "Do you have access to a fridge and freezer?"),
    l("چه وسایل آشپزی در اختیار داری؟", "Which cooking equipment do you have?"),
    l("چند وعده در هفته از جای دیگری تأمین می‌شود؟", "How many meals are provided elsewhere each week?"),
    l("این وعده‌ها معمولاً از کجا تأمین می‌شوند؟", "Where are those meals usually provided?"),
  ];
  const advance = () => question === titles.length - 1 ? props.onNext() : setQuestion((current) => current + 1);
  const back = () => question === 0 ? props.onBack() : setQuestion((current) => current - 1);
  return (
    <NutritionQuestionFrame busy={props.busy} current={question} total={titles.length} title={titles[question]} stage={1}
      optional={question === 7} onBack={back} onSubmit={advance}>
        {question === 0 && <SelectField label={l("مهارت آشپزی", "Cooking skill")} value={props.value.skill} onChange={(skill) => props.onChange({ ...props.value, skill: skill as CookingState["skill"] })} options={[["none", l("آشپزی نمی‌کنم", "I do not cook")], ["basic", l("پایه", "Basic")], ["confident", l("مسلط", "Confident")]]} />}
        {question === 1 && <SelectField label={l("روش آماده‌سازی ترجیحی", "Preferred preparation")} value={props.value.preparation} onChange={(preparation) => props.onChange({ ...props.value, preparation: preparation as CookingState["preparation"] })} options={[["daily", l("روزانه", "Daily")], ["batch", l("چندوعده‌ای", "Batch")], ["mixed", l("ترکیبی", "Mixed")], ["no_cooking", l("بدون آشپزی", "No cooking")]]} />}
        {question === 2 && <LabeledInput label={l("حداکثر زمان آشپزی (دقیقه)", "Maximum cooking time (minutes)")} type="number" min="0" max="360" required value={props.value.maximumTime} onChange={(maximumTime) => props.onChange({ ...props.value, maximumTime })} />}
        {question === 3 && <LabeledInput label={l("دفعات آشپزی در هفته", "Cooking sessions per week")} type="number" min="0" max="7" required value={props.value.frequency} onChange={(frequency) => props.onChange({ ...props.value, frequency })} />}
        {question === 4 && <div className="profile-checkboxes">
          <label className="nutrition-check"><input type="checkbox" checked={props.value.refrigerator} onChange={(event) => props.onChange({ ...props.value, refrigerator: event.target.checked })} />{l("دسترسی به یخچال", "Refrigerator access")}</label>
          <label className="nutrition-check"><input type="checkbox" checked={props.value.freezer} onChange={(event) => props.onChange({ ...props.value, freezer: event.target.checked })} />{l("دسترسی به فریزر", "Freezer access")}</label>
        </div>}
        {question === 5 && <div className="profile-checkboxes" aria-label={l("وسایل آشپزی موجود", "Available cooking equipment")}>
          {([[
            "stove", l("اجاق", "Stove")
          ], ["oven", l("فر", "Oven")], ["microwave", l("مایکروویو", "Microwave")], ["air_fryer", l("هواپز", "Air fryer")], ["rice_cooker", l("پلوپز", "Rice cooker")], ["blender", l("مخلوط‌کن", "Blender")], ["refrigerator", l("یخچال", "Refrigerator")]] as Array<[NutritionProfileInput["cooking_equipment"][number], string]>).map(([equipment, label]) => (
            <label key={equipment}><input type="checkbox" checked={props.value.equipment.includes(equipment)} onChange={() => props.onChange({ ...props.value, equipment: props.value.equipment.includes(equipment) ? props.value.equipment.filter((item) => item !== equipment) : [...props.value.equipment, equipment] })} />{label}</label>
          ))}
        </div>}
        {question === 6 && <LabeledInput label={l("وعده تأمین‌شده در هفته", "Provided meals per week")} type="number" min="0" max="35" required value={props.value.suppliedMeals} onChange={(suppliedMeals) => props.onChange({ ...props.value, suppliedMeals })} />}
        {question === 7 && <LabeledInput label={l("منبع وعده تأمین‌شده (اختیاری)", "Provided meal source (optional)")} value={props.value.suppliedSource} onChange={(suppliedSource) => props.onChange({ ...props.value, suppliedSource })} />}
    </NutritionQuestionFrame>
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
  const l = useLocalizer();
  const fields: Array<[keyof Pick<FoodsState, "available" | "favourites" | "disliked" | "neverSuggest" | "refused" | "allergies" | "intolerances" | "cultural" | "workContext">, string]> = [
    ["available", l("مواد غذایی موجود در خانه (اختیاری)", "Foods available at home (optional)")], ["favourites", l("غذاهای محبوب (اختیاری)", "Favourite foods (optional)")],
    ["disliked", l("غذاهای دوست‌نداشتنی (اختیاری)", "Disliked foods (optional)")], ["neverSuggest", l("دیگر هرگز پیشنهاد نشود (اختیاری)", "Never suggest again (optional)")],
    ["refused", l("غذاهایی که نمی‌خوری (اختیاری)", "Foods you refuse (optional)")], ["allergies", l("حساسیت‌های غذایی (اختیاری، با ویرگول جدا کن)", "Food allergies (optional, comma-separated)")],
    ["intolerances", l("عدم تحمل غذایی (اختیاری)", "Food intolerances (optional)")], ["cultural", l("محدودیت مذهبی یا فرهنگی (اختیاری)", "Religious or cultural exclusions (optional)")],
    ["workContext", l("شرایط کار یا شیفت (اختیاری)", "Work or shift context (optional)")],
  ];
  const questions = [...fields.map(([field]) => field), "dietaryPattern", "variety", "repetition", "leftovers", "batchCooking", "checkIn", ...(props.value.checkIn ? ["checkInTime"] : [])] as const;
  const [question, setQuestion] = useState(0);
  const current = questions[Math.min(question, questions.length - 1)];
  const field = fields.find(([name]) => name === current);
  const titles: Record<string, string> = {
    available: l("الان چه مواد غذایی در خانه داری؟", "Which foods do you have at home?"),
    favourites: l("چه غذاهایی را بیشتر دوست داری؟", "Which foods do you enjoy most?"),
    disliked: l("چه غذاهایی را دوست نداری؟", "Which foods do you dislike?"),
    neverSuggest: l("چه غذایی دیگر هرگز پیشنهاد نشود؟", "Which foods should never be suggested again?"),
    refused: l("چه غذاهایی را اصلاً نمی‌خوری؟", "Which foods do you refuse to eat?"),
    allergies: l("حساسیت غذایی داری؟", "Do you have any food allergies?"),
    intolerances: l("عدم تحمل غذایی داری؟", "Do you have any food intolerances?"),
    cultural: l("محدودیت مذهبی یا فرهنگی داری؟", "Do you have religious or cultural exclusions?"),
    workContext: l("برنامه کار یا شیفت روی غذایت اثر می‌گذارد؟", "Does work or shift timing affect your meals?"),
    dietaryPattern: l("الگوی غذایی تو کدام است؟", "Which dietary pattern do you follow?"),
    variety: l("چقدر تنوع غذایی می‌خواهی؟", "How much food variety would you like?"),
    repetition: l("هر وعده حداکثر چند بار تکرار شود؟", "How often may a meal repeat each week?"),
    leftovers: l("با خوردن باقی‌مانده غذا راحتی؟", "Are you comfortable eating leftovers?"),
    batchCooking: l("با آشپزی برای چند وعده راحتی؟", "Are you comfortable batch cooking?"),
    checkIn: l("یادآوری بررسی روزانه می‌خواهی؟", "Would you like a daily check-in reminder?"),
    checkInTime: l("یادآوری چه ساعتی باشد؟", "What time should we remind you?"),
  };
  const advance = () => question === questions.length - 1 ? props.onNext() : setQuestion((value) => value + 1);
  const back = () => question === 0 ? props.onBack() : setQuestion((value) => value - 1);
  const booleanChoice = (key: "leftovers" | "batchCooking" | "checkIn") => (
    <div className="guided-choice-grid">
      <button className={props.value[key] ? "is-selected" : ""} type="button" onClick={() => props.onChange({ ...props.value, [key]: true })}>{l("بله", "Yes")}</button>
      <button className={!props.value[key] ? "is-selected" : ""} type="button" onClick={() => props.onChange({ ...props.value, [key]: false })}>{l("نه", "No")}</button>
    </div>
  );
  return (
    <NutritionQuestionFrame busy={props.busy} current={question} total={questions.length} title={titles[current]} stage={2}
      optional={field !== undefined} nextLabel={question === questions.length - 1 ? l("مرور پاسخ‌ها", "Review answers") : undefined}
      onBack={back} onSubmit={advance}>
      {field && <LabeledInput label={field[1]} value={props.value[field[0]]} onChange={(value) => props.onChange({ ...props.value, [field[0]]: value })} />}
      {current === "dietaryPattern" && <SelectField label={l("الگوی غذایی", "Dietary pattern")} value={props.value.dietaryPattern} onChange={(dietaryPattern) => props.onChange({ ...props.value, dietaryPattern: dietaryPattern as FoodsState["dietaryPattern"] })} options={[["omnivore", l("همه‌چیزخوار", "Omnivore")], ["vegetarian", l("گیاه‌خوار", "Vegetarian")], ["vegan", l("وگان", "Vegan")]]} />}
      {current === "variety" && <SelectField label={l("تنوع ترجیحی", "Preferred variety")} value={props.value.variety} onChange={(variety) => props.onChange({ ...props.value, variety: variety as FoodsState["variety"] })} options={[["low", l("کم", "Low")], ["medium", l("متوسط", "Medium")], ["high", l("زیاد", "High")]]} />}
      {current === "repetition" && <LabeledInput label={l("حداکثر تکرار هر وعده در هفته", "Maximum repetitions per meal each week")} type="number" min="1" max="7" required value={props.value.repetition} onChange={(repetition) => props.onChange({ ...props.value, repetition })} />}
      {current === "leftovers" && booleanChoice("leftovers")}
      {current === "batchCooking" && booleanChoice("batchCooking")}
      {current === "checkIn" && booleanChoice("checkIn")}
      {current === "checkInTime" && <LabeledInput label={l("زمان یادآوری روزانه", "Daily reminder time")} type="time" required value={props.value.checkInTime} onChange={(checkInTime) => props.onChange({ ...props.value, checkInTime })} />}
    </NutritionQuestionFrame>
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
  const l = useLocalizer();
  return <div className="profile-actions">{onBack && <button className="secondary-button" type="button" disabled={busy} onClick={onBack}>{l("بازگشت", "Back")}</button>}<button className="primary-button" type="submit" disabled={busy}>{busy ? l("در حال ذخیره…", "Saving…") : nextLabel}</button></div>;
}
