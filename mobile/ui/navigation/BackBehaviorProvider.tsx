import { type ReactNode, createContext, useContext, useEffect, useMemo, useRef } from "react";
import { BackHandler, Platform } from "react-native";
import { useRouter } from "expo-router";

import {
  AndroidBackCoordinator,
  type AndroidBackHandler,
  type AndroidBackHandlerKind,
} from "./backBehavior";

const AndroidBackCoordinatorContext = createContext<AndroidBackCoordinator | null>(null);

export interface AndroidBackBehaviorProviderProps {
  readonly children: ReactNode;
}

export function AndroidBackBehaviorProvider({ children }: AndroidBackBehaviorProviderProps) {
  const router = useRouter();
  const coordinator = useMemo(
    () =>
      new AndroidBackCoordinator({
        canGoBack: () => router.canGoBack(),
        exitApp: () => BackHandler.exitApp(),
        goBack: () => router.back(),
      }),
    [router],
  );

  useEffect(() => {
    if (Platform.OS !== "android") {
      return undefined;
    }

    const subscription = BackHandler.addEventListener(
      "hardwareBackPress",
      () => coordinator.handleBack(),
    );
    return () => subscription.remove();
  }, [coordinator]);

  return (
    <AndroidBackCoordinatorContext.Provider value={coordinator}>
      {children}
    </AndroidBackCoordinatorContext.Provider>
  );
}

export function useAndroidBackHandler(
  kind: AndroidBackHandlerKind,
  handler: AndroidBackHandler,
  enabled = true,
): void {
  const coordinator = useContext(AndroidBackCoordinatorContext);
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  if (coordinator === null) {
    throw new Error("useAndroidBackHandler must be used inside AndroidBackBehaviorProvider");
  }

  useEffect(() => {
    if (!enabled) {
      return undefined;
    }
    return coordinator.register(kind, () => handlerRef.current());
  }, [coordinator, enabled, kind]);
}
