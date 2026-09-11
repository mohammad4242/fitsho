import { useEffect, useRef, useState } from "react";
import { Pressable, Text, View } from "react-native";

import type {
  MedicalConditionCode,
  NutritionProfileInput,
  SafetyProfileInput,
  StructuredExerciseInput,
  StructuredExerciseType,
  TrainingIntensity,
} from "@fitician/core/nutrition";
import type { NutritionBasicsDraft, OnboardingState } from "@fitician/core/onboarding";
import type { ProductMode, ProfileFormValues, ProfileInput } from "@fitician/core/profile";
import { irrToToman, tomanToIrr } from "@fitician/core/formatters";
import { profileInputForOnboarding, profileFormValuesForSharedProfile, profileFormValuesForTrainingProfile, emptyProfileFormValues } from "../onboardingForms";
import { normalizeOnboardingDigits } from "../onboardingModel";
import { Button, TextField } from "../../ui/components";
import { fiticianTokens } from "../../ui/tokens";
import { PublicChoiceCard, PublicQuestionFrame } from "./PublicQuestionFrame";
import { publicOnboardingStyles as styles } from "./publicOnboardingStyles";
import { usePublicAutoAdvance } from "./usePublicAutoAdvance";
import { GuidedTrainingQuestions } from "./GuidedTrainingQuestions";

export interface PublicNutritionAnswers {
  readonly nutritionBasics: NutritionBasicsDraft;
  readonly safety: SafetyProfileInput;
  readonly structuredExercise?: StructuredExerciseInput;
  readonly training?: ProfileInput;
}

export interface PublicNutritionOnboardingFlowProps {
  readonly mode: Extract<ProductMode, "nutrition" | "both">;
  readonly onBack: () => void;
  readonly onComplete: (answers: PublicNutritionAnswers) => void;
  readonly onRegisterBack?: (handler: () => void) => () => void;
  readonly state: OnboardingState;
}

type NutritionPhase = "training" | "preAccount";
type PreAccountQuestion = "conditions" | "activity" | "budget" | "dietary";

const conditionOptions: readonly [MedicalConditionCode, string][] = [
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

const safetyFlags = {
  dangerous_food_reaction_history: false,
  pregnant: false,
  breastfeeding: false,
  eating_disorder_diagnosed: false,
  eating_disorder_active_symptoms: false,
  emergency_or_danger_symptoms: false,
  complex_medication_food_interaction: false,
} as const;

const activityOptions = [
  ["sedentary", "کم‌تحرک", "بیشتر روز نشسته، بدون تمرین خاص", "clock"],
  ["light", "کمی فعال", "پیاده‌روی روزانه یا کارهای سبک", "scale"],
  ["moderate", "فعالیت متوسط", "ورزش منظم یا شغل با تحرک ۳ تا ۵ روز در هفته", "flame"],
  ["very_active", "بسیار فعال", "تمرین سنگین روزانه یا فعالیت بدنی شدید", "flash"],
] as const;

const dietaryOptions = [
  ["omnivore", "همه‌چیزخوار", "انواع مواد غذایی شامل گوشت، مرغ، ماهی، لبنیات و گیاهی", "nutrition", false],
  ["vegetarian", "گیاه‌خوار (به‌زودی)", "بدون گوشت، شامل لبنیات و تخم‌مرغ", "nutrition", true],
  ["vegan", "وگان (به‌زودی)", "کاملاً گیاهی، بدون فرآورده‌های حیوانی", "nutrition", true],
] as const;

function safetyFromState(state: OnboardingState): SafetyProfileInput {
  return state.safety ?? {
    ...safetyFlags,
    conditions: [],
    medications: [],
    physician_dietary_restrictions: null,
    other_relevant_condition: null,
  };
}

function formValuesForState(state: OnboardingState): ProfileFormValues {
  if (state.training !== null) return profileFormValuesForTrainingProfile(state.training);
  if (state.shared !== null) return profileFormValuesForSharedProfile(state.shared);
  return emptyProfileFormValues();
}

function nutritionBasicsFromAnswers(
  activity: NutritionProfileInput["daily_activity_level"],
  budget: string,
  dietaryPattern: NutritionProfileInput["dietary_pattern"],
): NutritionBasicsDraft {
  return {
    daily_activity_level: activity,
    individual_monthly_food_budget_irr: tomanToIrr(normalizeOnboardingDigits(budget)),
    budget_style: "strict",
    plan_style: "balanced",
    allergies: [],
    intolerances: [],
    dietary_pattern: dietaryPattern,
  };
}

function CheckboxCard({
  label,
  onPress,
  selected,
}: {
  readonly label: string;
  readonly onPress: () => void;
  readonly selected: boolean;
}) {
  return (
    <Pressable
      accessibilityLabel={label}
      accessibilityRole="checkbox"
      accessibilityState={{ checked: selected }}
      onPress={onPress}
      style={[styles.checkboxCard, selected && styles.checkboxCardSelected]}
    >
      <View style={[styles.checkboxIndicator, selected && styles.checkboxIndicatorSelected]}>
        {selected ? <Text style={{ color: fiticianTokens.colors.canvas }}>✓</Text> : null}
      </View>
      <Text style={styles.checkboxText}>{label}</Text>
    </Pressable>
  );
}

export function PublicNutritionOnboardingFlow({
  mode,
  onBack,
  onComplete,
  onRegisterBack,
  state,
}: PublicNutritionOnboardingFlowProps) {
  const [phase, setPhase] = useState<NutritionPhase>("training");
  const [trainingValues, setTrainingValues] = useState(() => formValuesForState(state));
  const [training, setTraining] = useState<ProfileInput | undefined>(state.training ?? undefined);
  const [structuredExercise, setStructuredExercise] = useState<StructuredExerciseInput | undefined>(state.structuredExercise ?? undefined);
  const [conditions, setConditions] = useState<MedicalConditionCode[]>(() => safetyFromState(state).conditions.map((item) => item.code));
  const [dailyActivity, setDailyActivity] = useState<NutritionProfileInput["daily_activity_level"]>(state.nutrition?.daily_activity_level ?? state.nutritionBasics?.daily_activity_level ?? "moderate");
  const [budget, setBudget] = useState(() => state.nutrition === null
    ? state.nutritionBasics === null ? "" : irrToToman(state.nutritionBasics.individual_monthly_food_budget_irr)
    : irrToToman(state.nutrition.individual_monthly_food_budget_irr));
  const [dietaryPattern, setDietaryPattern] = useState<NutritionProfileInput["dietary_pattern"]>(state.nutrition?.dietary_pattern ?? state.nutritionBasics?.dietary_pattern ?? "omnivore");
  const [question, setQuestion] = useState<PreAccountQuestion>("conditions");
  const [budgetError, setBudgetError] = useState<string | null>(null);
  const onCompleteRef = useRef(onComplete);
  const { resetAdvancing, selectAndAdvance } = usePublicAutoAdvance();

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  function updateTraining(
    field: keyof ProfileFormValues,
    value: string | ProfileFormValues["training_cautions"] | ProfileFormValues["available_equipment"],
  ) {
    setTrainingValues((current) => ({
      ...current,
      [field]: value,
      ...(field === "training_location" && value === "gym" ? { home_training_setup: "" } : {}),
    }));
  }

  function completeTraining(values: ProfileFormValues) {
    try {
      setTraining(profileInputForOnboarding(values, new Date()));
      setPhase("preAccount");
    } catch {
      // The guided component keeps the same field-level constraints as Web;
      // this protects the handoff if a restored draft is malformed.
    }
  }

  function completeExercise(value: StructuredExerciseInput) {
    setStructuredExercise(value);
    setPhase("preAccount");
  }

  function advancePreAccount() {
    if (question === "conditions") setQuestion("activity");
    else if (question === "activity") setQuestion("budget");
    else if (question === "budget") setQuestion("dietary");
    else finishPreAccount();
  }

  function finishPreAccount() {
    const normalizedBudget = normalizeOnboardingDigits(budget.trim());
    if (normalizedBudget === "" || !/\d/u.test(normalizedBudget) || !Number.isFinite(tomanToIrr(normalizedBudget))) {
      setBudgetError("بودجه ماهانه غذا را وارد کن.");
      setQuestion("budget");
      return;
    }
    setBudgetError(null);
    onCompleteRef.current({
      nutritionBasics: nutritionBasicsFromAnswers(dailyActivity, budget, dietaryPattern),
      safety: {
        ...safetyFlags,
        conditions: conditions.map((code) => ({ code, details: null })),
        medications: [],
        physician_dietary_restrictions: null,
        other_relevant_condition: null,
      },
      ...(mode === "nutrition" ? { structuredExercise } : { training }),
    });
  }

  function handleBack() {
    resetAdvancing();
    if (question === "conditions") setPhase("training");
    else if (question === "activity") setQuestion("conditions");
    else if (question === "budget") setQuestion("activity");
    else setQuestion("budget");
  }

  if (phase === "training") {
    if (mode === "both") {
      return (
        <GuidedTrainingQuestions
          onBack={onBack}
          onChange={updateTraining}
          onComplete={completeTraining}
          onRegisterBack={onRegisterBack}
          values={trainingValues}
        />
      );
    }
    return (
      <PublicNutritionExerciseQuestions
        fitnessGoal={state.shared?.fitness_goal}
        initialValue={structuredExercise}
        onBack={onBack}
        onComplete={completeExercise}
        onRegisterBack={onRegisterBack}
      />
    );
  }

  const activeStage = question === "conditions" ? 0 : question === "dietary" ? 2 : 1;
  const title = {
    activity: "میزان فعالیت روزانه‌ات چقدر است؟",
    budget: "بودجه ماهانه غذای تو چقدر است؟",
    conditions: "آیا شرایط پزشکی مشخصی داری؟",
    dietary: "چه سبک غذایی را ترجیح می‌دهی؟",
  }[question];
  const progressIndex = ["conditions", "activity", "budget", "dietary"].indexOf(question);

  return (
    <PublicQuestionFrame
      activeStage={activeStage}
      footer={question === "conditions" || question === "budget" || question === "dietary" ? (
        <Button
          label={question === "dietary" ? "ادامه و ساخت حساب" : "ادامه"}
          onPress={advancePreAccount}
        />
      ) : undefined}
      onBack={handleBack}
      progressLabel={`سؤال ${progressIndex + 1} از 4`}
      question={progressIndex}
      onRegisterBack={onRegisterBack}
      stageLabel="بخش‌های تغذیه"
      stages={["ایمنی", "سبک زندگی", "غذاها"]}
      testID="public-nutrition-pre-account"
      title={title}
      totalQuestions={4}
    >
      {question === "conditions" ? (
        <View style={styles.choiceGrid}>
          {conditionOptions.map(([value, label]) => (
            <CheckboxCard
              key={value}
              label={label}
              onPress={() => setConditions((current) => current.includes(value)
                ? current.filter((item) => item !== value)
                : [...current, value])}
              selected={conditions.includes(value)}
            />
          ))}
        </View>
      ) : null}
      {question === "activity" ? (
        <View style={styles.choiceGrid}>
          {activityOptions.map(([value, label, description, icon]) => (
            <PublicChoiceCard
              description={description}
              icon={icon}
              key={value}
              label={label}
              onPress={() => selectAndAdvance(
                () => setDailyActivity(value),
                advancePreAccount,
              )}
              selected={dailyActivity === value}
              value={value}
            />
          ))}
        </View>
      ) : null}
      {question === "budget" ? (
        <TextField
          error={budgetError ?? undefined}
          hint="بودجه شخصی خودت را فقط به تومان وارد کن."
          inputMode="numeric"
          keyboardType="number-pad"
          label="بودجه ماهانه غذا (تومان)"
          onChangeText={(value) => {
            setBudgetError(null);
            setBudget(value);
          }}
          textDirection="ltr"
          value={budget}
        />
      ) : null}
      {question === "dietary" ? (
        <View style={styles.choiceGrid}>
          {dietaryOptions.map(([value, label, description, icon, disabled]) => (
            <PublicChoiceCard
              description={description}
              disabled={disabled}
              icon={icon}
              key={value}
              label={label}
              onPress={() => {
                if (disabled) return;
                selectAndAdvance(
                  () => setDietaryPattern(value),
                  finishPreAccount,
                );
              }}
              selected={dietaryPattern === value}
              value={value}
            />
          ))}
        </View>
      ) : null}
    </PublicQuestionFrame>
  );
}

type ExerciseQuestion = "trains" | "type" | "days" | "duration" | "intensity";
type ExerciseDraft = {
  readonly days: number | null;
  readonly exerciseType: StructuredExerciseType | null;
  readonly intensity: TrainingIntensity | null;
  readonly minutes: number | null;
  readonly trains: boolean | null;
};

function PublicNutritionExerciseQuestions({
  fitnessGoal,
  initialValue,
  onBack,
  onComplete,
  onRegisterBack,
}: {
  readonly fitnessGoal?: string;
  readonly initialValue?: StructuredExerciseInput;
  readonly onBack: () => void;
  readonly onComplete: (value: StructuredExerciseInput) => void;
  readonly onRegisterBack?: (handler: () => void) => () => void;
}) {
  const initialTraining = initialValue?.trains === true ? initialValue : undefined;
  const [index, setIndex] = useState(0);
  const [blocked, setBlocked] = useState(false);
  const [draft, setDraft] = useState<ExerciseDraft>({
    days: initialTraining?.days_per_week ?? null,
    exerciseType: initialTraining?.exercise_type ?? null,
    intensity: initialTraining?.intensity ?? null,
    minutes: initialTraining?.minutes_per_session ?? null,
    trains: initialValue?.trains ?? null,
  });
  const { resetAdvancing, selectAndAdvance } = usePublicAutoAdvance();
  const questions: readonly ExerciseQuestion[] = draft.trains === false
    ? ["trains"]
    : ["trains", "type", "days", "duration", "intensity"];
  const question = questions[Math.min(index, questions.length - 1)];
  const onCompleteRef = useRef(onComplete);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  function back() {
    resetAdvancing();
    if (index === 0) onBack();
    else setIndex((current) => current - 1);
  }

  function chooseTrains(value: boolean) {
    setBlocked(false);
    if (!value && (fitnessGoal === "build_muscle" || fitnessGoal === "muscle_gain")) {
      setDraft({ days: null, exerciseType: null, intensity: null, minutes: null, trains: false });
      setBlocked(true);
      return;
    }
    if (!value) {
      setDraft({ days: null, exerciseType: null, intensity: null, minutes: null, trains: false });
      selectAndAdvance(() => undefined, () => onCompleteRef.current({ trains: false }));
      return;
    }
    selectAndAdvance(
      () => setDraft((current) => ({ ...current, trains: true })),
      () => setIndex((current) => current + 1),
    );
  }

  return (
    <PublicQuestionFrame
      activeStage={0}
      description="فقط همین اطلاعات برای جلوگیری از دوباره‌شماری انرژی لازم است."
      hideStageTrack
      onBack={back}
      onRegisterBack={onRegisterBack}
      progressLabel={`تمرین ${index + 1} از ${questions.length}`}
      question={index}
      stageLabel="بخش تمرین تغذیه"
      stages={[]}
      testID="public-nutrition-exercise"
      title={exerciseTitle(question)}
      totalQuestions={questions.length}
    >
      {question === "trains" ? (
        <View style={styles.choiceGrid}>
          <PublicChoiceCard
            label="منظم تمرین می‌کنم"
            onPress={() => chooseTrains(true)}
            selected={draft.trains === true}
            value="true"
          />
          <PublicChoiceCard
            label="تمرین نمی‌کنم"
            onPress={() => chooseTrains(false)}
            selected={draft.trains === false}
            value="false"
          />
        </View>
      ) : null}
      {question === "type" ? (
        <View style={styles.choiceGrid}>
          {([
            ["resistance", "تمرین مقاومتی"],
            ["endurance", "تمرین هوازی و استقامتی"],
            ["mixed", "تمرین ترکیبی"],
            ["other", "نوع دیگر"],
          ] as const).map(([value, label]) => (
            <PublicChoiceCard
              label={label}
              key={value}
              onPress={() => selectAndAdvance(
                () => setDraft((current) => ({ ...current, exerciseType: value })),
                () => setIndex((current) => current + 1),
              )}
              selected={draft.exerciseType === value}
              value={value}
            />
          ))}
        </View>
      ) : null}
      {question === "days" ? (
        <View style={styles.choiceGrid}>
          {[1, 2, 3, 4, 5, 6, 7].map((value) => (
            <PublicChoiceCard
              label={`${new Intl.NumberFormat("fa-IR").format(value)} روز در هفته`}
              key={value}
              onPress={() => selectAndAdvance(
                () => setDraft((current) => ({ ...current, days: value })),
                () => setIndex((current) => current + 1),
              )}
              selected={draft.days === value}
              value={String(value)}
            />
          ))}
        </View>
      ) : null}
      {question === "duration" ? (
        <View style={styles.choiceGrid}>
          {([
            [30, "۲۰–۳۰ دقیقه"],
            [45, "۳۰–۴۵ دقیقه"],
            [60, "۴۵–۶۰ دقیقه"],
            [75, "۶۰–۷۵ دقیقه"],
            [90, "۷۵–۹۰ دقیقه"],
            [120, "بیش از ۹۰ دقیقه"],
          ] as const).map(([value, label]) => (
            <PublicChoiceCard
              label={label}
              key={value}
              onPress={() => selectAndAdvance(
                () => setDraft((current) => ({ ...current, minutes: value })),
                () => setIndex((current) => current + 1),
              )}
              selected={draft.minutes === value}
              value={String(value)}
            />
          ))}
        </View>
      ) : null}
      {question === "intensity" ? (
        <View style={styles.choiceGrid}>
          {([
            ["light", "سبک"],
            ["moderate", "متوسط"],
            ["vigorous", "شدید"],
          ] as const).map(([value, label]) => (
            <PublicChoiceCard
              label={label}
              key={value}
              onPress={() => selectAndAdvance(
                () => setDraft((current) => ({ ...current, intensity: value })),
                () => onCompleteRef.current({
                  trains: true,
                  exercise_type: draft.exerciseType ?? "other",
                  days_per_week: draft.days ?? 1,
                  minutes_per_session: draft.minutes ?? 30,
                  intensity: value,
                }),
              )}
              selected={draft.intensity === value}
              value={value}
            />
          ))}
        </View>
      ) : null}
      {blocked ? <Text accessibilityRole="alert" style={styles.error}>برای این هدف باید هدفت را تغییر بدهی یا مسیر تمرینی را انتخاب کنی.</Text> : null}
    </PublicQuestionFrame>
  );
}

function exerciseTitle(question: ExerciseQuestion): string {
  return {
    days: "چند روز در هفته تمرین می‌کنی؟",
    duration: "هر جلسه معمولاً چقدر طول می‌کشد؟",
    intensity: "شدت معمول تمرینت چقدر است؟",
    trains: "در حال حاضر تمرین منظم داری؟",
    type: "نوع اصلی تمرینت چیست؟",
  }[question];
}
