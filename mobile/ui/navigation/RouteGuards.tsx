import { type ReactNode, createContext, useContext } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { Redirect } from "expo-router";

import { fiticianTokens } from "../tokens";
import {
  decideMobileRoute,
  defaultMobileRouteSnapshot,
  type MobileProductCapability,
  type MobileRouteKind,
  type MobileRouteSnapshot,
} from "./routePolicy";

const MobileRouteSnapshotContext = createContext<MobileRouteSnapshot>(defaultMobileRouteSnapshot);

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
      {children}
    </MobileRouteSnapshotContext.Provider>
  );
}

export function useMobileRouteSnapshot(): MobileRouteSnapshot {
  return useContext(MobileRouteSnapshotContext);
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
    <View accessibilityRole="progressbar" style={styles.loading}>
      <ActivityIndicator accessibilityLabel="در حال بارگذاری" color={fiticianTokens.colors.aqua} />
    </View>
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
