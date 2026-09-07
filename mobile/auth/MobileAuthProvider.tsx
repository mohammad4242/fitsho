/* oxlint-disable react/only-export-components -- provider and its hook form one public boundary */
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type { Credentials, GenericMessage, User } from "@fitician/core/auth";
import type { TransportRequest } from "@fitician/core";

import { createNativeTransport } from "../api/nativeTransport";
import { getMobileRuntimeConfig } from "../config/nativeRuntimeConfig";
import { createSecureRefreshTokenStore } from "./tokenStore";
import { resolveMobileClientMetadata } from "./deviceMetadata";
import {
  MobileAuthSession,
  type MobileAuthSessionSnapshot,
} from "./authSession";

export interface MobileAuthContextValue extends MobileAuthSessionSnapshot {
  readonly forgotPassword: (email: string) => Promise<GenericMessage>;
  readonly logout: () => Promise<void>;
  readonly logoutAll: () => Promise<void>;
  readonly register: (credentials: Credentials) => Promise<User>;
  readonly request: <TResponse>(request: TransportRequest) => Promise<TResponse>;
  readonly resetPassword: (token: string, password: string) => Promise<void>;
  readonly sendEmailVerification: () => Promise<GenericMessage>;
  readonly sendPhoneOtp: (phoneNumber: string) => Promise<GenericMessage & { retry_after_seconds: number }>;
  readonly signInWithGoogle: (credential: string) => Promise<User>;
  readonly signInWithPassword: (credentials: Credentials) => Promise<User>;
  readonly verifyEmail: (token: string) => Promise<void>;
  readonly verifyPhoneOtp: (phoneNumber: string, code: string) => Promise<User>;
}

export interface MobileAuthProviderProps {
  readonly children: ReactNode;
  readonly session?: MobileAuthSession;
}

const MobileAuthContext = createContext<MobileAuthContextValue | null>(null);

function createDefaultSession(): MobileAuthSession {
  const runtime = getMobileRuntimeConfig();
  const transport = createNativeTransport({
    apiBaseUrl: runtime.apiBaseUrl,
    trustedOrigin: runtime.frontendOrigin,
  });
  return new MobileAuthSession({
    metadata: () => resolveMobileClientMetadata(),
    refreshTokenStorage: createSecureRefreshTokenStore(),
    transport,
    trustedOrigin: runtime.frontendOrigin,
  });
}

export function MobileAuthProvider({ children, session }: MobileAuthProviderProps) {
  const sessionRef = useRef<MobileAuthSession | null>(null);
  if (sessionRef.current === null) {
    sessionRef.current = session ?? createDefaultSession();
  }
  const activeSession = sessionRef.current;
  const [snapshot, setSnapshot] = useState<MobileAuthSessionSnapshot>(activeSession.getSnapshot());

  useEffect(() => {
    const unsubscribe = activeSession.subscribe(setSnapshot);
    void activeSession.restore();
    return unsubscribe;
  }, [activeSession]);

  const forgotPassword = useCallback((email: string) => activeSession.forgotPassword(email), [activeSession]);
  const logout = useCallback(() => activeSession.logout(), [activeSession]);
  const logoutAll = useCallback(() => activeSession.logoutAll(), [activeSession]);
  const register = useCallback((credentials: Credentials) => activeSession.register(credentials), [activeSession]);
  const request = useCallback(
    <TResponse,>(requestInput: TransportRequest) => activeSession.request<TResponse>(requestInput),
    [activeSession],
  );
  const resetPassword = useCallback(
    (token: string, password: string) => activeSession.resetPassword(token, password),
    [activeSession],
  );
  const sendEmailVerification = useCallback(
    () => activeSession.sendEmailVerification(),
    [activeSession],
  );
  const sendPhoneOtp = useCallback(
    (phoneNumber: string) => activeSession.sendPhoneOtp(phoneNumber),
    [activeSession],
  );
  const signInWithGoogle = useCallback(
    (credential: string) => activeSession.signInWithGoogle(credential),
    [activeSession],
  );
  const signInWithPassword = useCallback(
    (credentials: Credentials) => activeSession.signInWithPassword(credentials),
    [activeSession],
  );
  const verifyEmail = useCallback((token: string) => activeSession.verifyEmail(token), [activeSession]);
  const verifyPhoneOtp = useCallback(
    (phoneNumber: string, code: string) => activeSession.verifyPhoneOtp(phoneNumber, code),
    [activeSession],
  );

  const value = useMemo<MobileAuthContextValue>(
    () => ({
      ...snapshot,
      forgotPassword,
      logout,
      logoutAll,
      register,
      request,
      resetPassword,
      sendEmailVerification,
      sendPhoneOtp,
      signInWithGoogle,
      signInWithPassword,
      verifyEmail,
      verifyPhoneOtp,
    }),
    [
      forgotPassword,
      logout,
      logoutAll,
      register,
      request,
      resetPassword,
      sendEmailVerification,
      sendPhoneOtp,
      signInWithGoogle,
      signInWithPassword,
      snapshot,
      verifyEmail,
      verifyPhoneOtp,
    ],
  );

  return <MobileAuthContext.Provider value={value}>{children}</MobileAuthContext.Provider>;
}

export function useMobileAuth(): MobileAuthContextValue {
  const context = useContext(MobileAuthContext);
  if (context === null) {
    throw new Error("useMobileAuth must be used within MobileAuthProvider");
  }
  return context;
}
