import { afterEach, expect, it, vi } from "vitest";

import type { NetInfoState } from "@react-native-community/netinfo";

const diagnostics = vi.hoisted(() => ({
  logDevelopmentDiagnostic: vi.fn(),
}));

vi.mock("./logging", () => diagnostics);

import {
  ConnectivityMonitor,
  connectivitySnapshotFromNetInfo,
  type ConnectivitySnapshot,
} from "./connectivity";

vi.mock("@react-native-community/netinfo", () => ({
  default: { addEventListener: vi.fn() },
}));

afterEach(() => {
  vi.restoreAllMocks();
  diagnostics.logDevelopmentDiagnostic.mockClear();
});

function state(values: Partial<NetInfoState>): NetInfoState {
  return values as NetInfoState;
}

function networkType(value: string): NetInfoState["type"] {
  return value as NetInfoState["type"];
}

it("maps unknown, offline, and online network states explicitly", () => {
  expect(connectivitySnapshotFromNetInfo(state({ isConnected: null }))).toMatchObject({
    isOnline: false,
    status: "unknown",
  });
  expect(connectivitySnapshotFromNetInfo(state({ isConnected: false }))).toMatchObject({
    isOnline: false,
    status: "offline",
  });
  expect(
    connectivitySnapshotFromNetInfo(state({ isConnected: true, isInternetReachable: false })),
  ).toMatchObject({ isOnline: false, status: "offline" });
  expect(connectivitySnapshotFromNetInfo(state({ isConnected: true }))).toMatchObject({
    isOnline: true,
    status: "online",
  });
});

it("updates subscribers and TanStack online state through one native listener", () => {
  let emit: ((next: NetInfoState) => void) | null = null;
  const onlineStates: boolean[] = [];
  const snapshots: ConnectivitySnapshot[] = [];
  const monitor = new ConnectivityMonitor(
    (listener) => {
      emit = listener;
      return () => {
        emit = null;
      };
    },
    (online) => onlineStates.push(online),
  );
  const unsubscribe = monitor.subscribe((snapshot) => snapshots.push(snapshot));
  const emitState = (next: NetInfoState) => {
    if (emit === null) {
      throw new Error("native listener was not registered");
    }
    emit(next);
  };

  monitor.start();
  emitState(state({ isConnected: false, isInternetReachable: false }));
  emitState(state({ isConnected: true, isInternetReachable: true }));

  expect(monitor.getSnapshot().status).toBe("online");
  expect(snapshots.map((snapshot) => snapshot.status)).toEqual(["offline", "online"]);
  expect(onlineStates).toEqual([false, true]);

  unsubscribe();
  monitor.stop();
  expect(emit).toBeNull();
});

it("keeps the native subscription idempotent and supports a clean restart", () => {
  let subscriptionCount = 0;
  const unsubscribers: Array<() => void> = [];
  const monitor = new ConnectivityMonitor((listener) => {
    subscriptionCount += 1;
    const unsubscribe = () => undefined;
    unsubscribers.push(unsubscribe);
    void listener;
    return unsubscribe;
  });

  monitor.start();
  monitor.start();
  expect(subscriptionCount).toBe(1);

  monitor.stop();
  monitor.stop();
  monitor.start();

  expect(subscriptionCount).toBe(2);
  expect(unsubscribers).toHaveLength(2);
});

it("reports connectivity transitions without logging every repeated native update", () => {
  let emit: ((next: NetInfoState) => void) | null = null;
  const monitor = new ConnectivityMonitor((listener) => {
    emit = listener;
    return () => undefined;
  });
  const emitState = (next: NetInfoState) => {
    if (emit === null) throw new Error("native listener was not registered");
    emit(next);
  };

  monitor.start();
  emitState(state({ isConnected: true, type: networkType("wifi") }));
  emitState(state({ isConnected: true, type: networkType("wifi") }));
  emitState(state({ isConnected: false, type: networkType("none") }));

  expect(diagnostics.logDevelopmentDiagnostic).toHaveBeenCalledTimes(2);
  expect(diagnostics.logDevelopmentDiagnostic).toHaveBeenNthCalledWith(
    1,
    "connectivity_changed",
    "info",
    { is_online: true, network_type: "wifi", status: "online" },
  );
  expect(diagnostics.logDevelopmentDiagnostic).toHaveBeenNthCalledWith(
    2,
    "connectivity_changed",
    "info",
    { is_online: false, network_type: "none", status: "offline" },
  );
});
