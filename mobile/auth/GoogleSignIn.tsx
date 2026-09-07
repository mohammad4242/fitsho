import * as WebBrowser from "expo-web-browser";
import { useIdTokenAuthRequest } from "expo-auth-session/providers/google";
import { useCallback } from "react";

import { getMobileRuntimeConfig } from "../config/nativeRuntimeConfig";
import { googleCredentialFromResult, googleResultMessage, GoogleSignInFlowError } from "./googleCredential";

WebBrowser.maybeCompleteAuthSession();

const DISABLED_CLIENT_ID = "disabled-google-client-id.apps.googleusercontent.com";

export interface GoogleSignInController {
  readonly available: boolean;
  readonly ready: boolean;
  readonly signIn: () => Promise<string>;
}

export function useGoogleSignIn(): GoogleSignInController {
  const { googleAndroidClientId } = getMobileRuntimeConfig();
  const available = googleAndroidClientId !== null;
  const [request, , promptAsync] = useIdTokenAuthRequest(
    {
      androidClientId: googleAndroidClientId ?? DISABLED_CLIENT_ID,
      selectAccount: true,
    },
    { scheme: "fitician" },
  );

  const signIn = useCallback(async () => {
    if (!available) {
      throw new GoogleSignInFlowError("ورود با گوگل در این محیط پیکربندی نشده است.");
    }
    const result = await promptAsync();
    const credential = googleCredentialFromResult(result);
    if (credential === null) {
      throw new GoogleSignInFlowError(googleResultMessage(result));
    }
    return credential;
  }, [available, promptAsync]);

  return { available, ready: request !== null, signIn };
}
