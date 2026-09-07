import { useEffect, useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { Pressable, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";

import { Button, Notice, TextField } from "../../../ui/components";
import { AuthScaffold } from "../../../auth/AuthScaffold";
import { authCopy } from "../../../auth/copy";
import { authErrorMessage } from "../../../auth/authError";
import { authStyles } from "../../../auth/authStyles";
import { useMobileAuth } from "../../../auth/MobileAuthProvider";
import { normalizePhoneNumber, validateOtpCode } from "../../../auth/validation";

interface OtpFormValues {
  code: string;
}

export default function PhoneOtpScreen() {
  const router = useRouter();
  const auth = useMobileAuth();
  const params = useLocalSearchParams<{ phoneNumber?: string }>();
  const phoneNumber = useMemo(
    () => normalizePhoneNumber(
      Array.isArray(params.phoneNumber) ? params.phoneNumber[0] ?? "" : params.phoneNumber ?? "",
    ),
    [params.phoneNumber],
  );
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const { control, handleSubmit } = useForm<OtpFormValues>({ defaultValues: { code: "" } });

  useEffect(() => {
    if (secondsLeft <= 0) return undefined;
    const timer = setInterval(() => setSecondsLeft((current) => Math.max(0, current - 1)), 1_000);
    return () => clearInterval(timer);
  }, [secondsLeft]);

  if (phoneNumber === "") {
    return (
      <AuthScaffold title={authCopy.common.otpCode}>
        <Notice message="شماره موبایل برای این درخواست پیدا نشد." variant="danger" />
        <Button label={authCopy.passwordRecovery.backToLogin} onPress={() => router.replace("/auth/sign-in")} />
      </AuthScaffold>
    );
  }

  const submit = handleSubmit(async ({ code }) => {
    setError(null);
    try {
      await auth.verifyPhoneOtp(phoneNumber, normalizePhoneNumber(code));
      router.replace("/onboarding");
    } catch (submissionError) {
      setError(authErrorMessage(submissionError, "otp"));
    }
  });

  const resend = async () => {
    setError(null);
    try {
      const result = await auth.sendPhoneOtp(phoneNumber);
      setSecondsLeft(result.retry_after_seconds);
    } catch (submissionError) {
      setError(authErrorMessage(submissionError, "otp"));
    }
  };

  return (
    <AuthScaffold
      subtitle={`${authCopy.login.phoneSubtitle} ${phoneNumber}`}
      title={authCopy.common.otpCode}
    >
      <View style={authStyles.content}>
        {error ? <Notice message={error} variant="danger" /> : null}
        <Controller
          control={control}
          name="code"
          rules={{ required: "کد ورود را وارد کنید.", validate: validateOtpCode }}
          render={({ field, fieldState }) => (
            <TextField
              autoCapitalize="none"
              autoComplete="one-time-code"
              error={fieldState.error?.message}
              keyboardType="number-pad"
              label={authCopy.common.otpCode}
              maxLength={6}
              onBlur={field.onBlur}
              onChangeText={field.onChange}
              textAlign="center"
              textDirection="ltr"
              value={field.value}
            />
          )}
        />
        <Button label={authCopy.login.verifyOtp} loading={auth.busy} onPress={submit} />
        <Pressable
          accessibilityRole="button"
          disabled={secondsLeft > 0 || auth.busy}
          onPress={() => void resend()}
        >
          <Text style={[authStyles.link, secondsLeft > 0 && { opacity: 0.5 }]}>
            {secondsLeft > 0
              ? authCopy.login.resendCountdown.replace("{{seconds}}", String(secondsLeft))
              : authCopy.login.resend}
          </Text>
        </Pressable>
      </View>
    </AuthScaffold>
  );
}
