import * as AppleAuthentication from "expo-apple-authentication";
import { randomUUID } from "expo-crypto";
import { useCallback, useEffect, useState } from "react";
import { Platform } from "react-native";

import {
  appleCredentialFromResult,
  appleResultMessage,
  AppleSignInFlowError,
  type AppleAuthCredential,
} from "./appleCredential";

export interface AppleSignInController {
  readonly available: boolean;
  readonly ready: boolean;
  readonly signIn: () => Promise<AppleAuthCredential>;
}

export function useAppleSignIn(): AppleSignInController {
  const isIos = Platform.OS === "ios";
  const [available, setAvailable] = useState(false);
  const [checked, setChecked] = useState(!isIos);

  useEffect(() => {
    let active = true;
    if (!isIos) {
      setAvailable(false);
      setChecked(true);
      return () => {
        active = false;
      };
    }
    void AppleAuthentication.isAvailableAsync()
      .then((result) => {
        if (!active) return;
        setAvailable(result);
        setChecked(true);
      })
      .catch(() => {
        if (!active) return;
        setAvailable(false);
        setChecked(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const signIn = useCallback(async () => {
    if (!isIos || !available) {
      throw new AppleSignInFlowError("ورود با اپل در این دستگاه در دسترس نیست.");
    }
    const nonce = randomUUID();
    try {
      const result = await AppleAuthentication.signInAsync({
        nonce,
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
        ],
      });
      const credential = appleCredentialFromResult(result, nonce);
      if (credential === null) {
        throw new AppleSignInFlowError("پاسخ ورود با اپل معتبر نبود.");
      }
      return credential;
    } catch (error) {
      if (error instanceof AppleSignInFlowError) throw error;
      throw new AppleSignInFlowError(appleResultMessage(error));
    }
  }, [available]);

  return { available, ready: checked, signIn };
}
