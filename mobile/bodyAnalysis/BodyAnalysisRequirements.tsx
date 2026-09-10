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
import { bodyPhotoCopy, onboardingCopy } from "./bodyAnalysisCopy";
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
          setError(bodyPhotoCopy.measurements.loadError);
          return;
        }
        setProfile(loaded);
        setValues(measurementValuesFromProfile(loaded));
      })
      .catch(() => {
        if (active) setError(bodyPhotoCopy.measurements.loadError);
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
          <Text style={styles.eyebrow}>{bodyPhotoCopy.measurements.eyebrow}</Text>
          <Text style={styles.title}>{bodyPhotoCopy.measurements.title}</Text>
          <Notice message={error ?? bodyPhotoCopy.measurements.loadError} variant="danger" />
          <Button label={bodyPhotoCopy.measurements.back} onPress={onCancel} variant="secondary" />
        </View>
      </Screen>
    );
  }

  return (
    <Screen contentContainerStyle={styles.screen}>
      <View style={styles.container}>
        <PageHeading
          compact
          eyebrow={bodyPhotoCopy.measurements.eyebrow}
          supportingText={bodyPhotoCopy.measurements.body}
          title={bodyPhotoCopy.measurements.title}
        />

        <MeasurementStatus confirmed={confirmed} />

        <Card style={styles.measurementPanel}>
          <Text style={styles.fieldsLegend}>{bodyPhotoCopy.measurements.fieldsLegend}</Text>
          <View style={styles.measurementRail} />
          <View style={styles.measurementGroup}>
            <View style={styles.panelHeading}>
              <View style={styles.panelHeadingCopy}>
                <Text style={styles.sectionTitle}>{bodyPhotoCopy.measurements.essentialTitle}</Text>
                <Text style={styles.body}>{bodyPhotoCopy.measurements.essentialBody}</Text>
              </View>
              <Text style={styles.stepBadge}>۰۱</Text>
            </View>
            <View style={styles.measurementRow}>
              <View style={styles.measurementField}>
                <TextField
                  accessibilityLabel={onboardingCopy.fields.height}
                  error={measurementErrorMessage(errors.height_cm)}
                  keyboardType="number-pad"
                  label={onboardingCopy.fields.height}
                  onChangeText={(value) => changeMeasurement("height_cm", value)}
                  required
                  value={values.height_cm}
                />
              </View>
              <View style={styles.measurementField}>
                <TextField
                  accessibilityLabel={onboardingCopy.fields.weight}
                  error={measurementErrorMessage(errors.current_weight_kg)}
                  keyboardType="decimal-pad"
                  label={onboardingCopy.fields.weight}
                  onChangeText={(value) => changeMeasurement("current_weight_kg", value)}
                  required
                  value={values.current_weight_kg}
                />
              </View>
            </View>
          </View>

          <View style={styles.measurementGroup}>
            <View style={styles.panelHeading}>
              <View style={styles.panelHeadingCopy}>
                <Text style={styles.sectionTitle}>{bodyPhotoCopy.measurements.proportionsTitle}</Text>
                <Text style={styles.body}>{bodyPhotoCopy.measurements.proportionsBody}</Text>
              </View>
              <Text style={styles.stepBadge}>۰۲</Text>
            </View>
            <View style={styles.measurementRow}>
              <View style={styles.measurementField}>
                <TextField
                  accessibilityLabel={bodyPhotoCopy.measurements.fields.shoulderCircumference}
                  error={measurementErrorMessage(errors.shoulder_circumference_cm)}
                  keyboardType="decimal-pad"
                  label={bodyPhotoCopy.measurements.fields.shoulderCircumference}
                  onChangeText={(value) => changeMeasurement("shoulder_circumference_cm", value)}
                  required
                  value={values.shoulder_circumference_cm}
                />
              </View>
              <View style={styles.measurementField}>
                <TextField
                  accessibilityLabel={bodyPhotoCopy.measurements.fields.waistCircumference}
                  error={measurementErrorMessage(errors.waist_circumference_cm)}
                  keyboardType="decimal-pad"
                  label={bodyPhotoCopy.measurements.fields.waistCircumference}
                  onChangeText={(value) => changeMeasurement("waist_circumference_cm", value)}
                  required
                  value={values.waist_circumference_cm}
                />
              </View>
              <View style={styles.measurementField}>
                <TextField
                  accessibilityLabel={bodyPhotoCopy.measurements.fields.hipCircumference}
                  error={measurementErrorMessage(errors.hip_circumference_cm)}
                  keyboardType="decimal-pad"
                  label={bodyPhotoCopy.measurements.fields.hipCircumference}
                  onChangeText={(value) => changeMeasurement("hip_circumference_cm", value)}
                  required
                  value={values.hip_circumference_cm}
                />
              </View>
            </View>
          </View>
        </Card>

        <Notice
          message={bodyPhotoCopy.measurements.snapshotNote}
          variant="warning"
        />

        <Card style={styles.confirmation} variant={confirmed ? "interactive" : "default"}>
          <Text style={styles.confirmationText}>{bodyPhotoCopy.measurements.confirmLabel}</Text>
          <Switch
            accessibilityLabel={bodyPhotoCopy.measurements.confirmLabel}
            onValueChange={setConfirmed}
            thumbColor={confirmed ? fiticianTokens.colors.aqua : fiticianTokens.colors.muted}
            trackColor={{ false: fiticianTokens.colors.lineStrong, true: fiticianTokens.colors.teal }}
            value={confirmed}
          />
        </Card>

        {saveError ? <Notice message={bodyPhotoCopy.measurements.saveError} variant="danger" /> : null}
        <View style={styles.actions}>
          <Button disabled={busy} label={bodyPhotoCopy.measurements.back} onPress={onCancel} variant="secondary" />
          <Button
            disabled={!canContinue}
            label={busy ? bodyPhotoCopy.measurements.saving : bodyPhotoCopy.measurements.continue}
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
        <Text style={styles.statusTitle}>
          {confirmed ? bodyPhotoCopy.measurements.status.confirmed : bodyPhotoCopy.measurements.status.pending}
        </Text>
        <Text style={styles.statusHint}>
          {confirmed
            ? bodyPhotoCopy.measurements.status.confirmedHint
            : bodyPhotoCopy.measurements.status.pendingHint}
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
    flexDirection: "row",
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
  fieldsLegend: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    letterSpacing: 0.7,
    textAlign: "right",
    writingDirection: "rtl",
  },
  measurementField: {
    flex: 1,
    minWidth: 0,
  },
  measurementGroup: {
    gap: fiticianTokens.spacing[3],
    paddingStart: fiticianTokens.spacing[3],
  },
  measurementPanel: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.lineStrong,
    gap: fiticianTokens.spacing[4],
    overflow: "hidden",
    padding: fiticianTokens.spacing[3],
    position: "relative",
  },
  measurementRail: {
    backgroundColor: fiticianTokens.colors.aqua,
    bottom: fiticianTokens.spacing[4],
    left: fiticianTokens.spacing[3],
    opacity: 0.55,
    position: "absolute",
    top: fiticianTokens.spacing[5],
    width: 1,
  },
  measurementRow: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  panel: {
    gap: fiticianTokens.spacing[3],
  },
  panelHeading: {
    alignItems: "flex-start",
    flexDirection: "row",
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
    flexDirection: "row",
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
    textAlign: "center",
    writingDirection: "ltr",
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
    writingDirection: "ltr",
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
