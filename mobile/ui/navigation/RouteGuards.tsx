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
import { Notice } from "../components";
import { RTL_LAYOUT } from "../rtl";
import { fiticianTokens } from "../tokens";
import {
  decideMobileRoute,
  defaultMobileRouteSnapshot,
  type MobileProductCapability,
  type MobileRouteErrorResource,
  type MobileRouteKind,
  type MobileRouteSnapshot,
} from "./routePolicy";
import {
  loadMobileProfileStatus,
  mobileProfileLoadingState,
  type MobileProfileRouteState,
} from "./profileRouteState";

const MobileRouteSnapshotContext = createContext<MobileRouteSnapshot>(defaultMobileRouteSnapshot);
const MobileProfileRefreshContext = createContext<() => Promise<void>>(
  async () => undefined,
);
const MobileSpecialistRefreshContext = createContext<() => Promise<void>>(
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
        <MobileSpecialistRefreshContext.Provider value={async () => undefined}>
          {children}
        </MobileSpecialistRefreshContext.Provider>
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
    setProfile(mobileProfileLoadingState);
    const nextProfile = await loadMobileProfileStatus(auth.request);
    if (generation === requestGeneration.current) {
      setProfile(nextProfile);
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
    ...mobileProfileLoadingState,
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
        <MobileSpecialistRefreshContext.Provider value={refreshSpecialistAccess}>
          {children}
        </MobileSpecialistRefreshContext.Provider>
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

export function useRefreshMobileSpecialistAccess(): () => Promise<void> {
  return useContext(MobileSpecialistRefreshContext);
}

export interface RouteGuardProps {
  readonly children: ReactNode;
  readonly kind: MobileRouteKind;
  readonly requiredCapability?: MobileProductCapability;
}

export function RouteGuard({ children, kind, requiredCapability }: RouteGuardProps) {
  const snapshot = useMobileRouteSnapshot();
  const refreshProfileStatus = useRefreshMobileProfileStatus();
  const refreshSpecialistAccess = useRefreshMobileSpecialistAccess();
  const decision = decideMobileRoute(kind, snapshot, requiredCapability);

  if (decision.status === "loading") {
    return <RouteGuardLoading />;
  }
  if (decision.status === "redirect") {
    return <Redirect href={decision.href} />;
  }
  if (decision.status === "error") {
    return (
      <RouteGuardError
        onRetry={() => void retryForResource(decision.resource, refreshProfileStatus, refreshSpecialistAccess)}
        resource={decision.resource}
      />
    );
  }
  return <>{children}</>;
}

function retryForResource(
  resource: MobileRouteErrorResource,
  refreshProfileStatus: () => Promise<void>,
  refreshSpecialistAccess: () => Promise<void>,
): Promise<void> {
  return resource === "profile" ? refreshProfileStatus() : refreshSpecialistAccess();
}

function RouteGuardLoading() {
  return (
    <SafeAreaView edges={["top", "bottom"]} style={[styles.loading, RTL_LAYOUT]}>
      <View accessibilityRole="progressbar">
        <ActivityIndicator accessibilityLabel="در حال بارگذاری" color={fiticianTokens.colors.aqua} />
      </View>
    </SafeAreaView>
  );
}

function RouteGuardError({
  onRetry,
  resource,
}: {
  readonly onRetry: () => void;
  readonly resource: MobileRouteErrorResource;
}) {
  const profile = resource === "profile";
  return (
    <SafeAreaView edges={["top", "bottom"]} style={[styles.loading, RTL_LAYOUT]}>
      <View style={[styles.error, RTL_LAYOUT]}>
        <Notice
          actionLabel="دوباره تلاش کن"
          message={profile ? "اطلاعات پروفایل دریافت نشد." : "دسترسی این بخش بررسی نشد."}
          onAction={onRetry}
          title={profile ? "اتصال به پروفایل برقرار نشد" : "بررسی دسترسی انجام نشد"}
          variant="warning"
        />
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
  error: {
    maxWidth: 520,
    paddingHorizontal: fiticianTokens.spacing[4],
    width: "100%",
  },
});
