import { useEffect, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";
import { View } from "react-native";

import { Button, Notice } from "../../../ui/components";
import { AuthScaffold } from "../../../auth/AuthScaffold";
import { authCopy } from "../../../auth/copy";
import { authStyles } from "../../../auth/authStyles";
import { useMobileAuth } from "../../../auth/MobileAuthProvider";

type VerificationStatus = "checking" | "invalid" | "success";

function firstParam(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

export default function VerifyEmailScreen() {
  const router = useRouter();
  const auth = useMobileAuth();
  const params = useLocalSearchParams<{ token?: string }>();
  const token = firstParam(params.token);
  const [status, setStatus] = useState<VerificationStatus>(token ? "checking" : "invalid");

  useEffect(() => {
    if (!token) return undefined;
    let active = true;
    void auth.verifyEmail(token).then(
      () => {
        if (active) setStatus("success");
      },
      () => {
        if (active) setStatus("invalid");
      },
    );
    return () => {
      active = false;
    };
  }, [auth, token]);

  return (
    <AuthScaffold
      subtitle={authCopy.emailVerification.subtitle}
      title={authCopy.emailVerification.title}
    >
      <View style={authStyles.content}>
        {status === "checking" ? <Notice message={authCopy.emailVerification.checking} variant="info" /> : null}
        {status === "success" ? <Notice message={authCopy.emailVerification.success} variant="success" /> : null}
        {status === "invalid" ? <Notice message={authCopy.emailVerification.invalidToken} variant="danger" /> : null}
        <Button label={authCopy.emailVerification.backToLogin} onPress={() => router.replace("/auth/sign-in")} />
      </View>
    </AuthScaffold>
  );
}
