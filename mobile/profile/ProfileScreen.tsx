import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { useRouter } from "expo-router";

import { ApiError } from "@fitician/core";
import type { NutritionProfile } from "@fitician/core/nutrition";
import type {
  FitnessGoal,
  HomeTrainingSetup,
  Equipment,
  Profile,
  ProfileFormValues,
  ProductMode,
  Sex,
  TrainingCaution,
  TrainingIntensity,
  TrainingLocation,
  UserSelectablePriorityMuscle,
} from "@fitician/core/profile";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { useAndroidBackHandler } from "../ui/navigation/BackBehaviorProvider";
import { Button, Card, FormField, Notice, TextField } from "../ui/components";
import { Screen } from "../ui/layout";
import { fiticianTokens } from "../ui/tokens";
import { useMobileRouteSnapshot, useRefreshMobileProfileStatus } from "../ui/navigation/RouteGuards";
import { createProfileApi } from "./profileApi";
import {
  nutritionFormsForProfile,
  nutritionInputForEdit,
  profileFormValuesForProfile,
  profileFormValuesForSharedProfileInput,
  profilePatchForSection,
  sharedProfileInputForEdit,
  validateNutritionEdit,
  validateProfileSection,
  type NutritionEditForms,
} from "./profileModel";
import type { SharedProfile } from "@fitician/core/profile";

type ProfileSection = "personal" | "training" | "nutrition";

type LoadedProfile = {
  readonly mode: ProductMode;
  readonly nutrition: NutritionProfile | null;
  readonly profile: Profile | null;
  readonly shared: SharedProfile;
};

type ProfileFieldErrors = Record<string, string>;

const sexOptions = [
  { label: "زن", value: "female" },
  { label: "مرد", value: "male" },
  { label: "سایر", value: "other" },
  { label: "ترجیح می‌دهم نگویم", value: "prefer_not_to_say" },
] as const;

const goalOptions = [
  { label: "کاهش وزن", value: "lose_weight" },
  { label: "افزایش وزن", value: "gain_weight" },
  { label: "چربی‌سوزی", value: "fat_loss" },
  { label: "عضله‌سازی", value: "build_muscle" },
  { label: "بازترکیب بدنی", value: "body_recomposition" },
  { label: "افزایش قدرت", value: "strength" },
] as const;

const experienceOptions = [
  { label: "ماه اول", value: "first_month" },
  { label: "مبتدی", value: "beginner" },
  { label: "متوسط", value: "intermediate" },
  { label: "پیشرفته", value: "advanced" },
] as const;

const locationOptions = [
  { label: "باشگاه", value: "gym" },
  { label: "خانه", value: "home" },
] as const;

const homeSetupOptions = [
  { label: "فقط وزن بدن", value: "bodyweight_only" },
  { label: "دمبل دارم", value: "dumbbells_available" },
] as const;

const intensityOptions = [
  { label: "سبک", value: "light" },
  { label: "متوسط", value: "moderate" },
  { label: "پرتوان", value: "vigorous" },
] as const;

const durationOptions = [
  { label: "۳۰ دقیقه", value: "30" },
  { label: "۴۵ دقیقه", value: "45" },
  { label: "۶۰ دقیقه", value: "60" },
  { label: "۷۵ دقیقه", value: "75" },
  { label: "۹۰ دقیقه", value: "90" },
  { label: "۱۲۰ دقیقه", value: "120" },
] as const;

const planDurationOptions = [
  { label: "۴ هفته", value: "4" },
  { label: "۶ هفته", value: "6" },
  { label: "۸ هفته", value: "8" },
] as const;

const weekdayOptions = [
  { label: "شنبه", value: "0" },
  { label: "یکشنبه", value: "1" },
  { label: "دوشنبه", value: "2" },
  { label: "سه‌شنبه", value: "3" },
  { label: "چهارشنبه", value: "4" },
  { label: "پنجشنبه", value: "5" },
  { label: "جمعه", value: "6" },
] as const;

const equipmentOptions = [
  { label: "وزن بدن", value: "bodyweight" },
  { label: "دمبل", value: "dumbbell" },
  { label: "هالتر", value: "barbell" },
  { label: "کابل", value: "cable" },
  { label: "دستگاه", value: "machine" },
  { label: "کش", value: "resistance_band" },
  { label: "نیمکت", value: "bench" },
  { label: "میله بارفیکس", value: "pull_up_bar" },
] as const;

const cautionOptions = [
  { label: "کمر", value: "lower_back" },
  { label: "زانو", value: "knee" },
  { label: "شانه", value: "shoulder" },
  { label: "گردن", value: "neck" },
  { label: "مچ دست", value: "wrist" },
  { label: "مورد دیگر", value: "other" },
] as const;

const priorityMuscleOptions = [
  { label: "سینه", value: "chest" },
  { label: "پشت", value: "back" },
  { label: "سرشانه", value: "shoulders" },
  { label: "جلو بازو", value: "biceps" },
  { label: "پشت بازو", value: "triceps" },
  { label: "باسن", value: "glutes" },
  { label: "چهارسر", value: "quadriceps" },
  { label: "همسترینگ", value: "hamstrings" },
  { label: "ساق", value: "calves" },
] as const;

const activityOptions = [
  { label: "کم‌تحرک", value: "sedentary" },
  { label: "فعالیت سبک", value: "light" },
  { label: "فعالیت متوسط", value: "moderate" },
  { label: "خیلی فعال", value: "very_active" },
] as const;

const budgetStyleOptions = [
  { label: "سخت‌گیرانه", value: "strict" },
  { label: "انعطاف‌پذیر", value: "flexible" },
] as const;

const dietaryOptions = [
  { label: "همه‌چیزخوار", value: "omnivore" },
  { label: "گیاه‌خواری", value: "vegetarian" },
  { label: "وگان", value: "vegan" },
] as const;

const mealOptions = [
  { label: "۲ وعده", value: "2" },
  { label: "۳ وعده", value: "3" },
  { label: "۴ وعده یا بیشتر", value: "4" },
] as const;

const snackOptions = [
  { label: "بدون میان‌وعده", value: "0" },
  { label: "۱ میان‌وعده", value: "1" },
  { label: "۲ میان‌وعده", value: "2" },
  { label: "۳ میان‌وعده یا بیشتر", value: "3" },
] as const;

const startDayOptions = [
  { label: "شنبه", value: "saturday" },
  { label: "یکشنبه", value: "sunday" },
  { label: "دوشنبه", value: "monday" },
  { label: "سه‌شنبه", value: "tuesday" },
  { label: "چهارشنبه", value: "wednesday" },
  { label: "پنجشنبه", value: "thursday" },
  { label: "جمعه", value: "friday" },
] as const;

export function ProfileScreen() {
  const auth = useMobileAuth();
  const router = useRouter();
  const snapshot = useMobileRouteSnapshot();
  const refreshProfileStatus = useRefreshMobileProfileStatus();
  const api = useMemo(() => createProfileApi(auth.request), [auth.request]);
  const mode = snapshot.profile.productMode;
  const [loaded, setLoaded] = useState<LoadedProfile | null>(null);
  const [values, setValues] = useState<ProfileFormValues | null>(null);
  const [nutritionForms, setNutritionForms] = useState<NutritionEditForms | null>(null);
  const [section, setSection] = useState<ProfileSection>("personal");
  const [fieldErrors, setFieldErrors] = useState<ProfileFieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setLoaded(null);
    setValues(null);
    setNutritionForms(null);
    setError(null);
    setSaveMessage(null);
    setSection("personal");

    if (auth.user?.id === undefined || mode === null) {
      setLoading(false);
      return () => {
        active = false;
      };
    }

    void Promise.all([
      api.getProfile(),
      api.getSharedProfile(),
      api.getNutritionProfile(),
    ]).then(([profile, shared, nutrition]) => {
      if (!active) return;
      const resolvedShared = profile === null
        ? shared
        : sharedFromProfile(profile, mode);
      if (resolvedShared === null) {
        throw new Error("Shared profile is unavailable");
      }
      setLoaded({ mode, nutrition, profile, shared: resolvedShared });
      setValues(profile === null
        ? profileFormValuesForSharedProfileInput(resolvedShared)
        : profileFormValuesForProfile(profile));
      setNutritionForms(nutrition === null ? null : nutritionFormsForProfile(nutrition));
    }).catch((loadError: unknown) => {
      if (active) setError(profileErrorMessage(loadError));
    }).finally(() => {
      if (active) setLoading(false);
    });

    return () => {
      active = false;
    };
  }, [api, auth.user?.id, mode]);

  const sections = useMemo<ProfileSection[]>(() => {
    if (loaded === null) return ["personal"];
    if (loaded.profile === null && loaded.nutrition !== null) return ["personal", "nutrition"];
    if (loaded.profile !== null && loaded.nutrition !== null) return ["personal", "training", "nutrition"];
    return loaded.profile === null ? ["personal"] : ["personal", "training"];
  }, [loaded]);

  const goBack = useCallback((): boolean => {
    if (busy) return true;
    const index = sections.indexOf(section);
    if (index > 0) {
      setSection(sections[index - 1]);
      setFieldErrors({});
      setSaveMessage(null);
      return true;
    }
    return false;
  }, [busy, section, sections]);

  useAndroidBackHandler("wizard", goBack, loaded !== null && values !== null);

  function updateValue(field: keyof ProfileFormValues, value: ProfileFormValues[typeof field]) {
    setValues((current) => current === null ? current : { ...current, [field]: value });
    setFieldErrors((current) => {
      const next = { ...current };
      delete next[field];
      return next;
    });
    setSaveMessage(null);
  }

  function updateNutritionBasics(
    field: keyof NutritionEditForms["basics"],
    value: string,
  ) {
    setNutritionForms((current) => current === null
      ? current
      : { ...current, basics: { ...current.basics, [field]: value } });
    setFieldErrors((current) => {
      const next = { ...current };
      delete next[field];
      return next;
    });
    setSaveMessage(null);
  }

  function updateNutritionPreference(
    field: keyof NutritionEditForms["preferences"],
    value: string | boolean,
  ) {
    setNutritionForms((current) => current === null
      ? current
      : { ...current, preferences: { ...current.preferences, [field]: value } });
    setFieldErrors((current) => {
      const next = { ...current };
      delete next[field];
      return next;
    });
    setSaveMessage(null);
  }

  async function saveCurrentSection() {
    if (loaded === null || values === null || busy) return;
    setBusy(true);
    setError(null);
    setSaveMessage(null);
    const today = new Date();
    try {
      if (section === "nutrition") {
        if (loaded.nutrition === null || nutritionForms === null) {
          throw new Error("Nutrition profile is unavailable");
        }
        const nutritionErrors = validateNutritionEdit(
          nutritionForms.basics,
          nutritionForms.preferences,
        );
        if (Object.keys(nutritionErrors).length > 0) {
          setFieldErrors(nutritionErrors);
          return;
        }
        const input = nutritionInputForEdit(
          loaded.nutrition,
          nutritionForms.basics,
          nutritionForms.preferences,
        );
        const updated = await api.saveNutritionProfile(input);
        setLoaded((current) => current === null ? current : { ...current, nutrition: updated });
        setNutritionForms(nutritionFormsForProfile(updated));
      } else {
        const errors = validateProfileSection(values, section, today);
        if (Object.keys(errors).length > 0) {
          setFieldErrors(errors);
          return;
        }
        if (section === "personal" && loaded.profile === null) {
          const input = sharedProfileInputForEdit(values);
          const updated = await api.saveSharedProfile(input);
          setLoaded((current) => current === null ? current : { ...current, shared: updated });
          setValues(profileFormValuesForSharedProfileInput(updated));
        } else if (loaded.profile !== null) {
          const patch = profilePatchForSection(values, loaded.profile, section);
          if (Object.keys(patch).length > 0) {
            const updated = await api.updateProfile(patch);
            setLoaded((current) => current === null
              ? current
              : { ...current, profile: updated, shared: sharedFromProfile(updated, current.mode) });
            setValues(profileFormValuesForProfile(updated));
          }
        }
      }
      setFieldErrors({});
      setSaveMessage("تغییرات ذخیره شد.");
      await refreshProfileStatus().catch(() => undefined);
    } catch (saveError) {
      setError(profileErrorMessage(saveError));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <Screen contentWidth="reading" contentContainerStyle={styles.centered}>
        <ActivityIndicator accessibilityLabel="در حال بارگذاری" color={fiticianTokens.colors.aqua} />
        <Text style={styles.mutedText}>در حال بارگذاری پروفایل…</Text>
      </Screen>
    );
  }

  if (error !== null && (loaded === null || values === null)) {
    return (
      <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
        <Text style={styles.brand}>FITICIAN</Text>
        <Notice message={error} variant="danger" />
        <Button label="بازگشت" onPress={() => router.back()} variant="secondary" />
      </Screen>
    );
  }

  if (loaded === null || values === null) return null;

  return (
    <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
      <View style={styles.brandRow}>
        <Text style={styles.brand}>FITICIAN</Text>
        <Text style={styles.eyebrow}>حساب کاربری</Text>
      </View>
      <Text accessibilityRole="header" style={styles.title}>پروفایل من</Text>
      <Text style={styles.intro}>اطلاعات بدنی، تنظیمات تمرین و ترجیحات تغذیه‌ای را از همین‌جا به‌روز کن.</Text>

      <Card style={styles.identityCard} variant="raised">
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>{loaded.shared.display_name.trim().slice(0, 1) || "ف"}</Text>
        </View>
        <View style={styles.identityCopy}>
          <Text style={styles.identityName}>{loaded.shared.display_name}</Text>
          <Text style={styles.mutedText}>{modeLabel(loaded.mode)}</Text>
        </View>
      </Card>

      {error !== null ? <Notice message={error} variant="danger" /> : null}
      {saveMessage !== null ? <Notice message={saveMessage} variant="success" /> : null}

      <View accessibilityRole="tablist" style={styles.sectionTabs}>
        {sections.map((item) => (
          <Pressable
            accessibilityRole="tab"
            accessibilityState={{ selected: item === section }}
            disabled={busy}
            key={item}
            onPress={() => {
              setSection(item);
              setFieldErrors({});
              setSaveMessage(null);
            }}
            style={[styles.sectionTab, item === section && styles.sectionTabActive]}
          >
            <Text style={[styles.sectionTabText, item === section && styles.sectionTabTextActive]}>
              {sectionLabel(item)}
            </Text>
          </Pressable>
        ))}
      </View>

      {section === "personal" ? (
        <PersonalSection
          errors={fieldErrors}
          showCircumferences={loaded.profile !== null}
          values={values}
          onChange={updateValue}
        />
      ) : null}
      {section === "training" ? (
        <TrainingSection errors={fieldErrors} values={values} onChange={updateValue} />
      ) : null}
      {section === "nutrition" && nutritionForms !== null ? (
        <NutritionSection
          basics={nutritionForms.basics}
          errors={fieldErrors}
          preferences={nutritionForms.preferences}
          onBasicsChange={updateNutritionBasics}
          onPreferencesChange={updateNutritionPreference}
        />
      ) : null}

      <View style={styles.actions}>
        <Button disabled={busy} label={section === "personal" ? "بستن" : "بازگشت"} onPress={goBackOrClose(goBack, section, router)} variant="secondary" />
        <Button disabled={busy} label="ذخیره تغییرات" loading={busy} onPress={() => void saveCurrentSection()} />
      </View>
    </Screen>
  );
}

function PersonalSection({
  errors,
  showCircumferences,
  values,
  onChange,
}: {
  readonly errors: ProfileFieldErrors;
  readonly showCircumferences: boolean;
  readonly values: ProfileFormValues;
  readonly onChange: (field: keyof ProfileFormValues, value: ProfileFormValues[keyof ProfileFormValues]) => void;
}) {
  return (
    <Card style={styles.formCard}>
      <Text style={styles.sectionTitle}>اطلاعات شخصی و اندازه‌گیری‌ها</Text>
      <TextField
        autoComplete="name"
        error={errors.display_name}
        label="نام نمایشی"
        onChangeText={(value) => onChange("display_name", value)}
        value={values.display_name}
      />
      <TextField
        error={errors.birth_date}
        keyboardType="numbers-and-punctuation"
        label="تاریخ تولد"
        onChangeText={(value) => onChange("birth_date", value)}
        placeholder="۱۳۷۰-۰۲-۲۲"
        textDirection="ltr"
        value={values.birth_date}
      />
      <ChoiceField
        error={errors.sex}
        label="جنسیت"
        options={sexOptions}
        selected={values.sex}
        onSelect={(value) => onChange("sex", value as Sex)}
      />
      <View style={styles.twoColumns}>
        <TextField
          error={errors.height_cm}
          keyboardType="numeric"
          label="قد (سانتی‌متر)"
          onChangeText={(value) => onChange("height_cm", value)}
          textDirection="ltr"
          value={values.height_cm}
        />
        <TextField
          error={errors.current_weight_kg}
          keyboardType="decimal-pad"
          label="وزن (کیلوگرم)"
          onChangeText={(value) => onChange("current_weight_kg", value)}
          textDirection="ltr"
          value={values.current_weight_kg}
        />
      </View>
      {showCircumferences ? (
        <>
          <Text style={styles.subheading}>اندازه‌های بدنی (اختیاری)</Text>
          <View style={styles.twoColumns}>
            <TextField
              error={errors.shoulder_circumference_cm}
              keyboardType="decimal-pad"
              label="سرشانه (سانتی‌متر)"
              onChangeText={(value) => onChange("shoulder_circumference_cm", value)}
              textDirection="ltr"
              value={values.shoulder_circumference_cm}
            />
            <TextField
              error={errors.waist_circumference_cm}
              keyboardType="decimal-pad"
              label="کمر (سانتی‌متر)"
              onChangeText={(value) => onChange("waist_circumference_cm", value)}
              textDirection="ltr"
              value={values.waist_circumference_cm}
            />
          </View>
          <TextField
            error={errors.hip_circumference_cm}
            keyboardType="decimal-pad"
            label="باسن (سانتی‌متر)"
            onChangeText={(value) => onChange("hip_circumference_cm", value)}
            textDirection="ltr"
            value={values.hip_circumference_cm}
          />
        </>
      ) : (
        <Text style={styles.mutedText}>اندازه دور بدن پس از ساخت پروفایل تمرینی در دسترس است.</Text>
      )}
      <ChoiceField
        error={errors.fitness_goal}
        label="هدف اصلی"
        options={goalOptions}
        selected={values.fitness_goal}
        onSelect={(value) => onChange("fitness_goal", value as FitnessGoal)}
      />
    </Card>
  );
}

function TrainingSection({
  errors,
  values,
  onChange,
}: {
  readonly errors: ProfileFieldErrors;
  readonly values: ProfileFormValues;
  readonly onChange: (field: keyof ProfileFormValues, value: ProfileFormValues[keyof ProfileFormValues]) => void;
}) {
  return (
    <Card style={styles.formCard}>
      <Text style={styles.sectionTitle}>تنظیمات تمرین</Text>
      <ChoiceField
        error={errors.experience_level}
        label="سطح تجربه"
        options={experienceOptions}
        selected={values.experience_level}
        onSelect={(value) => onChange("experience_level", value)}
      />
      <View style={styles.twoColumns}>
        <TextField
          error={errors.training_days_per_week}
          keyboardType="numeric"
          label="روز تمرین در هفته"
          onChangeText={(value) => onChange("training_days_per_week", value)}
          textDirection="ltr"
          value={values.training_days_per_week}
        />
        <TextField
          error={errors.training_age_months}
          keyboardType="numeric"
          label="سابقه تمرین (ماه)"
          onChangeText={(value) => onChange("training_age_months", value)}
          textDirection="ltr"
          value={values.training_age_months}
        />
      </View>
      <ChoiceField
        error={errors.training_location}
        label="محل تمرین"
        options={locationOptions}
        selected={values.training_location}
        onSelect={(value) => {
          onChange("training_location", value as TrainingLocation);
          if (value === "gym") {
            onChange("home_training_setup", "");
            onChange("available_equipment", []);
          }
        }}
      />
      {values.training_location === "home" ? (
        <>
          <ChoiceField
            error={errors.available_equipment}
            label="امکانات خانه"
            options={homeSetupOptions}
            selected={values.home_training_setup}
            onSelect={(value) => onChange("home_training_setup", value as HomeTrainingSetup)}
          />
          <MultiChoiceField
            label="تجهیزات موجود"
            options={equipmentOptions}
            selected={values.available_equipment ?? []}
            onToggle={(value) => {
              const equipment = value as Equipment;
              const current = new Set(values.available_equipment ?? []);
              if (current.has(equipment)) current.delete(equipment);
              else current.add(equipment);
              if (equipment === "bodyweight" && !current.has(equipment)) current.delete("pull_up_bar");
              onChange("available_equipment", equipmentOptions
                .map((option) => option.value)
                .filter((item) => current.has(item)));
            }}
          />
        </>
      ) : null}
      <ChoiceField
        error={errors.session_duration_minutes}
        label="مدت هر جلسه"
        options={durationOptions}
        selected={values.session_duration_minutes}
        onSelect={(value) => onChange("session_duration_minutes", value)}
      />
      <ChoiceField
        error={errors.training_intensity}
        label="شدت تمرین"
        options={intensityOptions}
        selected={values.training_intensity}
        onSelect={(value) => onChange("training_intensity", value as TrainingIntensity)}
      />
      <ChoiceField
        error={errors.plan_duration_weeks}
        label="مدت برنامه"
        options={planDurationOptions}
        selected={values.plan_duration_weeks}
        onSelect={(value) => onChange("plan_duration_weeks", value)}
      />
      <MultiChoiceField
        error={errors.preferred_weekdays}
        label="روزهای ترجیحی"
        options={weekdayOptions}
        selected={(values.preferred_weekdays ?? []).map(String)}
        onToggle={(value) => {
          const day = Number(value);
          const current = new Set(values.preferred_weekdays);
          if (current.has(day)) current.delete(day);
          else current.add(day);
          onChange("preferred_weekdays", [...current].sort((a, b) => a - b));
        }}
      />
      <MultiChoiceField
        error={errors.training_cautions}
        label="ملاحظات ایمنی تمرین"
        options={cautionOptions}
        selected={values.training_cautions ?? []}
        onToggle={(value) => {
          const caution = value as TrainingCaution;
          const current = new Set(values.training_cautions ?? []);
          if (current.has(caution)) current.delete(caution);
          else current.add(caution);
          onChange("training_cautions", [...current]);
        }}
      />
      <ChoiceField
        label="عضله اولویت‌دار"
        options={priorityMuscleOptions}
        selected={values.priority_muscle}
        onSelect={(value) => onChange("priority_muscle", value as UserSelectablePriorityMuscle)}
      />
    </Card>
  );
}

function NutritionSection({
  basics,
  errors,
  preferences,
  onBasicsChange,
  onPreferencesChange,
}: {
  readonly basics: NutritionEditForms["basics"];
  readonly errors: ProfileFieldErrors;
  readonly preferences: NutritionEditForms["preferences"];
  readonly onBasicsChange: (field: keyof NutritionEditForms["basics"], value: string) => void;
  readonly onPreferencesChange: (
    field: keyof NutritionEditForms["preferences"],
    value: string | boolean,
  ) => void;
}) {
  return (
    <Card style={styles.formCard}>
      <Text style={styles.sectionTitle}>ترجیحات تغذیه‌ای</Text>
      <ChoiceField
        label="فعالیت روزانه"
        options={activityOptions}
        selected={basics.daily_activity_level}
        onSelect={(value) => onBasicsChange("daily_activity_level", value)}
      />
      <TextField
        error={errors.monthly_food_budget_toman}
        keyboardType="numeric"
        label="بودجه ماهانه غذا (تومان)"
        onChangeText={(value) => onBasicsChange("monthly_food_budget_toman", value)}
        textDirection="ltr"
        value={basics.monthly_food_budget_toman}
      />
      <ChoiceField
        label="نوع بودجه"
        options={budgetStyleOptions}
        selected={basics.budget_style}
        onSelect={(value) => onBasicsChange("budget_style", value)}
      />
      <TextField
        error={errors.target_weight_change_kg_per_week}
        keyboardType="decimal-pad"
        label="نرخ تغییر وزن هفتگی (اختیاری)"
        onChangeText={(value) => onBasicsChange("target_weight_change_kg_per_week", value)}
        textDirection="ltr"
        value={basics.target_weight_change_kg_per_week}
      />
      <ChoiceField
        label="حالت نرخ وزن"
        options={[
          { label: "ایمن", value: "safe" },
          { label: "انتخاب کاربر", value: "user_override" },
        ]}
        selected={basics.weight_rate_mode}
        onSelect={(value) => onBasicsChange("weight_rate_mode", value)}
      />
      <ChoiceField
        label="الگوی غذایی"
        options={dietaryOptions}
        selected={basics.dietary_pattern}
        onSelect={(value) => onBasicsChange("dietary_pattern", value)}
      />
      <TextField
        label="حساسیت‌های غذایی"
        onChangeText={(value) => onBasicsChange("allergies", value)}
        value={basics.allergies}
      />
      <TextField
        label="عدم‌تحمل‌های غذایی"
        onChangeText={(value) => onBasicsChange("intolerances", value)}
        value={basics.intolerances}
      />
      <ChoiceField
        error={errors.meals_per_day}
        label="وعده اصلی در روز"
        options={mealOptions}
        selected={preferences.meals_per_day}
        onSelect={(value) => onPreferencesChange("meals_per_day", value)}
      />
      <ChoiceField
        error={errors.snacks_per_day}
        label="میان‌وعده در روز"
        options={snackOptions}
        selected={preferences.snacks_per_day}
        onSelect={(value) => onPreferencesChange("snacks_per_day", value)}
      />
      <ChoiceField
        label="روز شروع برنامه"
        options={startDayOptions}
        selected={preferences.preferred_plan_start_day}
        onSelect={(value) => onPreferencesChange("preferred_plan_start_day", value)}
      />
      <TextField
        label="غذاهای مورد علاقه"
        onChangeText={(value) => onPreferencesChange("favourite_foods", value)}
        value={preferences.favourite_foods}
      />
      <TextField
        label="غذاهای نامطلوب"
        onChangeText={(value) => onPreferencesChange("disliked_foods", value)}
        value={preferences.disliked_foods}
      />
      <TextField
        label="محدودیت مذهبی یا فرهنگی"
        onChangeText={(value) => onPreferencesChange("religious_cultural_exclusions", value)}
        value={preferences.religious_cultural_exclusions}
      />
      <TextField
        label="شرایط شیفت کاری"
        onChangeText={(value) => onPreferencesChange("work_shift_context", value)}
        value={preferences.work_shift_context}
      />
      <FormField label="یادآوری ثبت روزانه">
        <View style={styles.switchRow}>
          <Switch
            accessibilityLabel="یادآوری ثبت روزانه"
            onValueChange={(value) => onPreferencesChange("daily_check_in_enabled", value)}
            thumbColor={fiticianTokens.colors.ink}
            trackColor={{ false: fiticianTokens.colors.lineStrong, true: fiticianTokens.colors.aqua }}
            value={preferences.daily_check_in_enabled}
          />
          <Text style={styles.mutedText}>
            {preferences.daily_check_in_enabled ? "فعال" : "غیرفعال"}
          </Text>
        </View>
      </FormField>
      {preferences.daily_check_in_enabled ? (
        <TextField
          error={errors.preferred_check_in_time}
          keyboardType="numbers-and-punctuation"
          label="زمان یادآوری"
          onChangeText={(value) => onPreferencesChange("preferred_check_in_time", value)}
          placeholder="۲۱:۰۰"
          textDirection="ltr"
          value={preferences.preferred_check_in_time}
        />
      ) : null}
    </Card>
  );
}

type ChoiceOption = { readonly label: string; readonly value: string };

function ChoiceField({
  error,
  label,
  options,
  selected,
  onSelect,
}: {
  readonly error?: string;
  readonly label: string;
  readonly options: readonly ChoiceOption[];
  readonly selected: string;
  readonly onSelect: (value: string) => void;
}) {
  return (
    <FormField error={error} label={label}>
      <View style={styles.choiceGrid}>
        {options.map((option) => (
          <Pressable
            accessibilityRole="radio"
            accessibilityState={{ selected: option.value === selected }}
            key={option.value}
            onPress={() => onSelect(option.value)}
            style={[styles.choice, option.value === selected && styles.choiceSelected]}
          >
            <Text style={[styles.choiceText, option.value === selected && styles.choiceTextSelected]}>
              {option.label}
            </Text>
          </Pressable>
        ))}
      </View>
    </FormField>
  );
}

function MultiChoiceField({
  error,
  label,
  options,
  selected,
  onToggle,
}: {
  readonly error?: string;
  readonly label: string;
  readonly options: readonly ChoiceOption[];
  readonly selected: readonly string[];
  readonly onToggle: (value: string) => void;
}) {
  return (
    <FormField error={error} label={label}>
      <View style={styles.choiceGrid}>
        {options.map((option) => {
          const isSelected = selected.includes(option.value);
          return (
            <Pressable
              accessibilityRole="checkbox"
              accessibilityState={{ checked: isSelected }}
              key={option.value}
              onPress={() => onToggle(option.value)}
              style={[styles.choice, isSelected && styles.choiceSelected]}
            >
              <Text style={[styles.choiceText, isSelected && styles.choiceTextSelected]}>
                {option.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </FormField>
  );
}

function sharedFromProfile(profile: Profile, mode: ProductMode): SharedProfile {
  return {
    birth_date: profile.birth_date,
    current_weight_kg: profile.current_weight_kg,
    display_name: profile.display_name,
    fitness_goal: profile.fitness_goal,
    height_cm: profile.height_cm,
    product_mode: mode,
    sex: profile.sex,
    user_id: profile.user_id,
    weight_measured_at: profile.weight_measured_at,
    profile_photo_url: profile.profile_photo_url,
  };
}

function goBackOrClose(
  goBack: () => boolean,
  section: ProfileSection,
  router: ReturnType<typeof useRouter>,
): () => void {
  return () => {
    if (section === "personal") router.back();
    else goBack();
  };
}

function modeLabel(mode: ProductMode): string {
  if (mode === "training") return "مسیر تمرین";
  if (mode === "nutrition") return "مسیر تغذیه";
  return "مسیر تمرین و تغذیه";
}

function sectionLabel(section: ProfileSection): string {
  if (section === "personal") return "شخصی";
  if (section === "training") return "تمرین";
  return "تغذیه";
}

function profileErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.message !== "Request failed") return error.message;
  if (error instanceof Error && error.message !== "") {
    if (error.message.includes("profile")) return "اطلاعات پروفایل در دسترس نیست.";
  }
  return "ذخیره یا دریافت پروفایل انجام نشد. اتصال را بررسی کن و دوباره تلاش کن.";
}

const styles = StyleSheet.create({
  actions: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    marginTop: fiticianTokens.spacing[4],
  },
  avatar: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: 56,
    justifyContent: "center",
    width: 56,
  },
  avatarText: {
    color: fiticianTokens.colors.canvas,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
  },
  brand: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    letterSpacing: 1.4,
    writingDirection: "ltr",
  },
  brandRow: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  centered: {
    alignItems: "center",
    gap: fiticianTokens.spacing[3],
    justifyContent: "center",
  },
  choice: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
    width: "48%",
  },
  choiceGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
    justifyContent: "flex-start",
  },
  choiceSelected: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.aqua,
  },
  choiceText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 21,
    textAlign: "center",
    writingDirection: "rtl",
  },
  choiceTextSelected: {
    color: fiticianTokens.colors.aqua,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  eyebrow: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    writingDirection: "rtl",
  },
  formCard: {
    gap: fiticianTokens.spacing[4],
  },
  identityCard: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  identityCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  identityName: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    textAlign: "right",
    writingDirection: "rtl",
  },
  intro: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 27,
    textAlign: "right",
    writingDirection: "rtl",
  },
  mutedText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },
  screen: {
    gap: fiticianTokens.spacing[4],
    paddingBottom: fiticianTokens.spacing[6],
  },
  sectionTab: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flex: 1,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[2],
  },
  sectionTabActive: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.aqua,
  },
  sectionTabText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    writingDirection: "rtl",
  },
  sectionTabTextActive: {
    color: fiticianTokens.colors.aqua,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  sectionTabs: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  sectionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
    lineHeight: 32,
    textAlign: "right",
    writingDirection: "rtl",
  },
  subheading: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.lg,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  switchRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "flex-end",
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 42,
    textAlign: "right",
    writingDirection: "rtl",
  },
  twoColumns: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
});
