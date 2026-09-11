import { useEffect, useMemo, useRef, useState } from "react";
import { Pressable, Text, View } from "react-native";

import {
  userSelectablePriorityMuscles,
  type ProfileFormValues,
  type TrainingCaution,
  type UserSelectablePriorityMuscle,
} from "@fitician/core/profile";

import { Button, TextField } from "../../ui/components";
import { PublicChoiceCard, PublicQuestionFrame } from "./PublicQuestionFrame";
import { publicOnboardingStyles as styles } from "./publicOnboardingStyles";
import { usePublicAutoAdvance } from "./usePublicAutoAdvance";

type TrainingField =
  | "experience_level"
  | "training_age_months"
  | "training_days_per_week"
  | "training_location"
  | "home_training_setup"
  | "available_equipment"
  | "session_duration_minutes"
  | "training_intensity"
  | "priority_muscle"
  | "training_cautions"
  | "plan_duration_weeks";

type TrainingQuestion =
  | "experience"
  | "trainingAge"
  | "days"
  | "location"
  | "home"
  | "duration"
  | "intensity"
  | "priority"
  | "cautions"
  | "weeks";

export interface GuidedTrainingQuestionsProps {
  readonly onBack: () => void;
  readonly onChange: (
    field: TrainingField,
    value: string | ProfileFormValues["training_cautions"] | ProfileFormValues["available_equipment"],
  ) => void;
  readonly onComplete: (values: ProfileFormValues) => void;
  readonly onRegisterBack?: (handler: () => void) => () => void;
  readonly values: ProfileFormValues;
}

const stages = ["تجربه", "برنامه", "ایمنی"] as const;
const experienceOptions = [
  ["first_month", "ماه اولمه"],
  ["beginner", "مبتدی (زیر ۶ ماه)"],
  ["intermediate", "متوسط (۶ ماه تا ۲ سال)"],
  ["advanced", "پیشرفته (بیش از ۲ سال)"],
] as const;
const durationOptions = [
  ["30", "۲۰ تا ۳۰ دقیقه"],
  ["45", "۳۰ تا ۴۵ دقیقه"],
  ["60", "۴۵ تا ۶۰ دقیقه"],
  ["75", "۶۰ تا ۷۵ دقیقه"],
  ["90", "۷۵ تا ۹۰ دقیقه"],
  ["120", "بیش از ۹۰ دقیقه"],
] as const;
const intensityOptions = [
  ["light", "سبک"],
  ["moderate", "متوسط"],
  ["vigorous", "شدید"],
] as const;
const cautionOptions: readonly TrainingCaution[] = [
  "lower_back",
  "knee",
  "shoulder",
  "neck",
  "wrist",
  "other",
];
const cautionLabels: Record<TrainingCaution, string> = {
  lower_back: "احتیاط برای کمر",
  knee: "احتیاط برای زانو",
  shoulder: "احتیاط برای شانه",
  neck: "احتیاط برای گردن",
  wrist: "احتیاط برای مچ",
  other: "مورد احتیاط دیگر",
};
const priorityLabels: Record<UserSelectablePriorityMuscle, string> = {
  back: "پشت",
  biceps: "جلو بازو",
  calves: "ساق",
  chest: "سینه",
  glutes: "سرینی",
  hamstrings: "همسترینگ",
  quadriceps: "چهارسر ران",
  shoulders: "سرشانه",
  triceps: "پشت بازو",
};

function faNumber(value: number): string {
  return new Intl.NumberFormat("fa-IR").format(value);
}

export function GuidedTrainingQuestions({
  onBack,
  onChange,
  onComplete,
  onRegisterBack,
  values,
}: GuidedTrainingQuestionsProps) {
  const [index, setIndex] = useState(0);
  const [trainingAgeError, setTrainingAgeError] = useState<string | null>(null);
  const { resetAdvancing, selectAndAdvance } = usePublicAutoAdvance();
  const onCompleteRef = useRef(onComplete);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  const questions = useMemo<readonly TrainingQuestion[]>(
    () => [
      "experience",
      "trainingAge",
      "days",
      "location",
      ...(values.training_location === "home" ? ["home" as const] : []),
      "duration",
      "intensity",
      "priority",
      "cautions",
      "weeks",
    ],
    [values.training_location],
  );
  const safeIndex = Math.min(index, questions.length - 1);
  const question = questions[safeIndex];
  const activeStage = ["experience", "trainingAge"].includes(question)
    ? 0
    : ["days", "location", "home", "duration", "intensity", "priority"].includes(question)
      ? 1
      : 2;
  const cautions = values.training_cautions ?? [];

  function advance() {
    if (safeIndex === questions.length - 1) onCompleteRef.current(values);
    else setIndex((current) => current + 1);
  }

  function submit() {
    if (question === "trainingAge") {
      const raw = values.training_age_months.trim();
      if (raw !== "" && (!/^\d+$/u.test(raw) || Number(raw) > 900)) {
        setTrainingAgeError("سابقه تمرین باید عددی بین ۰ تا ۹۰۰ ماه باشد.");
        return;
      }
      setTrainingAgeError(null);
    }
    if (question === "cautions" && values.training_cautions === null) {
      onChange("training_cautions", []);
    }
    advance();
  }

  function handleBack() {
    resetAdvancing();
    if (safeIndex === 0) onBack();
    else setIndex((current) => Math.max(0, current - 1));
  }

  function toggleCaution(value: TrainingCaution) {
    onChange(
      "training_cautions",
      cautions.includes(value)
        ? cautions.filter((item) => item !== value)
        : [...cautions, value],
    );
  }

  const continueButton = (
    <Button
      disabled={question === "trainingAge" ? false : question === "cautions" ? false : question === "experience" ? values.experience_level === "" : false}
      label="ادامه"
      onPress={submit}
    />
  );

  return (
    <PublicQuestionFrame
      activeStage={activeStage}
      footer={question === "trainingAge" || question === "cautions" ? (
        <>
          {question === "cautions" ? (
            <Pressable accessibilityRole="button" onPress={submit}>
              <Text style={styles.textButton}>رد کردن این سؤال</Text>
            </Pressable>
          ) : null}
          {continueButton}
        </>
      ) : undefined}
      onBack={handleBack}
      onRegisterBack={onRegisterBack}
      progressLabel={`تمرین ${safeIndex + 1} از ${questions.length}`}
      question={safeIndex}
      stageLabel="بخش‌های تمرین"
      stages={stages}
      testID="public-training-questions"
      title={questionTitle(question)}
      totalQuestions={questions.length}
    >
      {question === "experience" ? (
        <View style={styles.choiceGrid}>
          {experienceOptions.map(([value, label]) => (
            <PublicChoiceCard
              label={label}
              key={value}
              onPress={() => selectAndAdvance(
                () => onChange("experience_level", value),
                () => setIndex((current) => current + 1),
              )}
              selected={values.experience_level === value}
              value={value}
            />
          ))}
        </View>
      ) : null}
      {question === "trainingAge" ? (
        <TextField
          error={trainingAgeError ?? undefined}
          hint="اختیاری است؛ اگر مطمئن نیستی خالی بگذار."
          inputMode="numeric"
          keyboardType="number-pad"
          label="سابقه تمرین به ماه"
          maxLength={3}
          onChangeText={(value) => {
            setTrainingAgeError(null);
            onChange("training_age_months", value);
          }}
          textDirection="ltr"
          value={values.training_age_months}
        />
      ) : null}
      {question === "days" ? (
        <View style={styles.choiceGrid}>
          {[2, 3, 4, 5, 6].map((value) => (
            <PublicChoiceCard
              label={`${faNumber(value)} روز در هفته`}
              key={value}
              onPress={() => selectAndAdvance(
                () => onChange("training_days_per_week", String(value)),
                () => setIndex((current) => current + 1),
              )}
              selected={values.training_days_per_week === String(value)}
              value={String(value)}
            />
          ))}
        </View>
      ) : null}
      {question === "location" ? (
        <View style={styles.choiceGrid}>
          <PublicChoiceCard
            label="خانه"
            onPress={() => selectAndAdvance(
              () => onChange("training_location", "home"),
              () => setIndex((current) => current + 1),
            )}
            selected={values.training_location === "home"}
            value="home"
          />
          <PublicChoiceCard
            label="باشگاه"
            onPress={() => selectAndAdvance(
              () => onChange("training_location", "gym"),
              () => setIndex((current) => current + 1),
            )}
            selected={values.training_location === "gym"}
            value="gym"
          />
        </View>
      ) : null}
      {question === "home" ? (
        <View style={styles.choiceGrid}>
          <PublicChoiceCard
            label="فقط وزن بدن"
            onPress={() => selectAndAdvance(
              () => {
                onChange("home_training_setup", "bodyweight_only");
                onChange("available_equipment", ["bodyweight", "pull_up_bar"]);
              },
              () => setIndex((current) => current + 1),
            )}
            selected={values.home_training_setup === "bodyweight_only"}
            value="bodyweight_only"
          />
          <PublicChoiceCard
            label="دمبل دارم"
            onPress={() => selectAndAdvance(
              () => {
                onChange("home_training_setup", "dumbbells_available");
                onChange("available_equipment", ["bodyweight", "dumbbell"]);
              },
              () => setIndex((current) => current + 1),
            )}
            selected={values.home_training_setup === "dumbbells_available"}
            value="dumbbells_available"
          />
        </View>
      ) : null}
      {question === "duration" ? (
        <View style={styles.choiceGrid}>
          {durationOptions.map(([value, label]) => (
            <PublicChoiceCard
              label={label}
              key={value}
              onPress={() => selectAndAdvance(
                () => onChange("session_duration_minutes", value),
                () => setIndex((current) => current + 1),
              )}
              selected={values.session_duration_minutes === value}
              value={value}
            />
          ))}
        </View>
      ) : null}
      {question === "intensity" ? (
        <View style={styles.choiceGrid}>
          {intensityOptions.map(([value, label]) => (
            <PublicChoiceCard
              label={label}
              key={value}
              onPress={() => selectAndAdvance(
                () => onChange("training_intensity", value),
                () => setIndex((current) => current + 1),
              )}
              selected={values.training_intensity === value}
              value={value}
            />
          ))}
        </View>
      ) : null}
      {question === "priority" ? (
        <View style={styles.choiceGrid}>
          <PublicChoiceCard
            label="تمرکز ویژه‌ای ندارم"
            onPress={() => selectAndAdvance(
              () => onChange("priority_muscle", ""),
              () => setIndex((current) => current + 1),
            )}
            selected={values.priority_muscle === ""}
            value="none"
          />
          {userSelectablePriorityMuscles.map((value) => (
            <PublicChoiceCard
              label={priorityLabels[value]}
              key={value}
              onPress={() => selectAndAdvance(
                () => onChange("priority_muscle", value),
                () => setIndex((current) => current + 1),
              )}
              selected={values.priority_muscle === value}
              value={value}
            />
          ))}
        </View>
      ) : null}
      {question === "cautions" ? (
        <View style={styles.choiceGrid}>
          {cautionOptions.map((value) => (
            <PublicChoiceCard
              label={cautionLabels[value]}
              key={value}
              onPress={() => toggleCaution(value)}
              selectionRole="checkbox"
              selected={cautions.includes(value)}
              value={value}
            />
          ))}
        </View>
      ) : null}
      {question === "weeks" ? (
        <View style={styles.choiceGrid}>
          {[4, 6, 8].map((value) => (
            <PublicChoiceCard
              label={`${faNumber(value)} هفته`}
              key={value}
              onPress={() => selectAndAdvance(
                () => onChange("plan_duration_weeks", String(value)),
                () => onCompleteRef.current({ ...values, plan_duration_weeks: String(value) }),
              )}
              selected={values.plan_duration_weeks === String(value)}
              value={String(value)}
            />
          ))}
        </View>
      ) : null}
    </PublicQuestionFrame>
  );
}

function questionTitle(question: TrainingQuestion): string {
  return {
    cautions: "برای تمرین مورد احتیاطی داری؟",
    days: "چند روز در هفته تمرین می‌کنی؟",
    duration: "برای هر جلسه چقدر زمان داری؟",
    experience: "چقدر سابقه تمرین مداوم داری؟",
    home: "در خانه چه امکاناتی داری؟",
    intensity: "شدت معمول تمرینت چقدر است؟",
    location: "کجا تمرین می‌کنی؟",
    priority: "دوست داری در برنامه روی کدام عضله بیشتر تمرکز شود؟",
    trainingAge: "چند ماه است منظم تمرین می‌کنی؟",
    weeks: "این برنامه چند هفته باشد؟",
  }[question];
}
