import { validateBodyAnalysisMeasurements } from "@fitician/core/profile-validation";
import type {
  MeasurementFormValues,
  MeasurementField,
  Profile,
  ProfilePatch,
} from "@fitician/core/profile";

const circumferenceFields = [
  "shoulder_circumference_cm",
  "waist_circumference_cm",
  "hip_circumference_cm",
] as const satisfies readonly MeasurementField[];

export type BodyAnalysisProfile = Pick<
  Profile,
  | "current_weight_kg"
  | "height_cm"
  | "hip_circumference_cm"
  | "shoulder_circumference_cm"
  | "waist_circumference_cm"
>;

export { validateBodyAnalysisMeasurements };

export function measurementValuesFromProfile(
  profile: BodyAnalysisProfile,
): MeasurementFormValues {
  return {
    current_weight_kg: String(profile.current_weight_kg),
    height_cm: String(profile.height_cm),
    hip_circumference_cm: profile.hip_circumference_cm === null
      ? ""
      : String(profile.hip_circumference_cm),
    shoulder_circumference_cm: profile.shoulder_circumference_cm === null
      ? ""
      : String(profile.shoulder_circumference_cm),
    waist_circumference_cm: profile.waist_circumference_cm === null
      ? ""
      : String(profile.waist_circumference_cm),
  };
}

export function measurementPatch(
  values: MeasurementFormValues,
  profile: BodyAnalysisProfile,
): ProfilePatch {
  const patch: ProfilePatch = {};
  const height = Number(values.height_cm.trim());
  const weight = Number(values.current_weight_kg.trim());
  if (height !== profile.height_cm) patch.height_cm = height;
  if (weight !== profile.current_weight_kg) patch.current_weight_kg = weight;

  for (const field of circumferenceFields) {
    const value = Number(values[field].trim());
    if (value !== profile[field]) patch[field] = value;
  }
  return patch;
}

export function measurementErrorMessage(code: string | undefined): string | undefined {
  if (code === undefined) return undefined;
  const messages: Record<string, string> = {
    circumferencePrecision: "حداکثر دو رقم اعشار وارد کن.",
    circumferenceRange: "اندازه باید بین ۴۰ تا ۲۵۰ سانتی‌متر باشد.",
    heightRange: "قد باید بین ۱۲۰ تا ۲۳۰ سانتی‌متر باشد.",
    required: "این اندازه لازم است.",
    weightPrecision: "وزن را با حداکثر دو رقم اعشار وارد کن.",
    weightRange: "وزن باید بین ۳۵ تا ۳۰۰ کیلوگرم باشد.",
  };
  return messages[code] ?? "این اندازه را بررسی کن.";
}
