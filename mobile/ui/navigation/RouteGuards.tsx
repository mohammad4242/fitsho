import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { Redirect } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";

import { useMobileAuth } from "../../auth/MobileAuthProvider";
import { mobileRouteSnapshotFromAuth } from "../../auth/authContext";
import { loadSpecialistAccess, type SpecialistAccessSnapshot } from "../../auth/specialistAccess";
import type { ProfileStatusResponse } from "@fitician/core/profile";
import { fiticianTokens } from "../tokens";
import {
  decideMobileRoute,
  defaultMobileRouteSnapshot,
  type MobileProductCapability,
  type MobileRouteKind,
  type MobileRouteSnapshot,
} from "./routePolicy";
import {
  mobileProfileStateFromStatus,
  type MobileProfileRouteState,
} from "./profileRouteState";

const MobileRouteSnapshotContext = createContext<MobileRouteSnapshot>(defaultMobileRouteSnapshot);
const MobileProfileRefreshContext = createContext<() => Promise<void>>(
  async () => undefined,
);

export interface MobileRouteStateProviderProps {
  readonly children: ReactNode;
  readonly snapshot?: MobileRouteSnapshot;
}

export function MobileRouteStateProvider({
  children,
  snapshot = defaultMobileRouteSnapshot,
}: MobileRouteStateProviderProps) {
  return (
    <MobileRouteSnapshotContext.Provider value={snapshot}>
      <MobileProfileRefreshContext.Provider value={async () => undefined}>
        {children}
      </MobileProfileRefreshContext.Provider>
    </MobileRouteSnapshotContext.Provider>
  );
}

export function MobileRouteStateProviderFromAuth({ children }: { readonly children: ReactNode }) {
  const auth = useMobileAuth();
  const [profile, setProfile] = useState<MobileProfileRouteState | null>(null);
  const [specialistAccess, setSpecialistAccess] = useState<SpecialistAccessSnapshot>({
    coach: "loading",
    physician: "loading",
  });
  const requestGeneration = useRef(0);
  const specialistRequestGeneration = useRef(0);
  const userId = auth.user?.id ?? null;
  const refreshProfileStatus = useCallback(async () => {
    const generation = ++requestGeneration.current;
    if (auth.status !== "signed_in" || userId === null) {
      setProfile(null);
      return;
    }
    setProfile(null);
    try {
      const status = await auth.request<ProfileStatusResponse>({
        method: "GET",
        path: "/api/v1/profile/status",
      });
      if (generation === requestGeneration.current) {
        setProfile(mobileProfileStateFromStatus(status));
      }
    } catch {
      if (generation === requestGeneration.current) {
        setProfile({
          completionState: "product_mode_not_selected",
          productMode: null,
          status: "resolved",
        });
      }
    }
  }, [auth.request, auth.status, userId]);

  const refreshSpecialistAccess = useCallback(async () => {
    const generation = ++specialistRequestGeneration.current;
    if (auth.status !== "signed_in" || userId === null) {
      setSpecialistAccess({ coach: "denied", physician: "denied" });
      return;
    }
    setSpecialistAccess({ coach: "loading", physician: "loading" });
    const access = await loadSpecialistAccess(auth.request);
    if (generation === specialistRequestGeneration.current) {
      setSpecialistAccess(access);
    }
  }, [auth.request, auth.status, userId]);

  useEffect(() => {
    void refreshProfileStatus();
  }, [refreshProfileStatus]);

  useEffect(() => {
    void refreshSpecialistAccess();
  }, [refreshSpecialistAccess]);

  const profileSnapshot = profile ?? {
    completionState: null,
    productMode: null,
    status: "loading" as const,
  };
  const snapshot = useMemo(
    () => ({
      ...mobileRouteSnapshotFromAuth(auth),
      profile: profileSnapshot,
      specialistAccess,
    }),
    [auth, profileSnapshot, specialistAccess],
  );
  return (
    <MobileRouteSnapshotContext.Provider value={snapshot}>
      <MobileProfileRefreshContext.Provider value={refreshProfileStatus}>
        {children}
      </MobileProfileRefreshContext.Provider>
    </MobileRouteSnapshotContext.Provider>
  );
}

export function useMobileRouteSnapshot(): MobileRouteSnapshot {
  return useContext(MobileRouteSnapshotContext);
}

export function useRefreshMobileProfileStatus(): () => Promise<void> {
  return useContext(MobileProfileRefreshContext);
}

export interface RouteGuardProps {
  readonly children: ReactNode;
  readonly kind: MobileRouteKind;
  readonly requiredCapability?: MobileProductCapability;
}

export function RouteGuard({ children, kind, requiredCapability }: RouteGuardProps) {
  const snapshot = useMobileRouteSnapshot();
  const decision = decideMobileRoute(kind, snapshot, requiredCapability);

  if (decision.status === "loading") {
    return <RouteGuardLoading />;
  }
  if (decision.status === "redirect") {
    return <Redirect href={decision.href} />;
  }
  return <>{children}</>;
}

function RouteGuardLoading() {
  return (
    <SafeAreaView edges={["top", "bottom"]} style={styles.loading}>
      <View accessibilityRole="progressbar">
        <ActivityIndicator accessibilityLabel="در حال بارگذاری" color={fiticianTokens.colors.aqua} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  loading: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.canvas,
    flex: 1,
    justifyContent: "center",
  },
});
