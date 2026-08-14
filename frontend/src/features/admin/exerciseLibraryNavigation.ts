import {
  bodyRegions,
  muscleFocuses,
  muscleFocusesByMuscle,
  muscleGroups,
  type BodyRegion,
  type MuscleFocus,
  type MuscleGroup,
} from "../exercises/types";
import { musclesByRegion } from "./validation";

export function readExerciseCreateContext(searchParams: URLSearchParams): {
  body_region?: BodyRegion;
  primary_muscle?: MuscleGroup;
  muscle_focus?: MuscleFocus;
} {
  const bodyRegion = readValue(searchParams.get("body_region"), bodyRegions);
  const primaryMuscle = readValue(searchParams.get("primary_muscle"), muscleGroups);
  const muscleFocus = readValue(searchParams.get("muscle_focus"), muscleFocuses);
  if (
    bodyRegion === undefined
    || primaryMuscle === undefined
    || !musclesByRegion[bodyRegion].includes(primaryMuscle)
  ) {
    return {};
  }
  return {
    body_region: bodyRegion,
    primary_muscle: primaryMuscle,
    ...(muscleFocus !== undefined && muscleFocusesByMuscle[primaryMuscle].includes(muscleFocus)
      ? { muscle_focus: muscleFocus }
      : {}),
  };
}

export function readExerciseLibraryReturn(searchParams: URLSearchParams): string {
  const candidate = searchParams.get("return_to");
  return candidate !== null && (candidate === "/exercises" || candidate.startsWith("/exercises?"))
    ? candidate
    : "/exercises";
}

export function exerciseLibraryReturnPath(
  returnTo: string,
  bodyRegion: BodyRegion | null | undefined,
  primaryMuscle: MuscleGroup | null | undefined,
  muscleFocus: MuscleFocus | null | undefined,
  isActive: boolean | undefined,
  needsReview: boolean | undefined,
): string {
  const safeReturn = returnTo === "/exercises" || returnTo.startsWith("/exercises?")
    ? returnTo
    : "/exercises";
  const query = new URLSearchParams(safeReturn.split("?", 2)[1] ?? "");
  for (const key of ["body_region", "primary_muscle", "muscle_focus", "equipment", "difficulty", "exercise_type", "labels", "search", "page", "admin_status"]) {
    query.delete(key);
  }
  if (bodyRegion != null && primaryMuscle != null) {
    query.set("body_region", bodyRegion);
    query.set("primary_muscle", primaryMuscle);
    if (muscleFocus != null && muscleFocusesByMuscle[primaryMuscle].includes(muscleFocus)) {
      query.set("muscle_focus", muscleFocus);
    }
  }
  if (needsReview) query.set("admin_status", "needs_review");
  else if (isActive === false) query.set("admin_status", "inactive");
  const serialized = query.toString();
  return `/exercises${serialized ? `?${serialized}` : ""}`;
}

function readValue<T extends string>(value: string | null, choices: readonly T[]): T | undefined {
  return choices.includes(value as T) ? value as T : undefined;
}
