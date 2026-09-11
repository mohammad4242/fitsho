import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import * as AppleAuthentication from "expo-apple-authentication";
import { Pressable, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";

import { Button, Notice, SegmentedControl, TextField } from "../../../ui/components";
import { AuthFormSection, AuthScaffold } from "../../../auth/AuthScaffold";
import { onboardingRoute, publicOnboardingParams } from "../../../auth/authRoute";
import { authCopy, mobileAuthCopy } from "../../../auth/copy";
import { authErrorMessage } from "../../../auth/authError";
import { authStyles } from "../../../auth/authStyles";
import { useAppleSignIn } from "../../../auth/AppleSignIn";
import { useGoogleSignIn } from "../../../auth/GoogleSignIn";
import { useMobileAuth } from "../../../auth/MobileAuthProvider";
import { normalizePhoneNumber, validateEmail, validateOtpCode, validatePassword, validatePhoneNumber } from "../../../auth/validation";

type SignInMode = "email" | "phone";
type PhoneStep = "request" | "verify";

function faNumber(value: number): string {
  return new Intl.NumberFormat("fa-IR").format(value);
}

interface EmailSignInFormValues {
  email: string;
  password: string;
}

interface PhoneSignInFormValues {
  code: string;
  phoneNumber: string;
}

export default function SignInScreen() {
  const router = useRouter();
  const auth = useMobileAuth();
  const apple = useAppleSignIn();
  const google = useGoogleSignIn();
  const params = useLocalSearchParams<{ reason?: string; source?: string }>();
  const [mode, setMode] = useState<SignInMode>("email");
  const [phoneStep, setPhoneStep] = useState<PhoneStep>("request");
  const [countdown, setCountdown] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [appleBusy, setAppleBusy] = useState(false);
  const emailForm = useForm<EmailSignInFormValues>({ defaultValues: { email: "", password: "" } });
  const phoneForm = useForm<PhoneSignInFormValues>({ defaultValues: { code: "", phoneNumber: "" } });
  const sessionExpired = params.reason === "session-expired" || auth.sessionExpired;

  useEffect(() => {
    if (countdown <= 0) return undefined;
    const timer = setInterval(() => setCountdown((current) => Math.max(0, current - 1)), 1_000);
    return () => clearInterval(timer);
  }, [countdown]);

  const submitEmail = emailForm.handleSubmit(async (values) => {
    setError(null);
    try {
      await auth.signInWithPassword({ email: values.email.trim(), password: values.password });
      router.replace(onboardingRoute(params.source));
    } catch (submissionError) {
      setError(authErrorMessage(submissionError));
    }
  });

  const submitPhone = phoneForm.handleSubmit(async ({ code, phoneNumber }) => {
    setError(null);
    const normalizedPhone = normalizePhoneNumber(phoneNumber);
    if (phoneStep === "request") {
      try {
        const result = await auth.sendPhoneOtp(normalizedPhone);
        phoneForm.setValue("phoneNumber", normalizedPhone, { shouldValidate: true });
        setPhoneStep("verify");
        setCountdown(result.retry_after_seconds);
      } catch (submissionError) {
        setError(authErrorMessage(submissionError, "otp"));
      }
      return;
    }
    const otpError = validateOtpCode(code);
    if (otpError) {
      setError(otpError);
      return;
    }
    try {
      await auth.verifyPhoneOtp(normalizedPhone, normalizePhoneNumber(code));
      router.replace(onboardingRoute(params.source));
    } catch (submissionError) {
      setError(authErrorMessage(submissionError, "otp"));
    }
  });

  const submitGoogle = async () => {
    setError(null);
    setGoogleBusy(true);
    try {
      await auth.signInWithGoogle(await google.signIn());
      router.replace(onboardingRoute(params.source));
    } catch (submissionError) {
      setError(authErrorMessage(submissionError, "google"));
    } finally {
      setGoogleBusy(false);
    }
  };

  const submitApple = async () => {
    setError(null);
    setAppleBusy(true);
    try {
      await auth.signInWithApple(await apple.signIn());
      router.replace(onboardingRoute(params.source));
    } catch (submissionError) {
      setError(authErrorMessage(submissionError, "apple"));
    } finally {
      setAppleBusy(false);
    }
  };

  const resendPhoneCode = () => {
    const phoneNumber = normalizePhoneNumber(phoneForm.getValues("phoneNumber"));
    if (countdown > 0 || validatePhoneNumber(phoneNumber)) return;
    setError(null);
    void auth.sendPhoneOtp(phoneNumber)
      .then((result) => setCountdown(result.retry_after_seconds))
      .catch((submissionError) => setError(authErrorMessage(submissionError, "otp")));
  };

  return (
    <AuthScaffold
      eyebrow={authCopy.login.eyebrow}
      subtitle={mode === "email" ? authCopy.login.subtitle : authCopy.login.phoneSubtitle}
      title={authCopy.login.title}
    >
      <View style={authStyles.content}>
        {sessionExpired ? <Notice message={mobileAuthCopy.sessionExpired} variant="warning" /> : null}
        {auth.startupError ? <Notice message={mobileAuthCopy.startupFailed} variant="warning" /> : null}
        <SegmentedControl
          accessibilityLabel={authCopy.login.methodLabel}
          onChange={(value) => {
            if (value !== "email" && value !== "phone") return;
            setError(null);
            setMode(value);
          }}
          options={[
            { label: authCopy.login.emailTab, value: "email" },
            { label: authCopy.login.phoneTab, value: "phone" },
          ]}
          selectedValue={mode}
        />

        {mode === "email" ? (
          <AuthFormSection>
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
            <View style={authStyles.fieldHeading}>
              <Text style={authStyles.fieldLabel}>{authCopy.common.password}</Text>
              <Pressable accessibilityRole="button" onPress={() => router.push({ pathname: "/auth/forgot-password", params: publicOnboardingParams(params.source) })}>
                <Text style={authStyles.inlineLink}>{authCopy.login.forgotPassword}</Text>
              </Pressable>
            </View>
            <Controller
              control={emailForm.control}
              name="password"
              rules={{ required: "رمز عبور را وارد کنید.", validate: validatePassword }}
              render={({ field, fieldState }) => (
                <TextField
                  accessibilityLabel={authCopy.common.password}
                  autoCapitalize="none"
                  autoComplete="current-password"
                  error={fieldState.error?.message}
                  onBlur={field.onBlur}
                  onChangeText={field.onChange}
                  secureTextEntry
                  maxLength={128}
                  textContentType="password"
                  value={field.value}
                />
              )}
            />
            {error ? <Notice message={error} variant="danger" /> : null}
            <Button label={authCopy.login.submit} loading={auth.busy} onPress={submitEmail} />
          </AuthFormSection>
        ) : (
          <AuthFormSection>
            <Controller
              control={phoneForm.control}
              name="phoneNumber"
              rules={{ required: "شماره موبایل را وارد کنید.", validate: validatePhoneNumber }}
              render={({ field, fieldState }) => (
                <TextField
                  autoComplete="tel"
                  editable={phoneStep === "request"}
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
            {phoneStep === "verify" ? (
              <>
                <Controller
                  control={phoneForm.control}
                  name="code"
                  render={({ field, fieldState }) => (
                    <TextField
                      autoComplete="one-time-code"
                      error={fieldState.error?.message}
                      keyboardType="number-pad"
                      label={authCopy.common.otpCode}
                      maxLength={6}
                      onBlur={field.onBlur}
                      onChangeText={field.onChange}
                      textDirection="ltr"
                      value={field.value}
                    />
                  )}
                />
                <View style={authStyles.fieldHeading}>
                  <Pressable accessibilityRole="button" disabled={countdown > 0 || auth.busy} onPress={resendPhoneCode}>
                    <Text style={authStyles.inlineLink}>
                      {countdown > 0 ? authCopy.login.resendCountdown.replace("{{seconds}}", faNumber(countdown)) : authCopy.login.resend}
                    </Text>
                  </Pressable>
                </View>
              </>
            ) : null}
            {error ? <Notice message={error} variant="danger" /> : null}
            <Button
              label={phoneStep === "request" ? authCopy.login.sendOtp : authCopy.login.verifyOtp}
              loading={auth.busy}
              onPress={submitPhone}
            />
          </AuthFormSection>
        )}

        <View style={authStyles.divider}>
          <View style={authStyles.dividerLine} />
          <Text style={authStyles.dividerText}>{authCopy.login.or}</Text>
          <View style={authStyles.dividerLine} />
        </View>
        <Button
          disabled={google.available && !google.ready}
          label="ادامه با گوگل"
          loading={googleBusy}
          onPress={() => void submitGoogle()}
          variant="secondary"
        />
        {apple.available ? (
          <AppleAuthentication.AppleAuthenticationButton
            accessibilityLabel="ادامه با اپل"
            buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.BLACK}
            buttonType={AppleAuthentication.AppleAuthenticationButtonType.SIGN_IN}
            cornerRadius={8}
            onPress={() => {
              if (appleBusy || auth.busy || !apple.ready) return;
              void submitApple();
            }}
            style={[authStyles.appleButton, (appleBusy || auth.busy) && { opacity: 0.6 }]}
          />
        ) : null}
        <View style={authStyles.footer}>
          <Text style={authStyles.footerText}>{authCopy.login.noAccount}</Text>
          <Pressable accessibilityRole="button" onPress={() => router.push({ pathname: "/auth/register", params: publicOnboardingParams(params.source) })}>
            <Text style={authStyles.link}>{authCopy.login.registerLink}</Text>
          </Pressable>
        </View>
      </View>
    </AuthScaffold>
  );
}
