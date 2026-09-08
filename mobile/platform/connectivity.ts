import NetInfo, { type NetInfoState } from "@react-native-community/netinfo";
import { onlineManager } from "@tanstack/react-query";

import { logDevelopmentDiagnostic } from "./logging";

export type ConnectivityStatus = "unknown" | "offline" | "online";

export type ConnectivitySnapshot = {
  readonly isConnected: boolean | null;
  readonly isInternetReachable: boolean | null;
  readonly isOnline: boolean;
  readonly status: ConnectivityStatus;
  readonly type: NetInfoState["type"] | null;
};

export type NetInfoSubscriber = (
  listener: (state: NetInfoState) => void,
) => () => void;

const UNKNOWN_SNAPSHOT: ConnectivitySnapshot = {
  isConnected: null,
  isInternetReachable: null,
  isOnline: false,
  status: "unknown",
  type: null,
};

export function connectivitySnapshotFromNetInfo(state: NetInfoState): ConnectivitySnapshot {
  const status: ConnectivityStatus =
    state.isConnected === false || state.isInternetReachable === false
      ? "offline"
      : state.isConnected === true
        ? "online"
        : "unknown";

  return {
    isConnected: state.isConnected,
    isInternetReachable: state.isInternetReachable,
    isOnline: status === "online",
    status,
    type: state.type,
  };
}

export class ConnectivityMonitor {
  private snapshot: ConnectivitySnapshot = UNKNOWN_SNAPSHOT;
  private lastDiagnosticStatus: ConnectivityStatus | null = null;
  private unsubscribeNative: (() => void) | null = null;
  private readonly listeners = new Set<(snapshot: ConnectivitySnapshot) => void>();

  constructor(
    private readonly subscribeNative: NetInfoSubscriber = (listener) =>
      NetInfo.addEventListener(listener),
    private readonly setQueryOnline: (online: boolean) => void = (online) =>
      onlineManager.setOnline(online),
  ) {}

  start(): void {
    if (this.unsubscribeNative !== null) {
      return;
    }
    this.unsubscribeNative = this.subscribeNative((state) => this.update(state));
  }

  stop(): void {
    this.unsubscribeNative?.();
    this.unsubscribeNative = null;
  }

  getSnapshot(): ConnectivitySnapshot {
    return this.snapshot;
  }

  subscribe(listener: (snapshot: ConnectivitySnapshot) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private update(state: NetInfoState): void {
    this.snapshot = connectivitySnapshotFromNetInfo(state);
    this.setQueryOnline(this.snapshot.isOnline);
    if (this.lastDiagnosticStatus !== this.snapshot.status) {
      this.lastDiagnosticStatus = this.snapshot.status;
      logDevelopmentDiagnostic("connectivity_changed", "info", {
        is_online: this.snapshot.isOnline,
        network_type: this.snapshot.type,
        status: this.snapshot.status,
      });
    }
    for (const listener of this.listeners) {
      listener(this.snapshot);
    }
  }
}

export const connectivityMonitor = new ConnectivityMonitor();
