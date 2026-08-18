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
  NutritionProfile,
  SafetyDecision,
  SafetyEvaluation,
  SafetyProfileInput,
} from "./types";
import type { OnboardingDraft, PreAccountNutritionBasics } from "../publicOnboarding/onboardingDraft";
import { GuidedSharedProfileQuestions } from "../publicOnboarding/GuidedSharedProfileQuestions";
import { GuidedTrainingQuestions } from "../publicOnboarding/GuidedTrainingQuestions";
import { NutritionExerciseQuestions } from "./NutritionExerciseQuestions";
import { formatTomanInput, irrToToman, tomanToIrr } from "./money";
import type { StructuredExerciseInput } from "./types";
import "./nutritionOnboarding.css";

type FlowStep =
  | "loading"
  | "personal"
  | "body"
  | "safety"
  | "pre_account"
  | "blocked"
  | "training"
  | "budget"
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
  editExisting?: boolean;
  onBack?: () => void;
};

const emptyProfileValues: ProfileFormValues = {
  display_name: "", birth_date: "", sex: "", height_cm: "", current_weight_kg: "",
  shoulder_circumference_cm: "", waist_circumference_cm: "", hip_circumference_cm: "",
  fitness_goal: "", experience_level: "", training_days_per_week: "",
  training_location: "", home_training_setup: "", session_duration_minutes: "",
  training_intensity: "",
  training_age_months: "",
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
      training_intensity: draft.training.training_intensity ?? "",
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
  editExisting = false,
  onBack,
}: Props) {
  const { i18n } = useTranslation();
  const language = i18n.resolvedLanguage === "en" ? "en" : "fa";
  const copy = flowCopy[language];
  const [step, setStep] = useState<FlowStep>(draftMode ? "personal" : "loading");
  const [values, setValues] = useState<ProfileFormValues>(() => draftValues(initialDraft));
  const [, setErrors] = useState<ProfileValidationErrors>({});
  const [busy, setBusy] = useState(false);
  const [requestError, setRequestError] = useState(false);
  const [detailsSaved, setDetailsSaved] = useState(false);
  const [decision, setDecision] = useState<SafetyDecision | SafetyEvaluation | null>(null);
  const [conditions, setConditions] = useState<MedicalConditionCode[]>(() => initialDraft?.safety?.conditions.map((item) => item.code) ?? []);
  const [safetyFlags, setSafetyFlags] = useState({
    dangerous_food_reaction_history: initialDraft?.safety?.dangerous_food_reaction_history ?? false,
    pregnant: initialDraft?.safety?.pregnant ?? false,
    breastfeeding: initialDraft?.safety?.breastfeeding ?? false,
    eating_disorder_diagnosed: initialDraft?.safety?.eating_disorder_diagnosed ?? false,
    eating_disorder_active_symptoms: initialDraft?.safety?.eating_disorder_active_symptoms ?? false,
    emergency_or_danger_symptoms: initialDraft?.safety?.emergency_or_danger_symptoms ?? false,
    complex_medication_food_interaction: initialDraft?.safety?.complex_medication_food_interaction ?? false,
  });
  const [medications, setMedications] = useState(() => initialDraft?.safety?.medications.map((item) => item.name).join(", ") ?? "");
  const [physicianRestrictions, setPhysicianRestrictions] = useState(() => initialDraft?.safety?.physician_dietary_restrictions ?? "");
  const [otherCondition, setOtherCondition] = useState(() => initialDraft?.safety?.other_relevant_condition ?? "");
  const [dailyActivityLevel, setDailyActivityLevel] = useState<NutritionProfileInput["daily_activity_level"]>(() => initialNutritionBasics?.daily_activity_level ?? "moderate");
  const [structuredExercise, setStructuredExercise] = useState<StructuredExerciseInput | undefined>(() => initialDraft?.structuredExercise);
  const [budget, setBudget] = useState(() => initialNutritionBasics === undefined ? "" : irrToToman(initialNutritionBasics.individual_monthly_food_budget_irr));
  const [budgetStyle, setBudgetStyle] = useState<"strict" | "flexible">(() => initialNutritionBasics?.budget_style ?? "strict");
  const [mealCount, setMealCount] = useState("3");
  const [snackCount, setSnackCount] = useState("1");
  const [startDay, setStartDay] = useState<NutritionProfileInput["preferred_plan_start_day"]>("saturday");
  const planStyle = initialNutritionBasics?.plan_style ?? "balanced";
  const [foods, setFoods] = useState<FoodsState>({
    favourites: "", disliked: "",
    allergies: initialNutritionBasics?.allergies.map((item) => item.name).join(", ") ?? "", intolerances: initialNutritionBasics?.intolerances.map((item) => item.name).join(", ") ?? "", cultural: "", workContext: "",
    dietaryPattern: initialNutritionBasics?.dietary_pattern ?? "omnivore",
    checkIn: false, checkInTime: "21:00",
  });

  useEffect(() => {
    if (draftMode) return;
    let active = true;
    void Promise.all([
      profileApi.getSharedProfile(),
      nutritionApi.getSafetyDecision(),
      nutritionApi.getNutritionProfile(),
      nutritionApi.getStructuredExercise(),
    ]).then(([shared, savedDecision, nutrition, savedExercise]) => {
      if (!active) return;
      if (savedExercise !== null) {
        setStructuredExercise(savedExercise.trains ? {
          trains: true,
          exercise_type: savedExercise.exercise_type ?? "other",
          days_per_week: savedExercise.days_per_week ?? 1,
          minutes_per_session: savedExercise.minutes_per_session ?? 30,
          intensity: savedExercise.intensity ?? "moderate",
        } : { trains: false });
      }
      if (nutrition !== null) {
        setDecision(savedDecision);
        if (!editExisting) {
          setStep("complete");
          return;
        }
        populateExistingNutrition(nutrition);
        setStep("budget");
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
        setStep(productMode === "nutrition" || !trainingProfileExists ? "training" : "budget");
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
  }, [draftMode, editExisting, onComplete, productMode, trainingProfileExists]);

  function populateExistingNutrition(nutrition: NutritionProfile) {
    setDailyActivityLevel(nutrition.daily_activity_level);
    setBudget(irrToToman(nutrition.individual_monthly_food_budget_irr));
    setBudgetStyle(nutrition.budget_style);
    setMealCount(String(nutrition.effective_main_meal_slots ?? nutrition.meals_per_day));
    setSnackCount(String(nutrition.effective_snack_slots ?? nutrition.snacks_per_day));
    setStartDay(nutrition.preferred_plan_start_day);
    setFoods({
      favourites: nutrition.favourite_foods.join(", "),
      disliked: nutrition.disliked_foods.join(", "),
      allergies: nutrition.allergies.map((item) => item.name).join(", "),
      intolerances: nutrition.intolerances.map((item) => item.name).join(", "),
      cultural: nutrition.religious_cultural_exclusions.join(", "),
      workContext: nutrition.work_shift_context ?? "",
      dietaryPattern: nutrition.dietary_pattern,
      checkIn: nutrition.daily_check_in_enabled,
      checkInTime: nutrition.preferred_check_in_time?.slice(0, 5) ?? "21:00",
    });
  }

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
      setStep("training");
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
      else setStep((productMode === "nutrition" && structuredExercise === undefined) || !trainingProfileExists ? "training" : "budget");
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

  function saveNutritionExercise(input: StructuredExerciseInput) {
    setStructuredExercise(input);
    if (draftMode) {
      onDraftChange?.({ structuredExercise: input, training: undefined });
      setStep("pre_account");
      return;
    }
    setStep("budget");
  }

  const nutritionInput = useMemo<NutritionProfileInput>(() => ({
    daily_activity_level: dailyActivityLevel,
    individual_monthly_food_budget_irr: tomanToIrr(budget),
    budget_style: budgetStyle,
    main_meal_count_bucket: mealCount === "2" ? "two_main_meals" : mealCount === "3" ? "three_main_meals" : "four_or_more_main_meals",
    snack_count_bucket: snackCount === "0" ? "zero_snacks" : snackCount === "1" ? "one_snack" : snackCount === "2" ? "two_snacks" : "three_or_more_snacks",
    meals_per_day: Number(mealCount),
    snacks_per_day: Number(snackCount),
    preferred_plan_start_day: startDay,
    favourite_foods: splitNames(foods.favourites),
    disliked_foods: splitNames(foods.disliked),
    allergies: splitNames(foods.allergies).map((name) => ({ name, details: null })),
    intolerances: splitNames(foods.intolerances).map((name) => ({ name, details: null })),
    dietary_pattern: foods.dietaryPattern,
    religious_cultural_exclusions: splitNames(foods.cultural),
    work_shift_context: foods.workContext.trim() || null,
    daily_check_in_enabled: foods.checkIn,
    preferred_check_in_time: foods.checkIn ? `${foods.checkInTime}:00` : null,
  }), [budget, budgetStyle, dailyActivityLevel, foods, mealCount, snackCount, startDay]);

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
        if (productMode === "nutrition") {
          if (structuredExercise === undefined) throw new Error("Structured exercise is required");
          return nutritionApi.saveStructuredExercise(structuredExercise);
        }
        return undefined;
      })
      .then(() => nutritionApi.createNutritionEstimate())
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
    ...(productMode === "nutrition" || !trainingProfileExists ? (["training"] as FlowStep[]) : []),
    "budget",
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

  if (editExisting && step === "budget") {
    return (
      <PostAccountNutritionDetails
        language={language}
        busy={busy}
        dailyActivityLevel={dailyActivityLevel}
        budget={budget}
        budgetStyle={budgetStyle}
        mealCount={mealCount}
        snackCount={snackCount}
        startDay={startDay}
        foods={foods}
        saved={detailsSaved}
        saveError={requestError}
        onDailyActivityLevel={setDailyActivityLevel}
        onBudget={setBudget}
        onBudgetStyle={setBudgetStyle}
        onMealCount={setMealCount}
        onSnackCount={setSnackCount}
        onStartDay={setStartDay}
        onFoods={setFoods}
        onBack={onBack}
        onSave={() => {
          setBusy(true);
          setRequestError(false);
          setDetailsSaved(false);
          void nutritionApi.saveNutritionProfile(nutritionInput)
            .then(() => {
              if (productMode === "nutrition" && structuredExercise !== undefined) {
                return nutritionApi.saveStructuredExercise(structuredExercise);
              }
              return undefined;
            })
            .then(() => nutritionApi.createNutritionEstimate())
            .then(() => setDetailsSaved(true))
            .catch(() => setRequestError(true))
            .finally(() => setBusy(false));
        }}
      />
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
          foods={foods}
          onFoods={setFoods}
          onConditions={setConditions}
          onFlags={setSafetyFlags}
          onMedications={setMedications}
          onPhysicianRestrictions={setPhysicianRestrictions}
          onOtherCondition={setOtherCondition}
          onComplete={saveSafety}
          onBack={() => setStep("personal")}
          startAfterMedical={!draftMode && initialDraft?.safety !== undefined}
        />
      )}
      {step === "pre_account" && <PreAccountNutritionQuestions
          busy={busy} conditions={conditions} foods={foods} budget={budget} dailyActivityLevel={dailyActivityLevel}
        onConditions={setConditions} onFoods={setFoods} onBudget={(value) => setBudget(formatTomanInput(value))}
        onDailyActivityLevel={setDailyActivityLevel}
        onBack={() => setStep("training")}
        onComplete={() => onDraftComplete?.({ safety: safetyInput(), structuredExercise, nutritionBasics: {
          daily_activity_level: dailyActivityLevel, individual_monthly_food_budget_irr: tomanToIrr(budget), budget_style: budgetStyle, plan_style: planStyle,
          allergies: splitNames(foods.allergies).map((name) => ({ name, details: null })), intolerances: splitNames(foods.intolerances).map((name) => ({ name, details: null })), dietary_pattern: foods.dietaryPattern,
        } })}
      />}
      {step === "training" && (
        productMode === "nutrition" ? (
          <NutritionExerciseQuestions
            initialValue={structuredExercise}
            fitnessGoal={values.fitness_goal}
            onBack={() => setStep(draftMode ? "personal" : "safety")}
            onComplete={saveNutritionExercise}
          />
        ) : (
          <GuidedTrainingQuestions
            values={values}
            onChange={updateProfileValue}
            onBack={() => setStep(draftMode ? "personal" : "safety")}
            onComplete={saveTraining}
          />
        )
      )}
      {step === "budget" && (
        <BudgetForm
          busy={busy} budget={budget} budgetStyle={budgetStyle} mealCount={mealCount}
          snackCount={snackCount} startDay={startDay} onBudget={(value) => setBudget(formatTomanInput(value))}
          onBudgetStyle={setBudgetStyle} onMealCount={setMealCount} onSnackCount={setSnackCount}
          onStartDay={setStartDay} onBack={() => setStep(productMode === "nutrition" || !trainingProfileExists ? "training" : "safety")}
    onNext={() => setStep("review")}
        />
      )}
      {step === "review" && (
        <form className="profile-form" onSubmit={finish}>
          <div className="nutrition-review-card">
            <strong>{language === "en" ? `Monthly budget: ${budget} Toman` : `بودجه ماهانه: ${new Intl.NumberFormat("fa-IR").format(Number(budget.replaceAll(",", "")))} تومان`}</strong>
            <span>{language === "en" ? `${mealCount} meals and ${snackCount} snacks per day` : `${mealCount} وعده اصلی و ${snackCount} میان‌وعده در روز`}</span>
            <span>{language === "en" ? "Safety policy" : "سیاست ایمنی"}: {decision?.policy_version}</span>
            <span>{language === "en" ? `Allergies: ${splitNames(foods.allergies).join(", ") || "None"}` : `حساسیت ثبت‌شده: ${splitNames(foods.allergies).join("، ") || "ندارد"}`}</span>
          </div>
          <Actions busy={busy} onBack={() => setStep("budget")} nextLabel={language === "en" ? "Save nutrition profile" : "ثبت پروفایل تغذیه"} />
        </form>
      )}
      {requestError && <p className="form-error" role="alert">{copy.error}</p>}
    </section>
  );
}

function PostAccountNutritionDetails(props: {
  language: "fa" | "en";
  busy: boolean;
  dailyActivityLevel: NutritionProfileInput["daily_activity_level"];
  budget: string;
  budgetStyle: NutritionProfileInput["budget_style"];
  mealCount: string;
  snackCount: string;
  startDay: NutritionProfileInput["preferred_plan_start_day"];
  foods: FoodsState;
  saved: boolean;
  saveError: boolean;
  onDailyActivityLevel: (value: NutritionProfileInput["daily_activity_level"]) => void;
  onBudget: (value: string) => void;
  onBudgetStyle: (value: NutritionProfileInput["budget_style"]) => void;
  onMealCount: (value: string) => void;
  onSnackCount: (value: string) => void;
  onStartDay: (value: NutritionProfileInput["preferred_plan_start_day"]) => void;
  onFoods: (value: FoodsState) => void;
  onBack?: () => void;
  onSave: () => void;
}) {
  const l = (fa: string, en: string) => props.language === "en" ? en : fa;
  return (
    <section className="nutrition-step profile-details-page" dir={props.language === "fa" ? "rtl" : "ltr"}>
      <p className="eyebrow eyebrow--accent">{l("پروفایل", "Profile")}</p>
      <h2 className="fitsho-display">{l("اطلاعات تغذیه‌ای", "Nutrition information")}</h2>
      <form className="profile-form nutrition-details-form" onSubmit={(event) => { event.preventDefault(); props.onSave(); }}>
        <fieldset className="profile-fieldset" disabled={props.busy}>
          <legend>{l("نیاز روزانه و وعده‌ها", "Daily needs and meals")}</legend>
          <SelectField label={l("میزان فعالیت روزانه", "Daily activity level")} value={props.dailyActivityLevel} onChange={(value) => props.onDailyActivityLevel(value as NutritionProfileInput["daily_activity_level"])} options={[["sedentary", l("کم‌تحرک", "Sedentary")], ["light", l("فعالیت سبک", "Light")], ["moderate", l("فعالیت متوسط", "Moderate")], ["very_active", l("بسیار فعال", "Very active")]]} />
          <LabeledInput label={l("بودجه ماهانه غذا (تومان)", "Monthly food budget (Toman)")} inputMode="numeric" required value={props.budget} onChange={props.onBudget} />
          <SelectField label={l("نوع بودجه", "Budget style")} value={props.budgetStyle} onChange={(value) => props.onBudgetStyle(value as NutritionProfileInput["budget_style"])} options={[["strict", l("سخت‌گیرانه", "Strict")], ["flexible", l("انعطاف‌پذیر", "Flexible")]]} />
          <SelectField label={l("وعده اصلی در روز", "Main meals per day")} value={props.mealCount} onChange={props.onMealCount} options={[["2", l("۲ وعده", "2 meals")], ["3", l("۳ وعده", "3 meals")], ["4", l("۴ وعده یا بیشتر", "4 or more meals")]]} />
          <SelectField label={l("میان‌وعده در روز", "Snacks per day")} value={props.snackCount} onChange={props.onSnackCount} options={[["0", l("هیچ‌کدام", "None")], ["1", l("۱ میان‌وعده", "1 snack")], ["2", l("۲ میان‌وعده", "2 snacks")], ["3", l("۳ میان‌وعده یا بیشتر", "3 or more snacks")]]} />
          <SelectField label={l("الگوی غذایی", "Dietary pattern")} value={props.foods.dietaryPattern} onChange={(value) => props.onFoods({ ...props.foods, dietaryPattern: value as FoodsState["dietaryPattern"] })} options={[["omnivore", l("همه‌چیزخوار", "Omnivore")], ["vegetarian", l("گیاه‌خوار", "Vegetarian")], ["vegan", l("وگان", "Vegan")]]} />
        </fieldset>
        <fieldset className="profile-fieldset" disabled={props.busy}>
          <legend>{l("ترجیحات غذایی", "Food preferences")}</legend>
          <TextArea label={l("غذاهایی که دوست داری (اختیاری)", "Foods you like (optional)")} value={props.foods.favourites} onChange={(favourites) => props.onFoods({ ...props.foods, favourites })} />
          <TextArea label={l("غذاهایی که دوست نداری (اختیاری)", "Foods you dislike (optional)")} value={props.foods.disliked} onChange={(disliked) => props.onFoods({ ...props.foods, disliked })} />
          <TextArea label={l("محدودیت مذهبی یا فرهنگی (اختیاری)", "Religious or cultural exclusions (optional)")} value={props.foods.cultural} onChange={(cultural) => props.onFoods({ ...props.foods, cultural })} />
        </fieldset>
        {props.saveError && <p className="form-error" role="alert">{l("تغییرات ذخیره نشد.", "Changes were not saved.")}</p>}
        {props.saved && <p className="profile-save-message profile-save-message--success" role="status">{l("اطلاعات تغذیه‌ای ذخیره شد.", "Nutrition information was saved.")}</p>}
        <div className="profile-actions profile-wizard__actions">
          {props.onBack && <button className="secondary-button" type="button" disabled={props.busy} onClick={props.onBack}>{l("بازگشت", "Back")}</button>}
          <button className="primary-button" type="submit" disabled={props.busy}>{props.busy ? l("در حال ذخیره…", "Saving…") : l("ذخیره اطلاعات", "Save information")}</button>
        </div>
      </form>
    </section>
  );
}

function stepTitle(step: FlowStep, language: "fa" | "en") {
  const fa = {
    loading: "", personal: "اول کمی با هم آشنا شویم", body: "هدفت را دقیق کنیم",
    safety: "اول ایمنی، بعد برنامه", blocked: "", training: "حالا بخش تمرین را هماهنگ کنیم", pre_account: "چند سؤال کوتاه تغذیه",
    budget: "بودجه و وعده‌ها", foods: "", review: "یک مرور کوتاه قبل از ثبت", complete: "",
  };
  const en = {
    loading: "", personal: "Let’s get to know each other", body: "Let’s define your goal",
    safety: "Safety first, then your plan", blocked: "", training: "Let’s align your training", pre_account: "A few quick nutrition questions",
    budget: "Budget and meals", foods: "", review: "A quick review before saving", complete: "",
  };
  return (language === "en" ? en : fa)[step];
}

function stepIntro(step: FlowStep, language: "fa" | "en") {
  const fa = {
    loading: "", personal: "سؤال‌ها کوتاه‌اند و قدم‌به‌قدم پیش می‌رویم.",
    body: "این اطلاعات بین تمرین و تغذیه مشترک است و فقط یک‌بار ثبت می‌شود.",
    safety: "این پاسخ‌ها برای تشخیص پزشکی نیست؛ فقط مسیر ایمن برنامه را مشخص می‌کند.",
    blocked: "", training: "اطلاعات فعلی تمرینت را صفحه‌به‌صفحه نگه می‌داریم.", pre_account: "بعد از ساخت حساب، فقط جزئیات باقی‌ماندهٔ پروفایل را کامل می‌کنیم.",
    budget: "بودجه شخصی خودت را فقط به تومان وارد کن.", foods: "",
    review: "بعد از ثبت، هنوز هیچ برنامه غذایی تولید نمی‌شود.", complete: "",
  };
  const en = {
    loading: "", personal: "The questions are short; we’ll take them one step at a time.",
    body: "Training and nutrition share this information, so we only ask once.",
    safety: "These answers do not provide a diagnosis; they only help keep your plan safe.",
    blocked: "", training: "We’ll keep your current training details one screen at a time.", pre_account: "After account setup, you will only complete the remaining profile details.",
    budget: "Enter your personal food budget in Toman.", foods: "",
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
  physicianRestrictions: string; otherCondition: string; foods: FoodsState;
  onConditions: (value: MedicalConditionCode[]) => void; onFlags: (value: Flags) => void;
  onMedications: (value: string) => void; onPhysicianRestrictions: (value: string) => void;
  onOtherCondition: (value: string) => void; onFoods: (value: FoodsState) => void; onComplete: () => void; onBack: () => void;
  startAfterMedical?: boolean;
}) {
  const l = useLocalizer();
  const firstQuestion = props.startAfterMedical ? 1 : 0;
  const [question, setQuestion] = useState(firstQuestion);
  const titles = [
    l("آیا شرایط پزشکی مشخصی داری؟", "Do you have any medical conditions?"),
    l("کدام موارد ایمنی دربارهٔ تو صدق می‌کند؟", "Do any of these safety considerations apply?"),
    l("در حال حاضر چه داروهایی مصرف می‌کنی؟", "Which medications do you currently take?"),
    l("پزشک محدودیت غذایی خاصی برایت تعیین کرده؟", "Has a physician prescribed dietary restrictions?"),
    l("شرایط دیگری هست که مربی باید بداند؟", "Is there anything else your coach should know?"),
    l("حساسیت یا عدم‌تحمل غذایی داری؟", "Do you have food allergies or intolerances?"),
  ];
  const advance = () => question === titles.length - 1 ? props.onComplete() : setQuestion((current) => current + 1);
  const back = () => question === firstQuestion ? props.onBack() : setQuestion((current) => current - 1);
  return (
    <NutritionQuestionFrame busy={props.busy} current={question} total={titles.length} title={titles[question]} stage={0}
      optional={question >= 2} nextLabel={question === titles.length - 1 ? l("ثبت ارزیابی ایمنی", "Save safety assessment") : undefined}
      onBack={back} onSubmit={advance}>
        {question === 0 && <div className="profile-checkboxes nutrition-option-grid">
          {conditionOptions.map(([code, fa, en]) => (
            <label className="nutrition-option" key={code}><input type="checkbox" checked={props.conditions.includes(code)}
              onChange={() => props.onConditions(props.conditions.includes(code)
                ? props.conditions.filter((item) => item !== code) : [...props.conditions, code])} />{l(fa, en)}</label>
          ))}
        </div>}
        {question === 1 && <div className="profile-checkboxes nutrition-option-grid">{([
          ["dangerous_food_reaction_history", "سابقه واکنش خطرناک غذایی", "History of dangerous food reaction"],
          ["pregnant", "بارداری", "Pregnant"], ["breastfeeding", "شیردهی", "Breastfeeding"],
          ["eating_disorder_diagnosed", "تشخیص اختلال خوردن", "Diagnosed eating disorder"],
          ["eating_disorder_active_symptoms", "علائم فعال اختلال خوردن", "Active eating-disorder symptoms"],
          ["complex_medication_food_interaction", "تداخل پیچیده دارو و غذا", "Complex medication-food interaction"],
          ["emergency_or_danger_symptoms", "علائم خطر یا وضعیت اورژانسی", "Emergency or danger symptoms"],
        ] as const).map(([field, fa, en]) => (
          <label className="nutrition-check nutrition-option" key={field}><input type="checkbox" checked={props.flags[field]}
            onChange={(event) => props.onFlags({ ...props.flags, [field]: event.target.checked })} />{l(fa, en)}</label>
        ))}</div>}
        {question === 2 && <TextArea label={l("داروهای فعلی (اختیاری، هر دارو یک خط)", "Current medications (optional, one per line)")} value={props.medications} onChange={props.onMedications} />}
        {question === 3 && <TextArea label={l("محدودیت غذایی تجویزشده توسط پزشک (اختیاری)", "Physician-prescribed dietary restrictions (optional)")} value={props.physicianRestrictions} onChange={props.onPhysicianRestrictions} />}
        {question === 4 && <TextArea label={l("شرایط مرتبط دیگر (اختیاری)", "Other relevant conditions (optional)")} value={props.otherCondition} onChange={props.onOtherCondition} />}
        {question === 5 && <div className="nutrition-allergy-fields"><TextArea label={l("حساسیت‌های غذایی (اختیاری، با ویرگول جدا کن)", "Food allergies (optional, comma separated)")} value={props.foods.allergies} onChange={(allergies) => props.onFoods({ ...props.foods, allergies })} /><TextArea label={l("عدم‌تحمل‌های غذایی (اختیاری، با ویرگول جدا کن)", "Food intolerances (optional, comma separated)")} value={props.foods.intolerances} onChange={(intolerances) => props.onFoods({ ...props.foods, intolerances })} /></div>}
    </NutritionQuestionFrame>
  );
}

function PreAccountNutritionQuestions(props: {
  busy: boolean; conditions: MedicalConditionCode[]; foods: FoodsState; budget: string;
  dailyActivityLevel: NutritionProfileInput["daily_activity_level"];
  onConditions: (value: MedicalConditionCode[]) => void;
  onFoods: (value: FoodsState) => void; onBudget: (value: string) => void;
  onDailyActivityLevel: (value: NutritionProfileInput["daily_activity_level"]) => void; onBack: () => void; onComplete: () => void;
}) {
  const l = useLocalizer();
  const [question, setQuestion] = useState(0);
  const titles = [
    l("آیا شرایط پزشکی مشخصی داری؟", "Do you have any medical conditions?"),
    l("میزان فعالیت روزانه‌ات چقدر است؟", "How active are you on a typical day?"),
    l("بودجه ماهانه غذای تو چقدر است؟", "What is your monthly food budget?"),
    l("چه سبک غذایی را ترجیح می‌دهی؟", "Which food style do you prefer?"),
  ];
  const advance = () => question === titles.length - 1 ? props.onComplete() : setQuestion((current) => current + 1);
  const back = () => question === 0 ? props.onBack() : setQuestion((current) => current - 1);
  return <NutritionQuestionFrame busy={props.busy} current={question} total={titles.length} title={titles[question]} stage={question === 0 ? 0 : question < 3 ? 1 : 2} nextLabel={question === titles.length - 1 ? l("ادامه و ساخت حساب", "Continue to account setup") : undefined} onBack={back} onSubmit={advance}>
    {question === 0 && <div className="profile-checkboxes nutrition-option-grid">{conditionOptions.map(([code, fa, en]) => <label className="nutrition-option" key={code}><input type="checkbox" checked={props.conditions.includes(code)} onChange={() => props.onConditions(props.conditions.includes(code) ? props.conditions.filter((item) => item !== code) : [...props.conditions, code])} />{l(fa, en)}</label>)}</div>}
    {question === 1 && <SelectField label={l("فعالیت روزانه", "Daily activity")} value={props.dailyActivityLevel} onChange={(value) => props.onDailyActivityLevel(value as NutritionProfileInput["daily_activity_level"])} options={[["sedentary", l("کم‌تحرک", "Mostly sedentary")], ["light", l("کمی فعال", "Lightly active")], ["moderate", l("فعالیت متوسط", "Moderately active")], ["very_active", l("بسیار فعال", "Very active")]]} />}
    {question === 2 && <LabeledInput label={l("بودجه ماهانه غذا (تومان)", "Monthly food budget (Toman)")} inputMode="numeric" required value={props.budget} onChange={props.onBudget} />}
    {question === 3 && <SelectField label={l("سبک غذا", "Food style")} value={props.foods.dietaryPattern} onChange={(dietaryPattern) => props.onFoods({ ...props.foods, dietaryPattern: dietaryPattern as FoodsState["dietaryPattern"] })} options={[["omnivore", l("همه‌چیزخوار", "Omnivore")], ["vegetarian", l("گیاه‌خوار", "Vegetarian")], ["vegan", l("وگان", "Vegan")]]} />}
  </NutritionQuestionFrame>;
}

function BudgetForm(props: {
  busy: boolean; budget: string; budgetStyle: "strict" | "flexible"; mealCount: string;
  snackCount: string; startDay: NutritionProfileInput["preferred_plan_start_day"];
  onBudget: (value: string) => void; onBudgetStyle: (value: "strict" | "flexible") => void;
  onMealCount: (value: string) => void; onSnackCount: (value: string) => void;
  onStartDay: (value: NutritionProfileInput["preferred_plan_start_day"]) => void;
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
  ];
  const advance = () => question === titles.length - 1 ? props.onNext() : setQuestion((current) => current + 1);
  const back = () => question === 0 ? props.onBack() : setQuestion((current) => current - 1);
  return (
    <NutritionQuestionFrame busy={props.busy} current={question} total={titles.length} title={titles[question]} stage={1}
      onBack={back} onSubmit={advance}>
      {question === 0 && <LabeledInput label={l("بودجه ماهانه غذا (تومان)", "Monthly food budget (Toman)")} inputMode="numeric" required value={props.budget} onChange={props.onBudget} />}
      {question === 1 && <SelectField label={l("نوع بودجه", "Budget style")} value={props.budgetStyle} onChange={(value) => props.onBudgetStyle(value as "strict" | "flexible")} options={[["strict", l("سخت‌گیرانه", "Strict")], ["flexible", l("انعطاف‌پذیر", "Flexible")]]} />}
      {question === 2 && <SelectField label={l("وعده اصلی در روز", "Main meals per day")} value={props.mealCount} onChange={props.onMealCount} options={[["2", l("۲ وعده", "2 meals")], ["3", l("۳ وعده", "3 meals")], ["4", l("۴ وعده یا بیشتر", "4 or more meals")]]} />}
      {question === 3 && <SelectField label={l("میان‌وعده در روز", "Snacks per day")} value={props.snackCount} onChange={props.onSnackCount} options={[["0", l("هیچ‌کدام", "None")], ["1", l("۱ میان‌وعده", "1 snack")], ["2", l("۲ میان‌وعده", "2 snacks")], ["3", l("۳ میان‌وعده یا بیشتر", "3 or more snacks")]]} />}
      {question === 4 && <SelectField label={l("روز شروع برنامه", "Plan start day")} value={props.startDay} onChange={(value) => props.onStartDay(value as NutritionProfileInput["preferred_plan_start_day"])} options={[["saturday", l("شنبه", "Saturday")], ["sunday", l("یکشنبه", "Sunday")], ["monday", l("دوشنبه", "Monday")], ["tuesday", l("سه‌شنبه", "Tuesday")], ["wednesday", l("چهارشنبه", "Wednesday")], ["thursday", l("پنجشنبه", "Thursday")], ["friday", l("جمعه", "Friday")]]} />}
    </NutritionQuestionFrame>
  );
}

type FoodsState = {
  favourites: string; disliked: string;
  allergies: string; intolerances: string; cultural: string; workContext: string;
  dietaryPattern: NutritionProfileInput["dietary_pattern"];
  checkIn: boolean; checkInTime: string;
};

function LabeledInput(props: { label: string; value: string; onChange: (value: string) => void; type?: string; min?: string; max?: string; required?: boolean; inputMode?: "numeric" | "decimal" | "text" }) {
  return <div className="profile-field"><label>{props.label}<input type={props.type ?? "text"} inputMode={props.inputMode} min={props.min} max={props.max} required={props.required} value={props.value} onChange={(event) => props.onChange(event.target.value)} /></label></div>;
}

function TextArea(props: { label: string; value: string; onChange: (value: string) => void }) {
  return <div className="profile-field nutrition-question__field"><label>{props.label}<textarea className="nutrition-question__textarea" dir="auto" value={props.value} onChange={(event) => props.onChange(event.target.value)} /></label></div>;
}

function SelectField(props: { label: string; value: string; options: Array<[string, string]>; onChange: (value: string) => void }) {
  return <div className="profile-field"><label>{props.label}<select value={props.value} onChange={(event) => props.onChange(event.target.value)}>{props.options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></div>;
}

function Actions({ busy, onBack, nextLabel }: { busy: boolean; onBack?: () => void; nextLabel: string }) {
  const l = useLocalizer();
  return <div className="profile-actions">{onBack && <button className="secondary-button" type="button" disabled={busy} onClick={onBack}>{l("بازگشت", "Back")}</button>}<button className="primary-button" type="submit" disabled={busy}>{busy ? l("در حال ذخیره…", "Saving…") : nextLabel}</button></div>;
}
