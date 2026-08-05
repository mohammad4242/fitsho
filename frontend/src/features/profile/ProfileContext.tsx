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
import { HYDRATED_ACCOUNT_EVENT, HYDRATED_ACCOUNT_KEY } from "../publicOnboarding/onboardingDraft";
import * as api from "./api";
import type {
  ProductMode,
  Profile,
  ProfileInput,
  ProfilePatch,
  ProfileStatusResponse,
} from "./types";

export type ProfileStatus = "idle" | "loading" | "missing" | "mode_selected" | "ready" | "error";

type ProfileContextValue = {
  profile: Profile | null;
  status: ProfileStatus;
  productMode: ProductMode | null;
  retryProfile: () => void;
  createProfile: (input: ProfileInput) => Promise<Profile>;
  selectProductMode: (mode: ProductMode) => Promise<ProfileStatusResponse>;
  updateProfile: (patch: ProfilePatch) => Promise<Profile>;
};

const ProfileContext = createContext<ProfileContextValue | null>(null);

export function ProfileProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const userId = user?.id ?? null;
  const [profile, setProfile] = useState<Profile | null>(null);
  const [status, setStatus] = useState<ProfileStatus>("idle");
  const [productMode, setProductMode] = useState<ProductMode | null>(null);
  const [retryAttempt, setRetryAttempt] = useState(0);
  const requestGeneration = useRef(0);

  useEffect(() => {
    const refreshAfterHydration = () => setRetryAttempt((attempt) => attempt + 1);
    window.addEventListener(HYDRATED_ACCOUNT_EVENT, refreshAfterHydration);
    return () => window.removeEventListener(HYDRATED_ACCOUNT_EVENT, refreshAfterHydration);
  }, []);

  useEffect(() => {
    const generation = ++requestGeneration.current;
    if (userId === null) {
      sessionStorage.removeItem(HYDRATED_ACCOUNT_KEY);
      setProfile(null);
      setProductMode(null);
      setStatus("idle");
      return;
    }

    let active = true;
    setStatus("loading");
    api.getProfileStatus()
      .then(async (profileStatus) => {
        if (active && generation === requestGeneration.current) {
          setProductMode(profileStatus.product_mode);
        }
        const readyStates = new Set([
          "training_ready",
          "both_ready",
          "nutrition_draft_ready",
          "nutrition_ready",
        ]);
        const shouldLoadTrainingProfile = profileStatus.product_mode === "training"
          ? profileStatus.completion_state === "training_ready"
          : profileStatus.product_mode === "both"
            && !["shared_profile_incomplete", "training_onboarding_incomplete"].includes(
              profileStatus.completion_state,
            );
        const currentProfile = shouldLoadTrainingProfile
          ? await api.getProfile()
          : null;
        if (active && generation === requestGeneration.current) {
          if (profileStatus.completion_state !== "product_mode_not_selected") {
            sessionStorage.removeItem(HYDRATED_ACCOUNT_KEY);
          }
          setProfile(currentProfile);
          setStatus(profileStatus.completion_state === "product_mode_not_selected"
            ? "missing"
            : readyStates.has(profileStatus.completion_state) ? "ready" : "mode_selected");
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
      productMode,
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
            setStatus(productMode === "training" ? "ready" : "mode_selected");
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
      selectProductMode: async (mode) => {
        const selected = await api.selectProductMode(mode);
        setProductMode(selected.product_mode);
        setProfile(null);
        setStatus("mode_selected");
        return selected;
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
    [productMode, profile, status],
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

export function useOptionalProfile(): ProfileContextValue | null {
  return useContext(ProfileContext);
}
