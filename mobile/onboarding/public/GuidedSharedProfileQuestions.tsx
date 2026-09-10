import { useEffect, useMemo, useRef, useState } from "react";
import { Modal, Pressable, ScrollView, Text, View } from "react-native";

import type { ProfileFormValues } from "@fitician/core/profile";

import { Button, AppIcon, TextField } from "../../ui/components";
import { RTL_LAYOUT } from "../../ui/rtl";
import { fiticianTokens } from "../../ui/tokens";
import { PublicChoiceCard, PublicQuestionFrame } from "./PublicQuestionFrame";
import { publicOnboardingStyles as styles } from "./publicOnboardingStyles";
import { usePublicAutoAdvance } from "./usePublicAutoAdvance";

type SharedField = "display_name" | "birth_date" | "sex" | "height_cm" | "current_weight_kg" | "fitness_goal";

export interface GuidedSharedProfileQuestionsProps {
  readonly onBack: () => void;
  readonly onChange: (field: SharedField, value: string) => void;
  readonly onComplete: (values: ProfileFormValues) => void;
  readonly onRegisterBack?: (handler: () => void) => () => void;
  readonly values: ProfileFormValues;
}

const stages = ["شخصی", "بدن", "هدف"] as const;
const titles = [
  "دوست داری چه صدایت کنیم؟",
  "چه تاریخی به دنیا آمدی؟",
  "جنسیتت چیست؟",
  "قد و وزنت چقدر است؟",
  "هدف اصلی تو چیست؟",
] as const;

const sexOptions = [
  { icon: "genderFemale" as const, label: "زن", value: "female" },
  { icon: "genderMale" as const, label: "مرد", value: "male" },
] as const;

const goalOptions = [
  { label: "کاهش وزن 🔻⬆️", value: "lose_weight" },
  { label: "افزایش وزن 🔺️⬇️", value: "gain_weight" },
  { label: "چربی‌سوزی 🔥", value: "fat_loss" },
  { label: "عضله‌سازی 💪", value: "build_muscle" },
  { label: "چربی‌سوزی + عضله‌سازی 🔥💪", value: "body_recomposition" },
] as const;

function faNumber(value: number): string {
  return new Intl.NumberFormat("fa-IR").format(value);
}

function ageOn(birthDate: Date, today: Date): number {
  return today.getUTCFullYear()
    - birthDate.getUTCFullYear()
    - (today.getUTCMonth() < birthDate.getUTCMonth()
      || (today.getUTCMonth() === birthDate.getUTCMonth() && today.getUTCDate() < birthDate.getUTCDate())
      ? 1
      : 0);
}

function validBirthDate(parts: BirthParts): boolean {
  if (!parts.year || !parts.month || !parts.day) return false;
  const date = new Date(0);
  date.setUTCFullYear(Number(parts.year), Number(parts.month) - 1, Number(parts.day));
  date.setUTCHours(0, 0, 0, 0);
  return date.getUTCFullYear() === Number(parts.year)
    && date.getUTCMonth() === Number(parts.month) - 1
    && date.getUTCDate() === Number(parts.day)
    && ageOn(date, new Date()) >= 18
    && ageOn(date, new Date()) <= 100;
}

type BirthParts = { day: string; month: string; year: string };

function DatePartPicker({
  label,
  onChange,
  options,
  testID,
  value,
}: {
  readonly label: string;
  readonly onChange: (value: string) => void;
  readonly options: readonly string[];
  readonly testID: string;
  readonly value: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <View style={styles.dateSelector}>
      <Text style={styles.dateSelectorLabel}>{label}</Text>
      <Pressable
        accessibilityLabel={label}
        accessibilityRole="button"
        onPress={() => setVisible(true)}
        style={styles.dateSelectorButton}
        testID={testID}
      >
        <Text style={styles.dateSelectorValue}>{value ? faNumber(Number(value)) : "—"}</Text>
        <AppIcon color={fiticianTokens.colors.muted} name="chevronDown" size={18} />
      </Pressable>
      <Modal
        accessibilityViewIsModal
        animationType="fade"
        onRequestClose={() => setVisible(false)}
        transparent
        visible={visible}
      >
        <View style={[styles.modalBackdrop, RTL_LAYOUT]}>
          <View style={[styles.modalCard, RTL_LAYOUT]}>
            <Text style={styles.modalTitle}>{label}</Text>
            <ScrollView contentContainerStyle={RTL_LAYOUT}>
              {options.map((option) => (
                <Pressable
                  accessibilityLabel={faNumber(Number(option))}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: value === option }}
                  key={option}
                  onPress={() => {
                    onChange(option);
                    setVisible(false);
                  }}
                  style={[styles.modalOption, value === option && styles.modalOptionSelected]}
                  testID={`${testID}-option-${option}`}
                >
                  <Text style={styles.modalOptionText}>{faNumber(Number(option))}</Text>
                </Pressable>
              ))}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </View>
  );
}

export function GuidedSharedProfileQuestions({
  onBack,
  onChange,
  onComplete,
  onRegisterBack,
  values,
}: GuidedSharedProfileQuestionsProps) {
  const [question, setQuestion] = useState(0);
  const [birthError, setBirthError] = useState<string | null>(null);
  const [showBodyConfirmation, setShowBodyConfirmation] = useState(false);
  const [bodyValuesConfirmed, setBodyValuesConfirmed] = useState(false);
  const [birthParts, setBirthParts] = useState<BirthParts>(() => {
    const [year = "", month = "", day = ""] = values.birth_date.split("-");
    return { day, month, year };
  });
  const { resetAdvancing, selectAndAdvance } = usePublicAutoAdvance();
  const onCompleteRef = useRef(onComplete);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  const years = useMemo(
    () => Array.from({ length: 83 }, (_, index) => String(new Date().getFullYear() - 18 - index)),
    [],
  );
  const daysInSelectedMonth = birthParts.year && birthParts.month
    ? new Date(Number(birthParts.year), Number(birthParts.month), 0).getDate()
    : 31;
  const activeStage = question <= 2 ? 0 : question === 3 ? 1 : 2;
  const needsBodyConfirmation = Number(values.height_cm) < 140
    || Number(values.height_cm) > 210
    || Number(values.current_weight_kg) < 40
    || Number(values.current_weight_kg) > 180;
  const ready = [
    values.display_name.trim().length >= 2 && values.display_name.trim().length <= 80,
    Boolean(birthParts.year && birthParts.month && birthParts.day),
    values.sex !== "",
    Number.isFinite(Number(values.height_cm))
      && Number(values.height_cm) >= 120
      && Number(values.height_cm) <= 230
      && Number.isFinite(Number(values.current_weight_kg))
      && Number(values.current_weight_kg) >= 35
      && Number(values.current_weight_kg) <= 300,
    values.fitness_goal !== "",
  ][question];

  useEffect(() => {
    if (Number(birthParts.day) > daysInSelectedMonth) {
      setBirthParts((current) => ({ ...current, day: "" }));
    }
  }, [birthParts.day, daysInSelectedMonth]);

  function submit() {
    if (question === 1) {
      if (!validBirthDate(birthParts)) {
        setBirthError("تاریخ تولد باید معتبر باشد و سن بین ۱۸ تا ۱۰۰ سال باشد.");
        return;
      }
      setBirthError(null);
      onChange("birth_date", `${birthParts.year}-${birthParts.month.padStart(2, "0")}-${birthParts.day.padStart(2, "0")}`);
    }
    if (question === 3 && needsBodyConfirmation && !bodyValuesConfirmed) {
      setShowBodyConfirmation(true);
      return;
    }
    if (question === titles.length - 1) onCompleteRef.current(values);
    else setQuestion((current) => current + 1);
  }

  function handleBack() {
    resetAdvancing();
    if (question === 0) onBack();
    else setQuestion((current) => current - 1);
  }

  function updateBodyValue(field: "height_cm" | "current_weight_kg", value: string) {
    setShowBodyConfirmation(false);
    setBodyValuesConfirmed(false);
    onChange(field, value);
  }

  return (
    <PublicQuestionFrame
      activeStage={activeStage}
      footer={question === 0 || question === 1 || question === 3 ? (
        <Button
          disabled={!ready}
          label="ادامه"
          onPress={submit}
        />
      ) : undefined}
      onBack={handleBack}
      onRegisterBack={onRegisterBack}
      progressLabel={`مرحله ${question + 1} از ${titles.length}`}
      question={question}
      stageLabel="بخش‌های پروفایل"
      stages={stages}
      testID="public-shared-questions"
      title={titles[question]}
      totalQuestions={titles.length}
    >
      {question === 0 ? (
        <TextField
          autoFocus
          autoCapitalize="words"
          label="نام نمایشی"
          maxLength={80}
          onChangeText={(value) => onChange("display_name", value)}
          value={values.display_name}
        />
      ) : null}
      {question === 1 ? (
        <View style={styles.fieldStack}>
          <Text style={styles.questionDescription}>روز، ماه و سال تولد را انتخاب کن.</Text>
          <View style={styles.dateGrid}>
            <DatePartPicker
              label="روز"
              onChange={(value) => setBirthParts((current) => ({ ...current, day: value }))}
              options={Array.from({ length: daysInSelectedMonth }, (_, index) => String(index + 1))}
              testID="birth-day"
              value={birthParts.day}
            />
            <DatePartPicker
              label="ماه"
              onChange={(value) => setBirthParts((current) => ({ ...current, month: value }))}
              options={Array.from({ length: 12 }, (_, index) => String(index + 1))}
              testID="birth-month"
              value={birthParts.month}
            />
            <DatePartPicker
              label="سال"
              onChange={(value) => setBirthParts((current) => ({ ...current, year: value }))}
              options={years}
              testID="birth-year"
              value={birthParts.year}
            />
          </View>
          {birthError ? <Text style={styles.error}>{birthError}</Text> : null}
        </View>
      ) : null}
      {question === 2 ? (
        <View style={styles.sexChoiceGrid}>
          {sexOptions.map((option) => (
            <PublicChoiceCard
              {...option}
              key={option.value}
              layout="sex"
              onPress={() => selectAndAdvance(
                () => onChange("sex", option.value),
                () => setQuestion(3),
              )}
              selected={values.sex === option.value}
            />
          ))}
        </View>
      ) : null}
      {question === 3 ? (
        <View style={styles.bodyFields}>
          <TextField
            keyboardType="number-pad"
            hint="۱۲۰ تا ۲۳۰ سانتی‌متر"
            label="قد (سانتی‌متر)"
            maxLength={3}
            onChangeText={(value) => updateBodyValue("height_cm", value)}
            textDirection="ltr"
            value={values.height_cm}
          />
          <TextField
            keyboardType="decimal-pad"
            hint="۳۵ تا ۳۰۰ کیلوگرم"
            label="وزن فعلی (کیلوگرم)"
            maxLength={6}
            onChangeText={(value) => updateBodyValue("current_weight_kg", value)}
            textDirection="ltr"
            value={values.current_weight_kg}
          />
          {showBodyConfirmation ? (
            <Pressable
              accessibilityLabel="این مقادیر درست هستند."
              accessibilityRole="checkbox"
              accessibilityState={{ checked: bodyValuesConfirmed }}
              onPress={() => setBodyValuesConfirmed((current) => !current)}
              style={styles.bodyConfirmation}
            >
              <AppIcon
                color={bodyValuesConfirmed ? fiticianTokens.colors.aqua : fiticianTokens.colors.muted}
                name={bodyValuesConfirmed ? "check" : "close"}
                size={20}
              />
              <Text style={styles.bodyConfirmationText}>این مقادیر درست هستند.</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}
      {question === 4 ? (
        <View style={styles.choiceGrid}>
          {goalOptions.map((option) => (
            <PublicChoiceCard
              {...option}
              key={option.value}
              onPress={() => selectAndAdvance(
                () => onChange("fitness_goal", option.value),
                () => onCompleteRef.current({ ...values, fitness_goal: option.value }),
              )}
              selected={values.fitness_goal === option.value}
            />
          ))}
        </View>
      ) : null}
    </PublicQuestionFrame>
  );
}
