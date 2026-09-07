import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { Pressable, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";

import { Button, Card, Notice, TextField } from "../../../ui/components";
import { AuthScaffold } from "../../../auth/AuthScaffold";
import { authCopy, mobileAuthCopy } from "../../../auth/copy";
import { authErrorMessage } from "../../../auth/authError";
import { authStyles } from "../../../auth/authStyles";
import { useGoogleSignIn } from "../../../auth/GoogleSignIn";
import { useMobileAuth } from "../../../auth/MobileAuthProvider";
import { normalizePhoneNumber, validateEmail, validatePhoneNumber } from "../../../auth/validation";

type SignInMode = "email" | "phone";

interface EmailSignInFormValues {
  email: string;
  password: string;
}

interface PhoneSignInFormValues {
  phoneNumber: string;
}

export default function SignInScreen() {
  const router = useRouter();
  const auth = useMobileAuth();
  const google = useGoogleSignIn();
  const params = useLocalSearchParams<{ reason?: string }>();
  const [mode, setMode] = useState<SignInMode>("email");
  const [error, setError] = useState<string | null>(null);
  const [googleBusy, setGoogleBusy] = useState(false);
  const emailForm = useForm<EmailSignInFormValues>({
    defaultValues: { email: "", password: "" },
  });
  const phoneForm = useForm<PhoneSignInFormValues>({ defaultValues: { phoneNumber: "" } });
  const sessionExpired = params.reason === "session-expired" || auth.sessionExpired;

  const submitEmail = emailForm.handleSubmit(async (values) => {
    setError(null);
    try {
      await auth.signInWithPassword({ email: values.email.trim(), password: values.password });
      router.replace("/onboarding");
    } catch (submissionError) {
      setError(authErrorMessage(submissionError));
    }
  });

  const submitPhone = phoneForm.handleSubmit(async ({ phoneNumber }) => {
    setError(null);
    try {
      const normalizedPhone = normalizePhoneNumber(phoneNumber);
      await auth.sendPhoneOtp(normalizedPhone);
      router.push({ pathname: "/auth/phone-otp", params: { phoneNumber: normalizedPhone } });
    } catch (submissionError) {
      setError(authErrorMessage(submissionError, "otp"));
    }
  });

  const submitGoogle = async () => {
    setError(null);
    setGoogleBusy(true);
    try {
      await auth.signInWithGoogle(await google.signIn());
      router.replace("/onboarding");
    } catch (submissionError) {
      setError(authErrorMessage(submissionError, "google"));
    } finally {
      setGoogleBusy(false);
    }
  };

  return (
    <AuthScaffold subtitle={authCopy.login.subtitle} title={authCopy.login.title}>
      <View style={authStyles.content}>
        {sessionExpired ? <Notice message={mobileAuthCopy.sessionExpired} variant="warning" /> : null}
        {auth.startupError ? <Notice message={mobileAuthCopy.startupFailed} variant="warning" /> : null}
        {error ? <Notice message={error} variant="danger" /> : null}
        <View accessibilityRole="tablist" style={authStyles.modeRow}>
          <Button
            label={authCopy.login.emailTab}
            onPress={() => {
              setError(null);
              setMode("email");
            }}
            style={{ flex: 1 }}
            variant={mode === "email" ? "primary" : "secondary"}
          />
          <Button
            label={authCopy.login.phoneTab}
            onPress={() => {
              setError(null);
              setMode("phone");
            }}
            style={{ flex: 1 }}
            variant={mode === "phone" ? "primary" : "secondary"}
          />
        </View>
        {mode === "email" ? (
          <Card>
            <View style={authStyles.content}>
              <Controller
                control={emailForm.control}
                name="email"
                rules={{ required: "ایمیل را وارد کنید.", validate: validateEmail }}
                render={({ field, fieldState }) => (
                  <TextField
                    autoCapitalize="none"
                    autoComplete="email"
                    error={fieldState.error?.message}
                    keyboardType="email-address"
                    label={authCopy.common.email}
                    onBlur={field.onBlur}
                    onChangeText={field.onChange}
                    textContentType="emailAddress"
                    textDirection="ltr"
                    value={field.value}
                  />
                )}
              />
              <Controller
                control={emailForm.control}
                name="password"
                rules={{ required: "رمز عبور را وارد کنید." }}
                render={({ field, fieldState }) => (
                  <TextField
                    autoCapitalize="none"
                    autoComplete="current-password"
                    error={fieldState.error?.message}
                    label={authCopy.common.password}
                    onBlur={field.onBlur}
                    onChangeText={field.onChange}
                    secureTextEntry
                    textContentType="password"
                    value={field.value}
                  />
                )}
              />
              <Button label={authCopy.login.submit} loading={auth.busy} onPress={submitEmail} />
              <Pressable accessibilityRole="button" onPress={() => router.push("/auth/forgot-password")}>
                <Text style={authStyles.link}>{authCopy.login.forgotPassword}</Text>
              </Pressable>
            </View>
          </Card>
        ) : (
          <Card>
            <View style={authStyles.content}>
              <Controller
                control={phoneForm.control}
                name="phoneNumber"
                rules={{ required: "شماره موبایل را وارد کنید.", validate: validatePhoneNumber }}
                render={({ field, fieldState }) => (
                  <TextField
                    autoComplete="tel"
                    error={fieldState.error?.message}
                    keyboardType="phone-pad"
                    label={authCopy.common.phoneNumber}
                    onBlur={field.onBlur}
                    onChangeText={field.onChange}
                    placeholder="۰۹۱۲۳۴۵۶۷۸۹"
                    textContentType="telephoneNumber"
                    textDirection="ltr"
                    value={field.value}
                  />
                )}
              />
              <Button label={authCopy.login.sendOtp} loading={auth.busy} onPress={submitPhone} />
            </View>
          </Card>
        )}
        {google.available ? (
          <>
            <View style={authStyles.divider}>
              <View style={authStyles.dividerLine} />
              <Text style={authStyles.dividerText}>{authCopy.login.or}</Text>
              <View style={authStyles.dividerLine} />
            </View>
            <Button
              disabled={!google.ready}
              label="ادامه با گوگل"
              loading={googleBusy}
              onPress={() => void submitGoogle()}
              variant="secondary"
            />
          </>
        ) : null}
        <View style={authStyles.footer}>
          <Text style={authStyles.footerText}>{authCopy.login.noAccount}</Text>
          <Pressable accessibilityRole="button" onPress={() => router.push("/auth/register")}>
            <Text style={authStyles.link}>{authCopy.login.registerLink}</Text>
          </Pressable>
        </View>
      </View>
    </AuthScaffold>
  );
}
