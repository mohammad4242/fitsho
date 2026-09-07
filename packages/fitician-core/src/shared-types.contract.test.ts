import {
  availableEquipment,
  fitnessGoals,
  productModes,
  sessionDurations,
} from "./profile.js";
import type { ProfileFormValues } from "./profile.js";
import { bodyRegions, muscleGroups } from "./exercises.js";
import type { ExerciseSummary } from "./exercises.js";
import type { User } from "./auth.js";
import type { WorkoutPlan } from "./workouts.js";
import type { WeeklyPlan } from "./nutrition.js";
import type { BodyPhotoSession } from "./body-photos.js";
import type { WorkoutReviewQueueItem } from "./workout-reviews.js";

const form: ProfileFormValues = {
  display_name: "Member",
  birth_date: "1990-01-01",
  sex: "prefer_not_to_say",
  height_cm: "180",
  current_weight_kg: "80",
  shoulder_circumference_cm: "",
  waist_circumference_cm: "",
  hip_circumference_cm: "",
  fitness_goal: "build_muscle",
  experience_level: "beginner",
  training_age_months: "",
  training_days_per_week: "3",
  preferred_weekdays: [0, 2, 4],
  priority_muscle: "chest",
  training_location: "home",
  home_training_setup: "bodyweight_only",
  available_equipment: ["bodyweight"],
  session_duration_minutes: "45",
  training_intensity: "moderate",
  training_cautions: [],
  plan_duration_weeks: "4",
};

const user: User = {
  id: "user-1",
  email: null,
  phone_number: null,
  created_at: "2026-01-01T00:00:00Z",
  is_admin: false,
};

const exercise: ExerciseSummary = {
  id: "exercise-1",
  slug: "push-up",
  name_en: "Push-up",
  name_fa: "شنا",
  content_type: "exercise",
  body_region: "upper_body",
  primary_muscle: "chest",
  muscle_focus: "general_chest",
  labels: [],
  secondary_muscles: [],
  equipment: ["bodyweight"],
  difficulty: "beginner",
  media_path: "/media/push-up.mp4",
  media_type: "video",
};

declare const workoutPlan: WorkoutPlan;
declare const weeklyPlan: WeeklyPlan;
declare const bodyPhotoSession: BodyPhotoSession;
declare const reviewItem: WorkoutReviewQueueItem;

void [
  availableEquipment,
  fitnessGoals,
  productModes,
  sessionDurations,
  bodyRegions,
  muscleGroups,
  form,
  user,
  exercise,
  workoutPlan,
  weeklyPlan,
  bodyPhotoSession,
  reviewItem,
];
