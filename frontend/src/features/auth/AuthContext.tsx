/* oxlint-disable react/only-export-components -- provider and its hook form one public boundary */
import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import * as api from "./api";
import type { Credentials, User } from "./types";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  startupError: boolean;
  retryStartup: () => void;
  register: (credentials: Credentials) => Promise<void>;
  login: (credentials: Credentials) => Promise<void>;
  loginWithPhone: (phoneNumber: string, code: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [startupError, setStartupError] = useState(false);
  const [startupAttempt, setStartupAttempt] = useState(0);
  const requestGeneration = useRef(0);

  useEffect(() => {
    const generation = ++requestGeneration.current;
    let active = true;
    setLoading(true);
    setStartupError(false);
    api
      .getCurrentUser()
      .then((currentUser) => {
        if (active && generation === requestGeneration.current) {
          setUser(currentUser);
        }
      })
      .catch(() => {
        if (active && generation === requestGeneration.current) {
          setStartupError(true);
        }
      })
      .finally(() => {
        if (active && generation === requestGeneration.current) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [startupAttempt]);

  const cancelStartupRequest = () => {
    requestGeneration.current += 1;
    setLoading(false);
    setStartupError(false);
  };

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      startupError,
      retryStartup: () => setStartupAttempt((attempt) => attempt + 1),
      register: async (credentials) => {
        cancelStartupRequest();
        setUser(await api.register(credentials));
      },
      login: async (credentials) => {
        cancelStartupRequest();
        setUser(await api.login(credentials));
      },
      loginWithPhone: async (phoneNumber, code) => {
        cancelStartupRequest();
        setUser(await api.verifyPhoneOtp(phoneNumber, code));
      },
      logout: async () => {
        cancelStartupRequest();
        await api.logout();
        setUser(null);
      },
    }),
    [loading, startupError, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
