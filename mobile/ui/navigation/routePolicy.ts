import type { User } from "@fitician/core/auth";
import type { ProfileCompletionState, ProductMode } from "@fitician/core/profile";

export type MobileRouteKind = "public" | "auth" | "onboarding" | "member" | "coach" | "physician";
export type MobileProductCapability = "training" | "nutrition";
export type MobileSpecialistAccess = "loading" | "granted" | "denied";

export interface MobileRouteSnapshot {
  readonly profile: {
    readonly completionState: ProfileCompletionState | null;
    readonly productMode: ProductMode | null;
    readonly status: "loading" | "resolved";
  };
  readonly session: {
    readonly status: "loading" | "signed_in" | "signed_out";
    readonly user: User | null;
  };
  readonly specialistAccess: {
    readonly coach: MobileSpecialistAccess;
    readonly physician: MobileSpecialistAccess;
  };
}

export type MobileRouteDecision =
  | { readonly status: "allow" }
  | { readonly status: "loading" }
  | { readonly href: "/auth/sign-in" | "/member" | "/onboarding"; readonly status: "redirect" };

export const defaultMobileRouteSnapshot: MobileRouteSnapshot = {
  profile: {
    completionState: null,
    productMode: null,
    status: "loading",
  },
  session: {
    status: "signed_out",
    user: null,
  },
  specialistAccess: {
    coach: "loading",
    physician: "loading",
  },
};

const onboardingStates: ReadonlySet<ProfileCompletionState> = new Set([
  "product_mode_not_selected",
  "shared_profile_incomplete",
  "training_onboarding_incomplete",
  "medical_review_information_incomplete",
  "nutrition_onboarding_incomplete",
]);

function isSignedIn(snapshot: MobileRouteSnapshot): boolean {
  return snapshot.session.status === "signed_in" && snapshot.session.user !== null;
}

function hasIncompleteProfile(snapshot: MobileRouteSnapshot): boolean {
  return (
    snapshot.profile.completionState === null ||
    onboardingStates.has(snapshot.profile.completionState) ||
    snapshot.profile.productMode === null
  );
}

export function supportsProductCapability(
  productMode: ProductMode | null,
  capability: MobileProductCapability,
): boolean {
  return productMode === "both" || productMode === capability;
}

function resolveSignedInLanding(snapshot: MobileRouteSnapshot): MobileRouteDecision {
  if (snapshot.profile.status === "loading") {
    return { status: "loading" };
  }
  return hasIncompleteProfile(snapshot)
    ? { href: "/onboarding", status: "redirect" }
    : { href: "/member", status: "redirect" };
}

export function decideMobileRoute(
  kind: MobileRouteKind,
  snapshot: MobileRouteSnapshot,
  requiredCapability?: MobileProductCapability,
): MobileRouteDecision {
  if (snapshot.session.status === "loading") {
    return { status: "loading" };
  }

  if (kind === "public" || kind === "auth") {
    return isSignedIn(snapshot) ? resolveSignedInLanding(snapshot) : { status: "allow" };
  }

  if (!isSignedIn(snapshot)) {
    return { href: "/auth/sign-in", status: "redirect" };
  }

  if (kind === "coach" || kind === "physician") {
    const access = snapshot.specialistAccess[kind];
    return access === "loading"
      ? { status: "loading" }
      : access === "granted"
        ? { status: "allow" }
        : { href: "/member", status: "redirect" };
  }

  if (snapshot.profile.status === "loading") {
    return { status: "loading" };
  }

  if (kind === "onboarding") {
    return hasIncompleteProfile(snapshot)
      ? { status: "allow" }
      : { href: "/member", status: "redirect" };
  }

  if (hasIncompleteProfile(snapshot)) {
    return { href: "/onboarding", status: "redirect" };
  }

  return requiredCapability === undefined ||
    supportsProductCapability(snapshot.profile.productMode, requiredCapability)
    ? { status: "allow" }
    : { href: "/member", status: "redirect" };
}
