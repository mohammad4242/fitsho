type ResourceQueryKeys<TFeature extends string> = {
  readonly all: readonly [TFeature];
  lists(): readonly [TFeature, "list"];
  list<TFilter>(filters: TFilter): readonly [TFeature, "list", TFilter];
  details(): readonly [TFeature, "detail"];
  detail<TId extends string | number>(id: TId): readonly [TFeature, "detail", TId];
};

function createResourceQueryKeys<const TFeature extends string>(
  feature: TFeature,
): ResourceQueryKeys<TFeature> {
  const all = [feature] as const;
  const lists = () => [...all, "list"] as const;
  const details = () => [...all, "detail"] as const;

  return {
    all,
    lists,
    list: <TFilter>(filters: TFilter) => [...lists(), filters] as const,
    details,
    detail: <TId extends string | number>(id: TId) => [...details(), id] as const,
  };
}

export const authKeys = {
  all: ["auth"] as const,
  session: () => ["auth", "session"] as const,
};

export const profileKeys = {
  ...createResourceQueryKeys("profile"),
  current: () => ["profile", "current"] as const,
  status: () => ["profile", "status"] as const,
  measurements: () => ["profile", "measurements"] as const,
};

export const exerciseKeys = createResourceQueryKeys("exercises");

export const workoutKeys = {
  ...createResourceQueryKeys("workouts"),
  plans: () => ["workouts", "plans"] as const,
  plan: (planId: string) => ["workouts", "plan", planId] as const,
  currentCycle: () => ["workouts", "current-cycle"] as const,
  cycle: (cycleId: string) => ["workouts", "cycle", cycleId] as const,
};

export const nutritionKeys = {
  ...createResourceQueryKeys("nutrition"),
  plans: () => ["nutrition", "plans"] as const,
  plan: (planId: string) => ["nutrition", "plan", planId] as const,
  profile: () => ["nutrition", "profile"] as const,
  estimate: () => ["nutrition", "estimate"] as const,
  tracking: (date: string) => ["nutrition", "tracking", date] as const,
};

export const bodyAnalysisKeys = {
  ...createResourceQueryKeys("body-analysis"),
  sessions: () => ["body-analysis", "sessions"] as const,
  session: (sessionId: string) => ["body-analysis", "detail", sessionId] as const,
  comparison: (comparisonId: string) => ["body-analysis", "comparison", comparisonId] as const,
};

export const coachKeys = createResourceQueryKeys("coach");
export const physicianKeys = createResourceQueryKeys("physician");

export const featureQueryKeys = {
  auth: authKeys,
  profile: profileKeys,
  exercises: exerciseKeys,
  workouts: workoutKeys,
  nutrition: nutritionKeys,
  bodyAnalysis: bodyAnalysisKeys,
  coach: coachKeys,
  physician: physicianKeys,
} as const;
