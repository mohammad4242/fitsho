import type { User } from "@fitician/core/auth";
import type { ProfileCompletionState, ProductMode } from "@fitician/core/profile";

export type MobileRouteKind = "public" | "auth" | "onboarding" | "account" | "member" | "coach" | "physician";
export type MobileProductCapability = "training" | "nutrition";
export type MobileSpecialistAccess = "loading" | "granted" | "denied" | "error";
export type MobileRouteErrorResource = "profile" | "coach" | "physician";

export interface MobileRouteSnapshot {
  readonly profile: {
    readonly completionState: ProfileCompletionState | null;
    readonly productMode: ProductMode | null;
    readonly status: "loading" | "resolved" | "error";
  };
  readonly session: {
    readonly sessionExpired?: boolean;
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
  | {
      readonly href: "/auth/sign-in" | "/auth/sign-in?reason=session-expired" | "/member" | "/onboarding";
      readonly status: "redirect";
    }
  | { readonly resource: MobileRouteErrorResource; readonly status: "error" };

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

function signInHref(snapshot: MobileRouteSnapshot): "/auth/sign-in" | "/auth/sign-in?reason=session-expired" {
  return snapshot.session.sessionExpired ? "/auth/sign-in?reason=session-expired" : "/auth/sign-in";
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
  if (snapshot.profile.status === "error") {
    return { resource: "profile", status: "error" };
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
    return { href: signInHref(snapshot), status: "redirect" };
  }

  if (kind === "account") {
    return { status: "allow" };
  }

  if (kind === "coach" || kind === "physician") {
    const access = snapshot.specialistAccess[kind];
    if (access === "loading") return { status: "loading" };
    if (access === "error") return { resource: kind, status: "error" };
    return access === "granted"
      ? { status: "allow" }
      : { href: "/member", status: "redirect" };
  }

  if (snapshot.profile.status === "loading") {
    return { status: "loading" };
  }
  if (snapshot.profile.status === "error") {
    return { resource: "profile", status: "error" };
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
