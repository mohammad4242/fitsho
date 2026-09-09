export const PUBLIC_ONBOARDING_SOURCE = "public-onboarding" as const;

export type AuthOnboardingSource = typeof PUBLIC_ONBOARDING_SOURCE;

export function onboardingRoute(source?: string): "/onboarding" | {
  readonly params: { readonly source: AuthOnboardingSource };
  readonly pathname: "/onboarding";
} {
  return source === PUBLIC_ONBOARDING_SOURCE
    ? { params: { source: PUBLIC_ONBOARDING_SOURCE }, pathname: "/onboarding" }
    : "/onboarding";
}

export function publicOnboardingParams(source?: string): { readonly source: AuthOnboardingSource } | undefined {
  return source === PUBLIC_ONBOARDING_SOURCE
    ? { source: PUBLIC_ONBOARDING_SOURCE }
    : undefined;
}
