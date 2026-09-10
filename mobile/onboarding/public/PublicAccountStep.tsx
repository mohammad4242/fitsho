import { useEffect, useState } from "react";
import { Pressable, Text, View } from "react-native";

import type { ProductMode } from "@fitician/core/profile";

import { authErrorMessage } from "../../auth/authError";
import { useGoogleSignIn } from "../../auth/GoogleSignIn";
import { useMobileAuth } from "../../auth/MobileAuthProvider";
import { normalizePhoneNumber, validateEmail, validateOtpCode, validatePassword, validatePhoneNumber } from "../../auth/validation";
import { AppIcon, Button, Notice, TextField } from "../../ui/components";
import { fiticianTokens } from "../../ui/tokens";
import { publicOnboardingStyles as styles } from "./publicOnboardingStyles";

export interface PublicAccountStepProps {
  readonly mode: ProductMode;
  readonly onAuthenticated: () => void;
  readonly onEdit: () => void;
}

type AccountMethod = "email" | "phone";
type AccountMode = "register" | "login";
type PhoneStep = "request" | "verify";

const copy = {
  accountModeLogin: "قبلاً حساب ساخته‌ام",
  accountModeRegister: "حساب جدید می‌سازم",
  apple: "Apple",
  changePhone: "تغییر شماره",
  confirmation: "تکرار رمز عبور",
  divider: "یا با ایمیل ادامه بده",
  edit: "بازگشت و ویرایش پاسخ‌ها",
  email: "ایمیل",
  emailMethod: "ایمیل",
  existingLogin: "ورود و ذخیره پاسخ‌ها",
  google: "Google",
  intro: "پاسخ‌ها بعد از ورود امن به حساب فیتشو منتقل می‌شوند.",
  lastStep: "آخرین قدم",
  login: "ورود و ذخیره پاسخ‌ها",
  newAccount: "ساخت حساب و ذخیره پاسخ‌ها",
  otpCode: "کد ورود",
  password: "رمز عبور",
  phone: "شماره تلفن",
  phoneCodeSubtitle: "کد شش‌رقمی ارسال‌شده را وارد کن.",
  phoneNumber: "شماره موبایل",
  phoneSubtitle: "شماره موبایلت را وارد کن تا کد ورود برایت ارسال شود.",
  phoneSubmitting: "در حال بررسی…",
  register: "ساخت حساب و ذخیره پاسخ‌ها",
  resend: "ارسال دوباره کد",
  resendCountdown: "ارسال دوباره تا",
  seconds: "ثانیه",
  securityBody: "پاسخ‌ها تا لحظه‌ی ساخت حساب در همین تب می‌مانند.",
  securityTitle: "مسیر امن انتقال اطلاعات",
  sendOtp: "ارسال کد ورود",
  soon: "به‌زودی",
  title: "حالا حسابت را بساز",
  verifyOtp: "تأیید و ذخیره پاسخ‌ها",
} as const;

function faNumber(value: number): string {
  return new Intl.NumberFormat("fa-IR").format(value);
}

export function PublicAccountStep({ onAuthenticated, onEdit }: PublicAccountStepProps) {
  const auth = useMobileAuth();
  const google = useGoogleSignIn();
  const [method, setMethod] = useState<AccountMethod>("email");
  const [accountMode, setAccountMode] = useState<AccountMode>("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [code, setCode] = useState("");
  const [phoneStep, setPhoneStep] = useState<PhoneStep>("request");
  const [countdown, setCountdown] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (countdown <= 0) return undefined;
    const timer = setInterval(() => setCountdown((current) => Math.max(0, current - 1)), 1_000);
    return () => clearInterval(timer);
  }, [countdown]);

  async function finish(authentication: Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await authentication;
      onAuthenticated();
    } catch (authenticationError) {
      setError(authErrorMessage(authenticationError, method === "phone" ? "otp" : "credentials"));
    } finally {
      setBusy(false);
    }
  }

  function submitEmail() {
    const emailError = validateEmail(email);
    if (emailError) {
      setError(emailError);
      return;
    }
    const passwordError = validatePassword(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }
    if (accountMode === "register" && password !== confirmation) {
      setError("تکرار رمز عبور با رمز عبور یکسان نیست.");
      return;
    }
    void finish(auth.user === null
      ? accountMode === "register"
        ? auth.register({ email: email.trim(), password })
        : auth.signInWithPassword({ email: email.trim(), password })
      : Promise.resolve());
  }

  function submitPhone() {
    const phoneError = validatePhoneNumber(phoneNumber);
    if (phoneError) {
      setError(phoneError);
      return;
    }
    const normalized = normalizePhoneNumber(phoneNumber);
    if (phoneStep === "request") {
      setBusy(true);
      setError(null);
      void auth.sendPhoneOtp(normalized)
        .then((result) => {
          setPhoneNumber(normalized);
          setPhoneStep("verify");
          setCountdown(result.retry_after_seconds);
        })
        .catch((requestError) => setError(authErrorMessage(requestError, "otp")))
        .finally(() => setBusy(false));
      return;
    }
    const otpError = validateOtpCode(code);
    if (otpError) {
      setError(otpError);
      return;
    }
    void finish(auth.user === null
      ? auth.verifyPhoneOtp(normalized, normalizePhoneNumber(code))
      : Promise.resolve());
  }

  function resendPhone() {
    if (countdown > 0 || busy) return;
    const normalized = normalizePhoneNumber(phoneNumber);
    setBusy(true);
    setError(null);
    void auth.sendPhoneOtp(normalized)
      .then((result) => setCountdown(result.retry_after_seconds))
      .catch((requestError) => setError(authErrorMessage(requestError, "otp")))
      .finally(() => setBusy(false));
  }

  function submitGoogle() {
    void finish(
      google.signIn().then((credential) => auth.signInWithGoogle(credential)),
    );
  }

  function selectMethod(nextMethod: AccountMethod) {
    setMethod(nextMethod);
    setError(null);
  }

  function changePhone() {
    setPhoneStep("request");
    setCode("");
    setCountdown(0);
    setError(null);
  }

  return (
    <View style={styles.account} testID="public-account-step">
      <View style={styles.accountTopline}>
        <View style={styles.accountHeader}>
          <Text style={styles.progressLabel}>{copy.lastStep}</Text>
          <Text accessibilityRole="header" style={styles.accountTitle}>{copy.title}</Text>
          <Text style={styles.accountIntro}>{copy.intro}</Text>
        </View>
        <Pressable accessibilityRole="button" onPress={onEdit}>
          <Text style={styles.textButton}>{copy.edit}</Text>
        </Pressable>
      </View>

      <View style={styles.accountSecurity}>
        <AppIcon color={fiticianTokens.colors.aqua} name="shield" size={28} />
        <View style={styles.accountSecurityCopy}>
          <Text style={styles.accountSecurityTitle}>{copy.securityTitle}</Text>
          <Text style={styles.accountSecurityBody}>{copy.securityBody}</Text>
        </View>
      </View>

      <View accessibilityRole="tablist" style={styles.accountMethods}>
        <Pressable
          accessibilityLabel={copy.emailMethod}
          accessibilityRole="tab"
          accessibilityState={{ selected: method === "email" }}
          onPress={() => selectMethod("email")}
          style={[styles.accountMethod, method === "email" && styles.accountMethodSelected]}
        >
          <Text style={[styles.accountMethodText, method === "email" && styles.accountMethodTextSelected]}>{copy.emailMethod}</Text>
        </Pressable>
        <Pressable
          accessibilityLabel={copy.phone}
          accessibilityRole="tab"
          accessibilityState={{ selected: method === "phone" }}
          onPress={() => selectMethod("phone")}
          style={[styles.accountMethod, method === "phone" && styles.accountMethodSelected]}
        >
          <Text style={[styles.accountMethodText, method === "phone" && styles.accountMethodTextSelected]}>{copy.phone}</Text>
        </Pressable>
      </View>

      <View accessibilityLabel="روش‌های ورود" style={styles.accountProviders}>
        <Button
          disabled={google.available && !google.ready}
          label={copy.google}
          loading={busy}
          onPress={submitGoogle}
          style={styles.providerButton}
          variant="secondary"
        />
        <Pressable
          accessibilityLabel={`${copy.apple} ${copy.soon}`}
          accessibilityRole="button"
          accessibilityState={{ disabled: true }}
          disabled
          style={styles.appleProvider}
        >
          <Text style={styles.appleProviderLabel}>{copy.apple}</Text>
          <Text style={styles.appleProviderHint}>{copy.soon}</Text>
        </Pressable>
      </View>

      <View style={styles.divider}>
        <View style={styles.dividerLine} />
        <Text style={styles.dividerText}>{copy.divider}</Text>
        <View style={styles.dividerLine} />
      </View>

      {method === "email" ? (
        <View style={styles.content}>
          <TextField
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
            label={copy.email}
            onChangeText={(value) => {
              setEmail(value);
              setError(null);
            }}
            textDirection="ltr"
            value={email}
          />
          <TextField
            autoCapitalize="none"
            autoComplete={accountMode === "register" ? "new-password" : "current-password"}
            label={copy.password}
            maxLength={128}
            onChangeText={(value) => {
              setPassword(value);
              setError(null);
            }}
            secureTextEntry
            textContentType={accountMode === "register" ? "newPassword" : "password"}
            value={password}
          />
          {accountMode === "register" ? (
            <TextField
              autoCapitalize="none"
              autoComplete="new-password"
              label={copy.confirmation}
              maxLength={128}
              onChangeText={(value) => {
                setConfirmation(value);
                setError(null);
              }}
              secureTextEntry
              textContentType="newPassword"
              value={confirmation}
            />
          ) : null}
          {error ? <Notice message={error} variant="danger" /> : null}
          <Button
            label={accountMode === "register" ? copy.register : copy.login}
            loading={busy || auth.busy}
            onPress={submitEmail}
          />
          <Pressable accessibilityRole="button" onPress={() => setAccountMode((current) => current === "register" ? "login" : "register")}>
            <Text style={styles.accountModeToggle}>{accountMode === "register" ? copy.accountModeLogin : copy.accountModeRegister}</Text>
          </Pressable>
        </View>
      ) : (
        <View style={styles.content}>
          <Text style={styles.questionDescription}>{phoneStep === "request" ? copy.phoneSubtitle : copy.phoneCodeSubtitle}</Text>
          <TextField
            autoComplete="tel"
            editable={phoneStep === "request"}
            keyboardType="phone-pad"
            label={copy.phoneNumber}
            onChangeText={(value) => {
              setPhoneNumber(value);
              setError(null);
            }}
            placeholder="۰۹۱۲۳۴۵۶۷۸۹"
            textDirection="ltr"
            value={phoneNumber}
          />
          {phoneStep === "verify" ? (
            <>
              <TextField
                autoComplete="one-time-code"
                keyboardType="number-pad"
                label={copy.otpCode}
                maxLength={6}
                onChangeText={(value) => {
                  setCode(value);
                  setError(null);
                }}
                textDirection="ltr"
                value={code}
              />
              <View style={styles.phoneActions}>
                <Pressable
                  accessibilityRole="button"
                  disabled={busy || countdown > 0}
                  onPress={resendPhone}
                >
                  <Text style={styles.textButton}>
                    {countdown > 0 ? `${copy.resendCountdown} ${faNumber(countdown)} ${copy.seconds}` : copy.resend}
                  </Text>
                </Pressable>
                <Pressable accessibilityRole="button" disabled={busy} onPress={changePhone}>
                  <Text style={styles.textButton}>{copy.changePhone}</Text>
                </Pressable>
              </View>
            </>
          ) : null}
          {error ? <Notice message={error} variant="danger" /> : null}
          <Button
            label={phoneStep === "request" ? copy.sendOtp : copy.verifyOtp}
            loading={busy || auth.busy}
            onPress={submitPhone}
          />
        </View>
      )}
    </View>
  );
}
