import {
  profileToFormValues,
  toProfileInput,
  toProfilePatch,
  validateAll,
  validateBodyAnalysisMeasurements,
  validateStep,
} from "./profile-validation.js";
import type { Profile, ProfileFormValues } from "./profile.js";

declare const values: ProfileFormValues;
declare const profile: Profile;
declare const today: Date;

void validateStep(values, 1, today);
void validateAll(values, today);
void validateBodyAnalysisMeasurements(values);
void toProfileInput(values);
void profileToFormValues(profile);
void toProfilePatch(values, profile);
