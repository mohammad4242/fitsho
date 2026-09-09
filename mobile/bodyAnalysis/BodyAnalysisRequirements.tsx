import { useEffect, useMemo, useState } from "react";
import { StyleSheet, Switch, Text, View } from "react-native";

import type {
  MeasurementField,
  MeasurementFormValues,
} from "@fitician/core/profile";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { Button, Card, Notice, ScreenHeader, Skeleton, TextField } from "../ui/components";
import { Screen } from "../ui/layout";
import { fiticianTokens } from "../ui/tokens";
import { createProfileApi } from "../profile/profileApi";
import { normalizeOnboardingDigits } from "../onboarding/onboardingModel";
import {
  type BodyAnalysisProfile,
  measurementErrorMessage,
  measurementPatch,
  measurementValuesFromProfile,
  validateBodyAnalysisMeasurements,
} from "./bodyAnalysisRequirementsModel";

export interface BodyAnalysisRequirementsProps {
  readonly onCancel: () => void;
  readonly onConfirmed: () => void;
}


export function BodyAnalysisRequirements({
  onCancel,
  onConfirmed,
}: BodyAnalysisRequirementsProps) {
  const auth = useMobileAuth();
  const api = useMemo(() => createProfileApi(auth.request), [auth.request]);
  const [profile, setProfile] = useState<BodyAnalysisProfile | null>(null);
  const [values, setValues] = useState<MeasurementFormValues | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState(false);

  useEffect(() => {
    let active = true;
    void api.getProfile()
      .then((loaded) => {
        if (!active) return;
        if (loaded === null) {
          setError("اطلاعات پروفایل پیدا نشد.");
          return;
        }
        setProfile(loaded);
        setValues(measurementValuesFromProfile(loaded));
      })
      .catch(() => {
        if (active) setError("خواندن اندازه‌ها انجام نشد. دوباره تلاش کن.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api]);

  const errors = useMemo(
    () => values === null ? {} : validateBodyAnalysisMeasurements(values),
    [values],
  );
  const canContinue = profile !== null
    && values !== null
    && Object.keys(errors).length === 0
    && confirmed
    && !busy;

  function changeMeasurement(field: MeasurementField, value: string) {
    setValues((current) => current === null
      ? current
      : { ...current, [field]: normalizeOnboardingDigits(value) });
    setConfirmed(false);
    setSaveError(false);
  }

  async function confirmMeasurements() {
    if (!canContinue || profile === null || values === null) return;
    setBusy(true);
    setSaveError(false);
    try {
      const patch = measurementPatch(values, profile);
      if (Object.keys(patch).length > 0) await api.updateProfile(patch);
      onConfirmed();
    } catch {
      setSaveError(true);
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <Screen scroll={false}>
        <View style={styles.loading}>
          <Skeleton accessibilityLabel="در حال خواندن اندازه‌ها" height={28} width="70%" />
          <Skeleton accessibilityLabel="در حال خواندن اندازه‌ها" height={160} />
        </View>
      </Screen>
    );
  }

  if (error !== null || values === null) {
    return (
      <Screen scroll={false}>
        <View style={styles.errorState}>
          <Text style={styles.eyebrow}>تحلیل بدن</Text>
          <Text style={styles.title}>اندازه‌ها آماده نیستند</Text>
          <Notice message={error ?? "اطلاعات اندازه‌ها در دسترس نیست."} variant="danger" />
          <Button label="بازگشت" onPress={onCancel} variant="secondary" />
        </View>
      </Screen>
    );
  }

  return (
    <Screen contentContainerStyle={styles.screen}>
      <View style={styles.container}>
        <ScreenHeader
          compact
          eyebrow="مرحله اول · اندازه‌گیری"
          subtitle="برای تفسیر بهتر عکس‌ها، این اندازه‌ها باید مربوط به همین روز باشند."
          title="اندازه‌ها را تأیید کن"
        />

        <Card style={styles.panel}>
          <Text style={styles.sectionTitle}>اندازه‌های اصلی</Text>
          <TextField
            accessibilityLabel="قد به سانتی‌متر"
            error={measurementErrorMessage(errors.height_cm)}
            keyboardType="number-pad"
            label="قد"
            onChangeText={(value) => changeMeasurement("height_cm", value)}
            required
            value={values.height_cm}
          />
          <TextField
            accessibilityLabel="وزن فعلی به کیلوگرم"
            error={measurementErrorMessage(errors.current_weight_kg)}
            keyboardType="decimal-pad"
            label="وزن فعلی"
            onChangeText={(value) => changeMeasurement("current_weight_kg", value)}
            required
            value={values.current_weight_kg}
          />
        </Card>

        <Card style={styles.panel}>
          <Text style={styles.sectionTitle}>نسبت‌های بدنی</Text>
          <Text style={styles.body}>هر سه اندازه برای این تحلیل لازم‌اند.</Text>
          <TextField
            accessibilityLabel="دور شانه به سانتی‌متر"
            error={measurementErrorMessage(errors.shoulder_circumference_cm)}
            keyboardType="decimal-pad"
            label="دور شانه"
            onChangeText={(value) => changeMeasurement("shoulder_circumference_cm", value)}
            required
            value={values.shoulder_circumference_cm}
          />
          <TextField
            accessibilityLabel="دور کمر به سانتی‌متر"
            error={measurementErrorMessage(errors.waist_circumference_cm)}
            keyboardType="decimal-pad"
            label="دور کمر"
            onChangeText={(value) => changeMeasurement("waist_circumference_cm", value)}
            required
            value={values.waist_circumference_cm}
          />
          <TextField
            accessibilityLabel="دور باسن به سانتی‌متر"
            error={measurementErrorMessage(errors.hip_circumference_cm)}
            keyboardType="decimal-pad"
            label="دور باسن"
            onChangeText={(value) => changeMeasurement("hip_circumference_cm", value)}
            required
            value={values.hip_circumference_cm}
          />
        </Card>

        <Card style={styles.confirmation} variant={confirmed ? "interactive" : "default"}>
          <Switch
            accessibilityLabel="اندازه‌ها مربوط به امروز هستند"
            onValueChange={setConfirmed}
            thumbColor={confirmed ? fiticianTokens.colors.aqua : fiticianTokens.colors.muted}
            trackColor={{ false: fiticianTokens.colors.lineStrong, true: fiticianTokens.colors.teal }}
            value={confirmed}
          />
          <Text style={styles.confirmationText}>اندازه‌ها مربوط به امروز هستند.</Text>
        </Card>

        {saveError ? <Notice message="ذخیره اندازه‌ها انجام نشد. دوباره تلاش کن." variant="danger" /> : null}
        <View style={styles.actions}>
          <Button disabled={busy} label="بازگشت" onPress={onCancel} variant="secondary" />
          <Button
            disabled={!canContinue}
            label={busy ? "در حال ذخیره…" : "ادامه به ثبت عکس‌ها"}
            loading={busy}
            onPress={() => void confirmMeasurements()}
          />
        </View>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  actions: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    marginTop: fiticianTokens.spacing[2],
  },
  body: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "right",
    writingDirection: "rtl",
  },
  confirmation: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    marginTop: fiticianTokens.spacing[2],
  },
  confirmationText: {
    color: fiticianTokens.colors.ink,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 24,
    textAlign: "right",
    writingDirection: "rtl",
  },
  container: {
    gap: fiticianTokens.spacing[3],
    paddingBottom: fiticianTokens.spacing[6],
  },
  errorState: {
    gap: fiticianTokens.spacing[4],
    justifyContent: "center",
    minHeight: 420,
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  loading: {
    gap: fiticianTokens.spacing[4],
    justifyContent: "center",
    minHeight: 420,
  },
  panel: {
    gap: fiticianTokens.spacing[3],
  },
  sectionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  screen: {
    paddingBottom: fiticianTokens.spacing[7],
    paddingTop: fiticianTokens.spacing[3],
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 42,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
