import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { AppIcon } from "../../shared/AppIcon";
import * as authApi from "../auth/api";
import { authErrorMessage } from "../auth/authError";
import { useAuth } from "../auth/AuthContext";
import { GoogleSignInButton } from "../auth/GoogleSignInButton";
import { NutritionOnboardingFlow } from "../nutrition/NutritionOnboardingFlow";
import { toProfileInput, validateStep, type ProfileValidationErrors } from "../profile/profileValidation";
import type { ProductMode, ProfileFormValue, ProfileFormValues } from "../profile/types";
import { clearOnboardingDraft, hydrateOnboardingDraft, loadOnboardingDraft, saveOnboardingDraft, type OnboardingDraft } from "./onboardingDraft";
import { GuidedSharedProfileQuestions } from "./GuidedSharedProfileQuestions";
import { GuidedTrainingQuestions } from "./GuidedTrainingQuestions";
import "./publicOnboarding.css";

const emptyValues: ProfileFormValues = {
  display_name: "", birth_date: "", sex: "", height_cm: "", current_weight_kg: "",
  shoulder_circumference_cm: "", waist_circumference_cm: "", hip_circumference_cm: "",
  fitness_goal: "", experience_level: "", training_days_per_week: "",
  training_age_months: "",
  preferred_weekdays: [], priority_muscle: "",
  training_location: "", home_training_setup: "", session_duration_minutes: "",
  training_intensity: "",
  training_cautions: null, plan_duration_weeks: "4",
};

type Language = "fa" | "en";
type AccountMethod = "email" | "phone";
type PhoneStep = "request" | "verify";

const publicCopy = {
  fa: {
    brand: "فیتشو", header: "اطلاعاتت تا زمان ساخت حساب فقط در همین تب نگه‌داری می‌شود.",
    mode: { eyebrow: "شروع با مربی فیتشو", title: "تو چه زمینه‌ای به کمک نیاز داری؟", training: "برنامه تمرینی", nutrition: "برنامه تغذیه", both: "تمرین و تغذیه", recommended: "پیشنهاد فیتشو" },
    account: {
      eyebrow: "آخرین قدم",
      title: "حالا حسابت را بساز",
      intro: "پاسخ‌ها بعد از ورود امن به حساب فیتشو منتقل می‌شوند.",
      edit: "بازگشت و ویرایش پاسخ‌ها",
      providers: "روش‌های ورود",
      securityTitle: "مسیر امن انتقال اطلاعات",
      securityBody: "پاسخ‌ها تا لحظه‌ی ساخت حساب در همین تب می‌مانند.",
      emailMethod: "ایمیل",
      soon: "به‌زودی",
      google: "Google",
      apple: "Apple",
      phone: "شماره تلفن",
      phoneNumber: "شماره موبایل",
      phoneSubtitle: "شماره موبایلت را وارد کن تا کد ورود برایت ارسال شود.",
      phoneCodeSubtitle: "کد شش‌رقمی ارسال‌شده را وارد کن.",
      otpCode: "کد ورود",
      divider: "یا با ایمیل ادامه بده",
      email: "ایمیل",
      password: "رمز عبور",
      confirmation: "تکرار رمز عبور",
      registering: "در حال ثبت…",
      register: "ساخت حساب و ذخیره پاسخ‌ها",
      login: "ورود و ذخیره پاسخ‌ها",
      sendOtp: "ارسال کد ورود",
      verifyOtp: "تأیید و ذخیره پاسخ‌ها",
      phoneSubmitting: "در حال بررسی…",
      resend: "ارسال دوباره کد",
      resendCountdown: "ارسال دوباره تا",
      seconds: "ثانیه",
      changePhone: "تغییر شماره",
      existing: "قبلاً حساب ساخته‌ام",
      newAccount: "حساب جدید می‌سازم",
      mismatch: "تکرار رمز عبور با رمز عبور یکسان نیست.",
    },
  },
  en: {
    brand: "Fitsho", header: "Your answers stay in this tab until you create an account.",
    mode: { eyebrow: "Start with your Fitsho coach", title: "What would you like help with?", training: "Training plan", nutrition: "Nutrition plan", both: "Training and nutrition", recommended: "Fitsho recommended" },
    account: {
      eyebrow: "Final step",
      title: "Create your account",
      intro: "Your answers will move securely into your Fitsho account after you sign in.",
      edit: "Back to edit answers",
      providers: "Sign-in methods",
      securityTitle: "Secure answer handoff",
      securityBody: "Your answers stay in this tab until your account is created.",
      emailMethod: "Email",
      soon: "Coming soon",
      google: "Google",
      apple: "Apple",
      phone: "Phone number",
      phoneNumber: "Mobile number",
      phoneSubtitle: "Enter your mobile number and we will send your login code.",
      phoneCodeSubtitle: "Enter the six-digit code we sent you.",
      otpCode: "Login code",
      divider: "or continue with email",
      email: "Email",
      password: "Password",
      confirmation: "Confirm password",
      registering: "Creating account…",
      register: "Create account and save answers",
      login: "Sign in and save answers",
      sendOtp: "Send login code",
      verifyOtp: "Verify and save answers",
      phoneSubmitting: "Checking…",
      resend: "Resend code",
      resendCountdown: "Resend in",
      seconds: "seconds",
      changePhone: "Change number",
      existing: "I already have an account",
      newAccount: "Create a new account",
      mismatch: "Passwords do not match.",
    },
  },
} as const;

export function PublicOnboardingPage() {
  const { i18n } = useTranslation();
  const language: Language = i18n.resolvedLanguage === "en" ? "en" : "fa";
  const text = publicCopy[language];
  const [draft, setDraft] = useState<OnboardingDraft | null>(() => loadOnboardingDraft());

  function updateDraft(next: OnboardingDraft | null) {
    setDraft(next);
    if (next === null) clearOnboardingDraft();
    else saveOnboardingDraft(next);
  }

  if (draft?.readyForAuth) return <FinalAccountStep draft={draft} language={language} onEdit={() => updateDraft({ ...draft, readyForAuth: false })} />;

  return (
    <main className="public-onboarding" dir={language === "fa" ? "rtl" : "ltr"}>
      <header className="public-onboarding__header">
        <Link className="brand-mark" to="/"><span className="brand-mark__pulse" aria-hidden="true" />{text.brand}</Link>
        <span>{text.header}</span>
      </header>
      <div className="public-onboarding__stage">
        {draft === null && <ModeSelection language={language} onChoose={(mode) => updateDraft({ mode })} />}
        {draft?.mode === "training" && (
          <TrainingDraftFlow
            onExit={() => updateDraft(null)}
            onComplete={(training) => updateDraft({ ...draft, training, readyForAuth: true })}
          />
        )}
        {(draft?.mode === "nutrition" || draft?.mode === "both") && (
          <NutritionOnboardingFlow
            productMode={draft.mode}
            draftMode
            initialDraft={draft}
            onDraftChange={(changes) => updateDraft({ ...draft, ...changes })}
            onExit={() => updateDraft(null)}
            onDraftComplete={(changes) => updateDraft({ ...draft, ...changes, readyForAuth: true })}
            onCreateTrainingProfile={async () => { throw new Error("Draft mode does not persist profiles"); }}
            onComplete={() => undefined}
          />
        )}
      </div>
    </main>
  );
}

function ModeSelection({ language, onChoose }: { language: Language; onChoose: (mode: ProductMode) => void }) {
  const text = publicCopy[language].mode;
  const modes = [
    ["training", text.training, "dumbbell"],
    ["nutrition", text.nutrition, "nutrition"],
    ["both", text.both, "target"],
  ] as const;
  return (
    <section className="public-mode-selection">
      <p className="eyebrow eyebrow--accent">{text.eyebrow}</p>
      <h1 className="fitsho-display">{text.title}</h1>
      <div className="product-mode-cards">
        {modes.map(([mode, title, icon]) => (
          <button
            key={mode}
            className={`product-mode-card mode-${mode} ${mode === "both" ? "is-recommended" : ""}`}
            type="button"
            aria-label={title}
            onClick={() => onChoose(mode)}
          >
            <span className="product-mode-card__icon" aria-hidden="true"><AppIcon name={icon} /></span>
            <span className="product-mode-card__content">
              <strong>{title}</strong>
              {mode === "both" && <span className="product-mode-card__badge">{text.recommended}</span>}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}

function TrainingDraftFlow({ onExit, onComplete }: { onExit: () => void; onComplete: (input: ReturnType<typeof toProfileInput>) => void }) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [values, setValues] = useState(emptyValues);
  const [errors, setErrors] = useState<ProfileValidationErrors>({});

  useEffect(() => {
    const first = Object.keys(errors)[0];
    if (first) document.querySelector<HTMLElement>(`[name="${first}"]`)?.focus();
  }, [errors]);

  function update(field: keyof ProfileFormValues, value: ProfileFormValue) {
    setValues((current) => ({ ...current, [field]: value, ...(field === "training_location" && value === "gym" ? { home_training_setup: "" } : {}) }));
    setErrors((current) => { const next = { ...current }; delete next[field]; return next; });
  }

  function completeTrainingQuestions() {
    const nextErrors = validateStep(values, 3, new Date());
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    onComplete(toProfileInput(values));
  }

  function completeSharedQuestions() {
    const nextErrors = { ...validateStep(values, 1, new Date()), ...validateStep(values, 2, new Date()) };
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length === 0) setStep(3);
  }

  if (step === 1) {
    return <section className="public-question-card public-question-card--fullscreen"><GuidedSharedProfileQuestions values={values} onChange={(field, value) => update(field, value)} onBack={onExit} onComplete={completeSharedQuestions} /></section>;
  }

  return <section className="public-question-card public-question-card--fullscreen"><GuidedTrainingQuestions values={values} onChange={update} onBack={() => setStep(1)} onComplete={completeTrainingQuestions} /></section>;
}

function FinalAccountStep({ draft, language, onEdit }: { draft: OnboardingDraft; language: Language; onEdit: () => void }) {
  const { t } = useTranslation();
  const text = publicCopy[language].account;
  const { user, register, login, loginWithPhone, loginWithGoogle } = useAuth();
  const navigate = useNavigate();
  const [method, setMethod] = useState<AccountMethod>("email");
  const [accountMode, setAccountMode] = useState<"register" | "login">("register");
  const [phoneStep, setPhoneStep] = useState<PhoneStep>("request");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [countdown, setCountdown] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const googleConfigured = Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim());

  useEffect(() => {
    if (countdown <= 0) return;
    const timer = window.setInterval(() => {
      setCountdown((seconds) => Math.max(0, seconds - 1));
    }, 1_000);
    return () => window.clearInterval(timer);
  }, [countdown]);

  function selectMethod(nextMethod: AccountMethod) {
    setMethod(nextMethod);
    setError(null);
  }

  function finishAuthentication(authentication: Promise<void>) {
    setBusy(true);
    setError(null);
    void authentication
      .then(() => hydrateOnboardingDraft(draft))
      .then(() => navigate(draft.mode === "training" ? "/dashboard" : "/onboarding", { replace: true }))
      .catch((reason: unknown) => setError(authErrorMessage(reason, t)))
      .finally(() => setBusy(false));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const credentials = { email: String(data.get("email") ?? ""), password: String(data.get("password") ?? "") };
    if (accountMode === "register" && credentials.password !== String(data.get("confirmation") ?? "")) {
      setError(text.mismatch);
      return;
    }
    const authenticate = user !== null
      ? Promise.resolve()
      : (accountMode === "register" ? register(credentials) : login(credentials));
    finishAuthentication(authenticate);
  }

  function sendOtp(number: string) {
    setBusy(true);
    setError(null);
    void authApi
      .sendPhoneOtp(number)
      .then((result) => {
        setPhoneNumber(number);
        setPhoneStep("verify");
        setCountdown(result.retry_after_seconds);
      })
      .catch((reason: unknown) => setError(authErrorMessage(reason, t)))
      .finally(() => setBusy(false));
  }

  function submitPhone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const number = phoneNumber || String(data.get("phone_number") ?? "");
    if (phoneStep === "request") {
      sendOtp(number);
      return;
    }
    const code = String(data.get("code") ?? "");
    const authenticate = user !== null ? Promise.resolve() : loginWithPhone(number, code);
    finishAuthentication(authenticate);
  }

  function handleGoogleCredential(credential: string) {
    const authenticate = user !== null ? Promise.resolve() : loginWithGoogle(credential);
    finishAuthentication(authenticate);
  }

  function handleGoogleError() {
    setError(t("errors.generic"));
  }

  function changePhone() {
    setPhoneStep("request");
    setCountdown(0);
    setError(null);
  }

  return (
    <main className="public-onboarding public-account-step" dir={language === "fa" ? "rtl" : "ltr"}>
      <section className="public-account-step__card">
        <div className="public-account-step__header">
          <div>
            <p className="eyebrow eyebrow--accent">{text.eyebrow}</p>
            <h1 className="fitsho-display">{text.title}</h1>
            <p>{text.intro}</p>
          </div>
          <button className="text-button" type="button" onClick={onEdit}>{text.edit}</button>
        </div>

        <div className="account-security-note">
          <span className="account-security-note__icon"><AppIcon name="shield" /></span>
          <span>
            <strong>{text.securityTitle}</strong>
            <small>{text.securityBody}</small>
          </span>
        </div>

        <div className="account-methods" role="tablist" aria-label={text.providers}>
          <button
            id="public-account-email-tab"
            type="button"
            role="tab"
            aria-controls="public-account-email-panel"
            aria-selected={method === "email"}
            onClick={() => selectMethod("email")}
          >
            {text.emailMethod}
          </button>
          <button
            id="public-account-phone-tab"
            type="button"
            role="tab"
            aria-controls="public-account-phone-panel"
            aria-selected={method === "phone"}
            onClick={() => selectMethod("phone")}
          >
            {text.phone}
          </button>
        </div>

        <div className="account-provider-grid" aria-label={text.providers}>
          {googleConfigured && (
            <div className="account-provider account-provider--google">
              <span className="account-provider__identity">
                <span className="account-provider__mark" aria-hidden="true">G</span>
                <span>{text.google}</span>
              </span>
              <GoogleSignInButton
                onCredential={handleGoogleCredential}
                onError={handleGoogleError}
                disabled={busy}
              />
            </div>
          )}
          <button
            className="account-provider account-provider--future"
            type="button"
            aria-label={`${text.apple} ${text.soon}`}
            disabled
          >
            <span>{text.apple}</span>
            <small>{text.soon}</small>
          </button>
        </div>
        <div className="account-divider"><span>{text.divider}</span></div>
        {method === "email" ? (
          <form id="public-account-email-panel" className="auth-form account-auth-form" role="tabpanel" aria-labelledby="public-account-email-tab" onSubmit={submit}>
            <label htmlFor="public-account-email">{text.email}</label>
            <input id="public-account-email" name="email" type="email" autoComplete="email" required />
            <label htmlFor="public-account-password">{text.password}</label>
            <input id="public-account-password" name="password" type="password" minLength={8} maxLength={128} autoComplete={accountMode === "register" ? "new-password" : "current-password"} required />
            {accountMode === "register" && <><label htmlFor="public-account-confirmation">{text.confirmation}</label><input id="public-account-confirmation" name="confirmation" type="password" minLength={8} maxLength={128} autoComplete="new-password" required /></>}
            {error && <p className="form-error" role="alert" aria-live="polite">{error}</p>}
            <button className="primary-button" type="submit" disabled={busy}>{busy ? text.registering : accountMode === "register" ? text.register : text.login}</button>
          </form>
        ) : (
          <form id="public-account-phone-panel" className="auth-form account-auth-form" role="tabpanel" aria-labelledby="public-account-phone-tab" onSubmit={submitPhone}>
            <p className="account-form-hint">{phoneStep === "request" ? text.phoneSubtitle : text.phoneCodeSubtitle}</p>
            <label htmlFor="public-account-phone">{text.phoneNumber}</label>
            <input
              id="public-account-phone"
              name="phone_number"
              type="tel"
              autoComplete="tel"
              inputMode="tel"
              dir="ltr"
              value={phoneNumber}
              onChange={(event) => setPhoneNumber(event.target.value)}
              disabled={phoneStep === "verify"}
              required
            />
            {phoneStep === "verify" && (
              <>
                <label htmlFor="public-account-otp">{text.otpCode}</label>
                <input
                  id="public-account-otp"
                  name="code"
                  type="text"
                  autoComplete="one-time-code"
                  inputMode="numeric"
                  pattern="[0-9]{6}"
                  minLength={6}
                  maxLength={6}
                  dir="ltr"
                  required
                />
                <div className="account-phone-actions">
                  <button
                    className="auth-resend"
                    type="button"
                    disabled={busy || countdown > 0}
                    onClick={() => sendOtp(phoneNumber)}
                  >
                    {countdown > 0
                      ? `${text.resendCountdown} ${countdown.toLocaleString(language === "fa" ? "fa-IR" : "en-US")} ${text.seconds}`
                      : text.resend}
                  </button>
                  <button className="text-button" type="button" onClick={changePhone} disabled={busy}>{text.changePhone}</button>
                </div>
              </>
            )}
            {error && <p className="form-error" role="alert" aria-live="polite">{error}</p>}
            <button className="primary-button" type="submit" disabled={busy}>
              {busy ? text.phoneSubmitting : phoneStep === "request" ? text.sendOtp : text.verifyOtp}
            </button>
          </form>
        )}
        <button className="text-button" type="button" onClick={() => setAccountMode((mode) => mode === "register" ? "login" : "register")}>{accountMode === "register" ? text.existing : text.newAccount}</button>
      </section>
    </main>
  );
}
