import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ActivityIndicator,
  Image,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { useRouter } from "expo-router";

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
import {
  AppIcon,
  Button,
  Card,
  FormField,
  Notice,
  PageHeading,
  TextField,
} from "../ui/components";
import { Screen } from "../ui/layout";
import { mobileRequestErrorMessage } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import { useMobileRouteSnapshot, useRefreshMobileProfileStatus } from "../ui/navigation/RouteGuards";
import { createProfileApi } from "./profileApi";
import { ProfilePhotoControl } from "./ProfilePhotoControl";
import { AccountPrivacyLinks } from "../accountDeletion/AccountPrivacyLinks";
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
] as const;

const goalOptions = [
  { label: "کاهش وزن", value: "lose_weight" },
  { label: "افزایش وزن", value: "gain_weight" },
  { label: "چربی‌سوزی", value: "fat_loss" },
  { label: "عضله‌سازی", value: "build_muscle" },
  { label: "ریکامپ", value: "body_recomposition" },
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
      <PageHeading title="پروفایل ورزشی" />

      <ProfileOverviewCard
        email={auth.user?.email ?? null}
        mode={loaded.mode}
        profile={loaded.profile}
        shared={loaded.shared}
        onEdit={() => {
          setSection("personal");
          setFieldErrors({});
          setSaveMessage(null);
        }}
      />
      <ProfilePhotoControl
        initialUrl={loaded.shared.profile_photo_url}
        label={loaded.shared.display_name}
        onChanged={(nextUrl) => {
          setLoaded((current) => current === null
            ? current
            : { ...current, shared: { ...current.shared, profile_photo_url: nextUrl } });
        }}
      />

      {section === "personal" ? (
        <ProfileMeasurements
          shared={loaded.shared}
          onOpenProgress={() => router.push("/member/body-analysis-history")}
        />
      ) : null}

      {error !== null ? <Notice message={error} variant="danger" /> : null}
      {saveMessage !== null ? <Notice message={saveMessage} variant="success" /> : null}

      <ProfileSectionProgress
        accessibilityLabel="بخش ویرایش پروفایل"
        disabled={busy}
        onChange={(value) => {
          setSection(value);
          setFieldErrors({});
          setSaveMessage(null);
        }}
        sections={sections}
        selectedSection={section}
      />

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

      <AccountPrivacyLinks />
      <View style={styles.actions}>
        <Button disabled={busy} label="ذخیره تغییرات" loading={busy} onPress={() => void saveCurrentSection()} />
        <Button disabled={busy} label={section === "personal" ? "بستن" : "بازگشت"} onPress={goBackOrClose(goBack, section, router)} variant="secondary" />
      </View>
    </Screen>
  );
}

function ProfileSectionProgress({
  accessibilityLabel,
  disabled,
  onChange,
  sections,
  selectedSection,
}: {
  readonly accessibilityLabel: string;
  readonly disabled: boolean;
  readonly onChange: (section: ProfileSection) => void;
  readonly sections: readonly ProfileSection[];
  readonly selectedSection: ProfileSection;
}) {
  const currentIndex = Math.max(0, sections.indexOf(selectedSection));

  return (
    <View
      accessibilityLabel={accessibilityLabel}
      accessibilityRole="radiogroup"
      style={styles.profileProgress}
      testID="profile-section-tabs"
    >
      <Text style={styles.profileProgressCount}>
        مرحله {formatProfileNumber(currentIndex + 1)} از {formatProfileNumber(sections.length)}
      </Text>
      <View style={styles.progressSteps}>
        {sections.length > 1 ? <View pointerEvents="none" style={styles.progressLine} /> : null}
        {sections.map((item, index) => {
          const isActive = index <= currentIndex;
          const isCurrent = index === currentIndex;
          return (
            <Pressable
              accessible
              accessibilityLabel={sectionLabel(item)}
              accessibilityRole="radio"
              accessibilityState={{ disabled, selected: isCurrent }}
              disabled={disabled}
              key={item}
              onPress={() => {
                if (!disabled && !isCurrent) onChange(item);
              }}
              style={[
                styles.progressStep,
                isActive && styles.progressStepActive,
                isCurrent && styles.progressStepCurrent,
              ]}
            >
              <View style={[styles.progressBadge, isActive && styles.progressBadgeActive, isCurrent && styles.progressBadgeCurrent]}>
                <AppIcon
                  color={isActive ? fiticianTokens.colors.canvas : fiticianTokens.colors.muted}
                  name={sectionIcon(item)}
                  size={18}
                />
              </View>
              <Text style={[styles.progressStepLabel, isActive && styles.progressStepLabelActive]}>
                {sectionLabel(item)}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function ProfileFormGroup({
  children,
  icon,
  title,
}: {
  readonly children: ReactNode;
  readonly icon: "nutrition" | "profile" | "target" | "training";
  readonly title: string;
}) {
  return (
    <Card style={styles.formGroup} variant="default">
      <View style={styles.formGroupHeader}>
        <Text style={styles.formGroupTitle}>{title}</Text>
        <View style={styles.formGroupIcon}>
          <AppIcon color={fiticianTokens.colors.aqua} name={icon} size={18} />
        </View>
      </View>
      <View style={styles.formGroupFields}>{children}</View>
    </Card>
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
    <View style={styles.formGroups}>
      <ProfileFormGroup icon="profile" title="مشخصات فردی">
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
      </ProfileFormGroup>

      <ProfileFormGroup icon="target" title="بدن و هدف">
        <View style={styles.twoColumns}>
          <View style={styles.column}>
            <TextField
              error={errors.height_cm}
              keyboardType="numeric"
              label="قد (سانتی‌متر)"
              onChangeText={(value) => onChange("height_cm", value)}
              textDirection="ltr"
              value={values.height_cm}
            />
          </View>
          <View style={styles.column}>
            <TextField
              error={errors.current_weight_kg}
              keyboardType="decimal-pad"
              label="وزن (کیلوگرم)"
              onChangeText={(value) => onChange("current_weight_kg", value)}
              textDirection="ltr"
              value={values.current_weight_kg}
            />
          </View>
        </View>
        {showCircumferences ? (
          <>
            <View style={styles.measurementHeading}>
              <Text style={styles.subheading}>اندازه‌های بدنی</Text>
              <Text style={styles.optionalBadge}>اختیاری</Text>
            </View>
            <View style={styles.twoColumns}>
              <View style={styles.column}>
                <TextField
                  error={errors.shoulder_circumference_cm}
                  keyboardType="decimal-pad"
                  label="دور شانه (سانتی‌متر)"
                  onChangeText={(value) => onChange("shoulder_circumference_cm", value)}
                  textDirection="ltr"
                  value={values.shoulder_circumference_cm}
                />
              </View>
              <View style={styles.column}>
                <TextField
                  error={errors.waist_circumference_cm}
                  keyboardType="decimal-pad"
                  label="دور کمر (سانتی‌متر)"
                  onChangeText={(value) => onChange("waist_circumference_cm", value)}
                  textDirection="ltr"
                  value={values.waist_circumference_cm}
                />
              </View>
            </View>
            <View style={styles.singleColumn}>
              <TextField
                error={errors.hip_circumference_cm}
                keyboardType="decimal-pad"
                label="دور باسن (سانتی‌متر)"
                onChangeText={(value) => onChange("hip_circumference_cm", value)}
                textDirection="ltr"
                value={values.hip_circumference_cm}
              />
            </View>
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
      </ProfileFormGroup>
    </View>
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
    <ProfileFormGroup icon="training" title="تنظیمات تمرین">
      <ChoiceField
        error={errors.experience_level}
        label="سطح تجربه"
        options={experienceOptions}
        selected={values.experience_level}
        onSelect={(value) => onChange("experience_level", value)}
      />
      <View style={styles.twoColumns}>
        <View style={styles.column}>
          <TextField
            error={errors.training_days_per_week}
            keyboardType="numeric"
            label="روز تمرین در هفته"
            onChangeText={(value) => onChange("training_days_per_week", value)}
            textDirection="ltr"
            value={values.training_days_per_week}
          />
        </View>
        <View style={styles.column}>
          <TextField
            error={errors.training_age_months}
            keyboardType="numeric"
            label="سابقه تمرین (ماه)"
            onChangeText={(value) => onChange("training_age_months", value)}
            textDirection="ltr"
            value={values.training_age_months}
          />
        </View>
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
    </ProfileFormGroup>
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
    <ProfileFormGroup icon="nutrition" title="ترجیحات تغذیه‌ای">
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
          <Text style={styles.mutedText}>
            {preferences.daily_check_in_enabled ? "فعال" : "غیرفعال"}
          </Text>
          <Switch
            accessibilityLabel="یادآوری ثبت روزانه"
            onValueChange={(value) => onPreferencesChange("daily_check_in_enabled", value)}
            thumbColor={fiticianTokens.colors.ink}
            trackColor={{ false: fiticianTokens.colors.lineStrong, true: fiticianTokens.colors.aqua }}
            value={preferences.daily_check_in_enabled}
          />
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
    </ProfileFormGroup>
  );
}

function ProfileOverviewCard({
  email,
  mode,
  profile,
  shared,
  onEdit,
}: {
  readonly email: string | null;
  readonly mode: ProductMode;
  readonly profile: Profile | null;
  readonly shared: SharedProfile;
  readonly onEdit: () => void;
}) {
  const stats = [
    { direction: "ltr" as const, icon: "ruler" as const, label: "قد", value: `${formatProfileNumber(shared.height_cm)} سانتی‌متر` },
    { direction: "ltr" as const, icon: "scale" as const, label: "وزن", value: `${formatProfileNumber(shared.current_weight_kg)} کیلوگرم` },
    { direction: "ltr" as const, icon: "calendar" as const, label: "سن", value: formatProfileNumber(ageFromBirthDate(shared.birth_date)) },
    {
      direction: "ltr" as const,
      icon: "flame" as const,
      label: "فعالیت",
      value: profile?.training_days_per_week
        ? `${formatProfileNumber(profile.training_days_per_week)} روز در هفته`
        : "ثبت نشده",
    },
    { direction: "rtl" as const, icon: "target" as const, label: "هدف", value: goalLabel(shared.fitness_goal) },
  ];

  return (
    <Card accessibilityLabel="خلاصه پروفایل" style={styles.overviewCard} variant="raised">
      <View style={styles.summaryIdentityRow}>
        {shared.profile_photo_url === null || shared.profile_photo_url === undefined ? (
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{shared.display_name.trim().slice(0, 1) || "ف"}</Text>
          </View>
        ) : (
          <Image accessibilityLabel={shared.display_name} source={{ uri: shared.profile_photo_url }} style={styles.summaryPhoto} />
        )}
        <View style={styles.overviewCopy}>
          <Text style={styles.overviewTitle}>{shared.display_name}</Text>
          {email ? <Text numberOfLines={1} style={styles.email}>{email}</Text> : null}
          <Text style={styles.overviewSubtitle}>{modeLabel(mode)}</Text>
        </View>
        <Pressable accessibilityLabel="ویرایش پروفایل" accessibilityRole="button" onPress={onEdit} style={styles.summaryEdit}>
          <Text style={styles.summaryEditText}>ویرایش</Text>
        </Pressable>
      </View>
      <View style={styles.overviewStats}>
        {stats.map((stat, index) => (
          <ProfileStat
            direction={stat.direction}
            icon={stat.icon}
            key={stat.label}
            label={stat.label}
            separated={index % 3 !== 0}
            value={stat.value}
          />
        ))}
      </View>
    </Card>
  );
}

function ProfileStat({
  icon,
  label,
  direction,
  separated = false,
  value,
}: {
  readonly icon: "calendar" | "flame" | "ruler" | "scale" | "target";
  readonly label: string;
  readonly direction: "ltr" | "rtl";
  readonly separated?: boolean;
  readonly value: string;
}) {
  return (
    <View style={[styles.overviewStat, separated && styles.overviewStatSeparated]}>
      <View style={styles.overviewStatCopy}>
        <Text style={styles.overviewStatLabel}>{label}</Text>
        <Text style={[styles.overviewStatValue, direction === "ltr" && styles.overviewStatNumeric]}>{value}</Text>
      </View>
      <View style={styles.overviewStatIcon}>
        <AppIcon color={fiticianTokens.colors.aqua} name={icon} size={17} />
      </View>
    </View>
  );
}

function ProfileMeasurements({
  shared,
  onOpenProgress,
}: {
  readonly shared: SharedProfile;
  readonly onOpenProgress: () => void;
}) {
  const measuredAt = formatProfileDate(shared.weight_measured_at);

  return (
    <View style={styles.measurementStack}>
      <Card style={styles.measurementCard} variant="raised">
        <View style={styles.measurementRow}>
          <View style={styles.measurementCopy}>
            <Text accessibilityRole="header" style={styles.measurementTitle}>آخرین اندازه‌گیری وزن</Text>
            <Text style={styles.measurementValue}>{formatProfileNumber(shared.current_weight_kg)} کیلوگرم</Text>
          </View>
          <Text style={styles.measurementDate}>ثبت‌شده در {measuredAt}</Text>
        </View>
      </Card>
      <Card style={styles.measurementCard} variant="default">
        <View style={styles.measurementRow}>
          <View style={styles.measurementCopy}>
            <Text accessibilityRole="header" style={styles.measurementTitle}>تحلیل بدن</Text>
            <Text numberOfLines={2} style={styles.measurementDescription}>
              اختیاری — برای برنامه تمرینی دقیق‌تر و شخصی‌تر، عکس‌های استاندارد بدن را اضافه کن.
            </Text>
          </View>
          <Pressable
            accessible
            accessibilityLabel="مشاهده روند بدن"
            accessibilityRole="button"
            onPress={onOpenProgress}
            style={styles.measurementAction}
          >
            <Text style={styles.measurementActionText}>مشاهده روند بدن</Text>
          </Pressable>
        </View>
      </Card>
    </View>
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
    <FormField error={error} label={label} style={styles.choiceField}>
      <View style={styles.choiceGrid}>
        {options.map((option) => (
          <Pressable
            accessible
            accessibilityLabel={option.label}
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
    <FormField error={error} label={label} style={styles.choiceField}>
      <View style={styles.choiceGrid}>
        {options.map((option) => {
          const isSelected = selected.includes(option.value);
          return (
            <Pressable
              accessible
              accessibilityLabel={option.label}
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
  if (section === "training") return "تمرینی";
  return "تغذیه‌ای";
}

function sectionIcon(section: ProfileSection): "nutrition" | "profile" | "training" {
  if (section === "personal") return "profile";
  if (section === "training") return "training";
  return "nutrition";
}

function goalLabel(goal: FitnessGoal): string {
  const labels: Record<FitnessGoal, string> = {
    body_recomposition: "ریکامپ",
    build_muscle: "عضله‌سازی",
    fat_loss: "چربی‌سوزی",
    gain_weight: "افزایش وزن",
    improve_fitness: "بهبود آمادگی",
    lose_weight: "کاهش وزن",
    maintain_weight: "حفظ وزن",
    strength: "افزایش قدرت",
  };
  return labels[goal];
}

function formatProfileNumber(value: number): string {
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 }).format(value);
}

function ageFromBirthDate(value: string): number {
  const birth = new Date(`${value}T00:00:00Z`);
  const now = new Date();
  let age = now.getUTCFullYear() - birth.getUTCFullYear();
  if (
    now.getUTCMonth() < birth.getUTCMonth()
    || (now.getUTCMonth() === birth.getUTCMonth() && now.getUTCDate() < birth.getUTCDate())
  ) {
    age -= 1;
  }
  return age;
}

function formatProfileDate(value: string): string {
  return new Intl.DateTimeFormat("fa-IR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function profileErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message !== "") {
    if (error.message.includes("profile")) return "اطلاعات پروفایل در دسترس نیست.";
  }
  return mobileRequestErrorMessage(error, "ذخیره یا دریافت پروفایل انجام نشد. اتصال را بررسی کن و دوباره تلاش کن.");
}

const styles = StyleSheet.create({
  actions: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    marginTop: fiticianTokens.spacing[2],
  },
  avatar: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: 52,
    justifyContent: "center",
    width: 52,
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
    flexBasis: "48%",
    flexGrow: 1,
    flexShrink: 1,
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    minWidth: 0,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: 10,
  },
  choiceField: {
    gap: fiticianTokens.spacing[2],
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
    elevation: 1,
    shadowColor: fiticianTokens.colors.aqua,
    shadowOffset: { height: 1, width: 0 },
    shadowOpacity: 0.18,
    shadowRadius: 4,
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
  column: {
    flex: 1,
    minWidth: 0,
  },
  formGroup: {
    gap: fiticianTokens.spacing[3],
    padding: 14,
  },
  formGroupFields: {
    gap: fiticianTokens.spacing[3],
  },
  formGroupHeader: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  formGroupIcon: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    height: 32,
    justifyContent: "center",
    width: 32,
  },
  formGroups: {
    gap: fiticianTokens.spacing[3],
  },
  formGroupTitle: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.lg,
    lineHeight: 24,
    textAlign: "right",
    writingDirection: "rtl",
  },
  email: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "ltr",
  },
  mutedText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },
  overviewCard: {
    gap: 0,
    padding: fiticianTokens.spacing[3],
  },
  overviewCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  overviewStat: {
    alignItems: "center",
    flexBasis: "31%",
    flexDirection: "row",
    flexGrow: 1,
    flexShrink: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
    paddingHorizontal: fiticianTokens.spacing[1],
    paddingVertical: 8,
  },
  overviewStatSeparated: {
    borderRightColor: fiticianTokens.colors.line,
    borderRightWidth: 1,
  },
  overviewStatCopy: {
    flex: 1,
    gap: 3,
    minWidth: 0,
  },
  overviewStatIcon: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    height: 30,
    justifyContent: "center",
    width: 30,
  },
  overviewStats: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
    paddingTop: fiticianTokens.spacing[2],
  },
  summaryEdit: {
    alignItems: "center",
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    minWidth: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[1],
  },
  overviewStatLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    textAlign: "right",
    writingDirection: "rtl",
  },
  overviewStatValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 11,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  overviewStatNumeric: {
    writingDirection: "ltr",
  },
  overviewSubtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  overviewTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 29,
    textAlign: "right",
    writingDirection: "rtl",
  },
  summaryEditText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
    writingDirection: "rtl",
  },
  summaryIdentityRow: {
    alignItems: "center",
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    paddingBottom: fiticianTokens.spacing[3],
  },
  summaryPhoto: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderRadius: fiticianTokens.radii.pill,
    height: 52,
    width: 52,
  },
  measurementCard: {
    minHeight: 76,
    padding: fiticianTokens.spacing[3],
  },
  measurementCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  measurementDate: {
    color: fiticianTokens.colors.muted,
    flexShrink: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    maxWidth: "38%",
    textAlign: "right",
    writingDirection: "rtl",
  },
  measurementDescription: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
    textAlign: "right",
    writingDirection: "rtl",
  },
  measurementHeading: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  measurementRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  measurementTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  measurementAction: {
    alignItems: "center",
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    minWidth: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[2],
  },
  measurementActionText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
    writingDirection: "rtl",
  },
  measurementStack: {
    gap: fiticianTokens.spacing[2],
  },
  measurementValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "ltr",
  },
  optionalBadge: {
    backgroundColor: fiticianTokens.colors.surfaceHighlight,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: 3,
    writingDirection: "rtl",
  },
  profileProgress: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.card,
    borderWidth: 1,
    elevation: fiticianTokens.shadows.soft.elevation,
    gap: fiticianTokens.spacing[2],
    padding: fiticianTokens.spacing[3],
    shadowColor: fiticianTokens.shadows.soft.color,
    shadowOffset: fiticianTokens.shadows.soft.offset,
    shadowOpacity: fiticianTokens.shadows.soft.opacity,
    shadowRadius: fiticianTokens.shadows.soft.radius,
  },
  profileProgressCount: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  progressBadge: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    height: 40,
    justifyContent: "center",
    width: 40,
  },
  progressBadgeActive: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  progressBadgeCurrent: {
    elevation: fiticianTokens.shadows.glow.elevation,
    shadowColor: fiticianTokens.colors.aqua,
    shadowOffset: fiticianTokens.shadows.glow.offset,
    shadowOpacity: fiticianTokens.shadows.glow.opacity,
    shadowRadius: fiticianTokens.shadows.glow.radius,
  },
  progressLine: {
    backgroundColor: fiticianTokens.colors.lineStrong,
    height: 1,
    left: 24,
    position: "absolute",
    right: 24,
    top: 20,
  },
  progressStep: {
    alignItems: "center",
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flex: 1,
    gap: fiticianTokens.spacing[1],
    justifyContent: "flex-start",
    minHeight: 62,
    paddingHorizontal: fiticianTokens.spacing[1],
    paddingVertical: 3,
    zIndex: 1,
  },
  progressStepActive: {
    borderColor: fiticianTokens.colors.lineStrong,
  },
  progressStepCurrent: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.aqua,
    elevation: fiticianTokens.shadows.glow.elevation,
    shadowColor: fiticianTokens.colors.aqua,
    shadowOffset: fiticianTokens.shadows.glow.offset,
    shadowOpacity: fiticianTokens.shadows.glow.opacity,
    shadowRadius: fiticianTokens.shadows.glow.radius,
  },
  progressStepLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "center",
    writingDirection: "rtl",
  },
  progressStepLabelActive: {
    color: fiticianTokens.colors.aqua,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  progressSteps: {
    flexDirection: "row",
    minHeight: 64,
    position: "relative",
  },
  screen: {
    gap: fiticianTokens.spacing[3],
    paddingBottom: fiticianTokens.spacing[6],
  },
  singleColumn: {
    width: "100%",
  },
  subheading: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
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
  twoColumns: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
});
