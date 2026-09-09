import { useEffect, useMemo, useState } from "react";
import { StyleSheet, Switch, Text, View } from "react-native";

import type {
  MeasurementField,
  MeasurementFormValues,
} from "@fitician/core/profile";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { Button, Card, Notice, PageHeading, Skeleton, TextField } from "../ui/components";
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
        <PageHeading
          compact
          eyebrow="پیش از جلسه عکس"
          supportingText="اندازه‌هایی را وارد کن که با وضعیت بدنت امروز مطابقت دارند. این مقادیر همراه همین جلسه عکس ذخیره می‌شوند."
          title="اندازه‌های فعلی‌ات را تأیید کن"
        />

        <MeasurementStatus confirmed={confirmed} />

        <Card style={styles.panel}>
          <View style={styles.panelHeading}>
            <Text style={styles.stepBadge}>۰۱</Text>
            <View style={styles.panelHeadingCopy}>
              <Text style={styles.sectionTitle}>اندازه‌های پایه</Text>
              <Text style={styles.body}>قد و وزن، نقطهٔ شروع این اسکن هستند.</Text>
            </View>
          </View>
          <TextField
            accessibilityLabel="قد به سانتی‌متر"
            error={measurementErrorMessage(errors.height_cm)}
            keyboardType="number-pad"
            label="قد (سانتی‌متر)"
            onChangeText={(value) => changeMeasurement("height_cm", value)}
            required
            value={values.height_cm}
          />
          <TextField
            accessibilityLabel="وزن فعلی به کیلوگرم"
            error={measurementErrorMessage(errors.current_weight_kg)}
            keyboardType="decimal-pad"
            label="وزن فعلی (کیلوگرم)"
            onChangeText={(value) => changeMeasurement("current_weight_kg", value)}
            required
            value={values.current_weight_kg}
          />
        </Card>

        <Card style={styles.panel}>
          <View style={styles.panelHeading}>
            <Text style={styles.stepBadge}>۰۲</Text>
            <View style={styles.panelHeadingCopy}>
              <Text style={styles.sectionTitle}>تناسبات بدن</Text>
              <Text style={styles.body}>متر را بدون کشیدن، در پهن‌ترین بخش هر ناحیه قرار بده.</Text>
            </View>
          </View>
          <TextField
            accessibilityLabel="دور شانه به سانتی‌متر"
            error={measurementErrorMessage(errors.shoulder_circumference_cm)}
            keyboardType="decimal-pad"
            label="دور شانه (سانتی‌متر)"
            onChangeText={(value) => changeMeasurement("shoulder_circumference_cm", value)}
            required
            value={values.shoulder_circumference_cm}
          />
          <TextField
            accessibilityLabel="دور کمر به سانتی‌متر"
            error={measurementErrorMessage(errors.waist_circumference_cm)}
            keyboardType="decimal-pad"
            label="دور کمر (سانتی‌متر)"
            onChangeText={(value) => changeMeasurement("waist_circumference_cm", value)}
            required
            value={values.waist_circumference_cm}
          />
          <TextField
            accessibilityLabel="دور باسن به سانتی‌متر"
            error={measurementErrorMessage(errors.hip_circumference_cm)}
            keyboardType="decimal-pad"
            label="دور باسن (سانتی‌متر)"
            onChangeText={(value) => changeMeasurement("hip_circumference_cm", value)}
            required
            value={values.hip_circumference_cm}
          />
        </Card>

        <Notice
          message="متر را بدون کشیدن بیش از حد دور بدن قرار بده. تحلیل تا وقتی تأیید نکنی این مقادیر فعلی هستند شروع نمی‌شود."
          variant="warning"
        />

        <Card style={styles.confirmation} variant={confirmed ? "interactive" : "default"}>
          <Switch
            accessibilityLabel="اندازه‌ها مربوط به امروز هستند"
            onValueChange={setConfirmed}
            thumbColor={confirmed ? fiticianTokens.colors.aqua : fiticianTokens.colors.muted}
            trackColor={{ false: fiticianTokens.colors.lineStrong, true: fiticianTokens.colors.teal }}
            value={confirmed}
          />
          <Text style={styles.confirmationText}>تأیید می‌کنم این اندازه‌ها برای همین جلسه عکس فعلی هستند.</Text>
        </Card>

        {saveError ? <Notice message="ذخیره اندازه‌ها انجام نشد. دوباره تلاش کن." variant="danger" /> : null}
        <View style={styles.actions}>
          <Button disabled={busy} label="بازگشت" onPress={onCancel} variant="secondary" />
          <Button
            disabled={!canContinue}
            label={busy ? "در حال ذخیره…" : "ذخیره و ادامه"}
            loading={busy}
            onPress={() => void confirmMeasurements()}
          />
        </View>
      </View>
    </Screen>
  );
}

function MeasurementStatus({ confirmed }: { readonly confirmed: boolean }) {
  return (
    <Card
      accessibilityLiveRegion="polite"
      style={[styles.statusCard, confirmed && styles.statusCardConfirmed]}
    >
      <View style={[styles.statusMark, confirmed && styles.statusMarkConfirmed]}>
        <Text style={[styles.statusMarkText, confirmed && styles.statusMarkTextConfirmed]}>
          {confirmed ? "✓" : "۰۱"}
        </Text>
      </View>
      <View style={styles.statusCopy}>
        <Text style={styles.statusTitle}>{confirmed ? "آمادهٔ ادامه" : "در انتظار تأیید"}</Text>
        <Text style={styles.statusHint}>
          {confirmed ? "این مقادیر همراه همین اسکن ذخیره می‌شوند." : "مقادیر امروزت را بررسی کن."}
        </Text>
      </View>
    </Card>
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
  panelHeading: {
    alignItems: "flex-start",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
  },
  panelHeadingCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
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
  statusCard: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
  },
  statusCardConfirmed: {
    backgroundColor: fiticianTokens.colors.successSurface,
    borderColor: fiticianTokens.colors.success,
  },
  statusCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  statusHint: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  statusMark: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 38,
    justifyContent: "center",
    width: 38,
  },
  statusMarkConfirmed: {
    backgroundColor: fiticianTokens.colors.successSurface,
    borderColor: fiticianTokens.colors.success,
  },
  statusMarkText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  statusMarkTextConfirmed: {
    color: fiticianTokens.colors.success,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.lg,
  },
  statusTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  stepBadge: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    minHeight: 32,
    minWidth: 32,
    padding: fiticianTokens.spacing[2],
    textAlign: "center",
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
