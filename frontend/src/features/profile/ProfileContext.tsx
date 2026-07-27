/* oxlint-disable react/only-export-components -- provider and hook form one public boundary */
import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useAuth } from "../auth/AuthContext";
import * as api from "./api";
import type { Profile, ProfileInput, ProfilePatch } from "./types";

export type ProfileStatus = "idle" | "loading" | "missing" | "ready" | "error";

type ProfileContextValue = {
  profile: Profile | null;
  status: ProfileStatus;
  retryProfile: () => void;
  createProfile: (input: ProfileInput) => Promise<Profile>;
  updateProfile: (patch: ProfilePatch) => Promise<Profile>;
};

const ProfileContext = createContext<ProfileContextValue | null>(null);

export function ProfileProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const userId = user?.id ?? null;
  const [profile, setProfile] = useState<Profile | null>(null);
  const [status, setStatus] = useState<ProfileStatus>("idle");
  const [retryAttempt, setRetryAttempt] = useState(0);
  const requestGeneration = useRef(0);

  useEffect(() => {
    const generation = ++requestGeneration.current;
    if (userId === null) {
      setProfile(null);
      setStatus("idle");
      return;
    }

    let active = true;
    setStatus("loading");
    api
      .getProfile()
      .then((currentProfile) => {
        if (active && generation === requestGeneration.current) {
          setProfile(currentProfile);
          setStatus(currentProfile === null ? "missing" : "ready");
        }
      })
      .catch(() => {
        if (active && generation === requestGeneration.current) {
          setProfile(null);
          setStatus("error");
        }
      });

    return () => {
      active = false;
    };
  }, [retryAttempt, userId]);

  const value = useMemo<ProfileContextValue>(
    () => ({
      profile,
      status,
      retryProfile: () => {
        requestGeneration.current += 1;
        setRetryAttempt((attempt) => attempt + 1);
      },
      createProfile: async (input) => {
        const generation = ++requestGeneration.current;
        try {
          const createdProfile = await api.createProfile(input);
          if (generation === requestGeneration.current) {
            setProfile(createdProfile);
            setStatus("ready");
          }
          return createdProfile;
        } catch (error) {
          if (generation === requestGeneration.current) {
            setProfile(null);
            setStatus("missing");
          }
          throw error;
        }
      },
      updateProfile: async (patch) => {
        const generation = ++requestGeneration.current;
        try {
          const updatedProfile = await api.updateProfile(patch);
          if (generation === requestGeneration.current) {
            setProfile(updatedProfile);
            setStatus("ready");
          }
          return updatedProfile;
        } catch (error) {
          if (generation === requestGeneration.current) {
            setStatus("ready");
          }
          throw error;
        }
      },
    }),
    [profile, status],
  );

  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>;
}

export function useProfile(): ProfileContextValue {
  const context = useContext(ProfileContext);
  if (context === null) {
    throw new Error("useProfile must be used within ProfileProvider");
  }
  return context;
}
