import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { authErrorMessage } from "../auth/authError";
import { useAuth } from "../auth/AuthContext";
import { NutritionOnboardingFlow } from "../nutrition/NutritionOnboardingFlow";
import { BodyGoalFields, ExperienceFields, PersonalFields } from "../profile/ProfileFormFields";
import { toProfileInput, validateStep, type ProfileValidationErrors } from "../profile/profileValidation";
import type { ProductMode, ProfileFormValues } from "../profile/types";
import { clearOnboardingDraft, hydrateOnboardingDraft, loadOnboardingDraft, saveOnboardingDraft, type OnboardingDraft } from "./onboardingDraft";
import "./publicOnboarding.css";

const emptyValues: ProfileFormValues = {
  display_name: "", birth_date: "", sex: "", height_cm: "", current_weight_kg: "",
  shoulder_circumference_cm: "", waist_circumference_cm: "", hip_circumference_cm: "",
  fitness_goal: "", experience_level: "", training_days_per_week: "",
  training_location: "", home_training_setup: "", session_duration_minutes: "",
  physical_limitations: "", training_cautions: null, plan_duration_weeks: "4",
};

type Language = "fa" | "en";

const publicCopy = {
  fa: {
    brand: "فیتشو", header: "اطلاعاتت تا زمان ساخت حساب فقط در همین تب نگه‌داری می‌شود.",
    mode: { eyebrow: "شروع با مربی فیتشو", title: "تو چه زمینه‌ای به کمک نیاز داری؟", training: "برنامه تمرینی", nutrition: "برنامه تغذیه", both: "تمرین و تغذیه", recommended: "پیشنهاد فیتشو" },
    training: { eyebrow: (step: number) => `مربی فیتشو · مرحله ${step} از ۳`, titles: ["اول کمی آشنا شویم", "بدن و هدفت", "سبک تمرین تو"], intro: "آرام و قدم‌به‌قدم جلو می‌رویم؛ سؤال‌های اختیاری را می‌توانی رد کنی.", skipMeasurements: "رد کردن اندازه‌گیری‌های اختیاری", skipNotes: "رد کردن توضیحات اختیاری", back: "بازگشت", next: "ادامه", finish: "ادامه و ساخت حساب" },
    account: { eyebrow: "آخرین قدم", title: "حالا حسابت را بساز", intro: "پاسخ‌ها بعد از ورود امن به حساب فیتشو منتقل می‌شوند.", providers: "روش‌های ورود", soon: "به‌زودی", phone: "شماره تلفن", divider: "ایمیل فعال است", email: "ایمیل", password: "رمز عبور", confirmation: "تکرار رمز عبور", registering: "در حال ثبت…", register: "ساخت حساب و ذخیره پاسخ‌ها", login: "ورود و ذخیره پاسخ‌ها", existing: "قبلاً حساب ساخته‌ام", newAccount: "حساب جدید می‌سازم", mismatch: "تکرار رمز عبور با رمز عبور یکسان نیست." },
  },
  en: {
    brand: "Fitsho", header: "Your answers stay in this tab until you create an account.",
    mode: { eyebrow: "Start with your Fitsho coach", title: "What would you like help with?", training: "Training plan", nutrition: "Nutrition plan", both: "Training and nutrition", recommended: "Fitsho recommended" },
    training: { eyebrow: (step: number) => `Your Fitsho coach · Step ${step} of 3`, titles: ["Let’s get to know each other", "Your body and goal", "Your training style"], intro: "We’ll take this step by step. You can skip optional questions.", skipMeasurements: "Skip optional measurements", skipNotes: "Skip optional notes", back: "Back", next: "Continue", finish: "Continue to account setup" },
    account: { eyebrow: "Final step", title: "Create your account", intro: "Your answers will move securely into your Fitsho account after you sign in.", providers: "Sign-in methods", soon: "Coming soon", phone: "Phone number", divider: "Email is available", email: "Email", password: "Password", confirmation: "Confirm password", registering: "Creating account…", register: "Create account and save answers", login: "Sign in and save answers", existing: "I already have an account", newAccount: "Create a new account", mismatch: "Passwords do not match." },
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

  if (draft?.readyForAuth) return <FinalAccountStep draft={draft} language={language} />;

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
            language={language}
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
    ["training", text.training],
    ["nutrition", text.nutrition],
    ["both", text.both],
  ] as const;
  return (
    <section className="public-mode-selection">
      <p className="eyebrow eyebrow--accent">{text.eyebrow}</p>
      <h1 className="fitsho-display">{text.title}</h1>
      <div className="product-mode-cards">
        {modes.map(([mode, title]) => (
          <button
            key={mode}
            className={`product-mode-card mode-${mode} ${mode === "both" ? "is-recommended" : ""}`}
            type="button"
            aria-label={title}
            onClick={() => onChoose(mode)}
          >
            {mode === "both" && <span>{text.recommended}</span>}
            <strong>{title}</strong>
          </button>
        ))}
      </div>
    </section>
  );
}

function TrainingDraftFlow({ language, onExit, onComplete }: { language: Language; onExit: () => void; onComplete: (input: ReturnType<typeof toProfileInput>) => void }) {
  const text = publicCopy[language].training;
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [values, setValues] = useState(emptyValues);
  const [errors, setErrors] = useState<ProfileValidationErrors>({});

  useEffect(() => {
    const first = Object.keys(errors)[0];
    if (first) document.querySelector<HTMLElement>(`[name="${first}"]`)?.focus();
  }, [errors]);

  function update(field: keyof ProfileFormValues, value: string | ProfileFormValues["training_cautions"]) {
    setValues((current) => ({ ...current, [field]: value, ...(field === "training_location" && value === "gym" ? { home_training_setup: "" } : {}) }));
    setErrors((current) => { const next = { ...current }; delete next[field]; return next; });
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const nextErrors = validateStep(values, step, new Date());
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    if (step < 3) setStep((step + 1) as 2 | 3);
    else onComplete(toProfileInput(values));
  }

  return (
    <section className="public-question-card">
      <p className="eyebrow eyebrow--accent">{text.eyebrow(step)}</p>
      <h1 className="fitsho-display">{text.titles[step - 1]}</h1>
      <p>{text.intro}</p>
      <form className="profile-form" noValidate onSubmit={submit}>
        {step === 1 && <PersonalFields values={values} errors={errors} onChange={update} />}
        {step === 2 && <><BodyGoalFields values={values} errors={errors} onChange={update} /><button className="text-button" type="button" onClick={() => { update("shoulder_circumference_cm", ""); update("waist_circumference_cm", ""); update("hip_circumference_cm", ""); }}>{text.skipMeasurements}</button></>}
        {step === 3 && <><ExperienceFields values={values} errors={errors} onChange={update} /><button className="text-button" type="button" onClick={() => update("physical_limitations", "")}>{text.skipNotes}</button></>}
        <div className="profile-actions">
          <button className="secondary-button" type="button" onClick={() => step === 1 ? onExit() : setStep((step - 1) as 1 | 2)}>{text.back}</button>
          <button className="primary-button" type="submit">{step === 3 ? text.finish : text.next}</button>
        </div>
      </form>
    </section>
  );
}

function FinalAccountStep({ draft, language }: { draft: OnboardingDraft; language: Language }) {
  const { t } = useTranslation();
  const text = publicCopy[language].account;
  const { user, register, login } = useAuth();
  const navigate = useNavigate();
  const [accountMode, setAccountMode] = useState<"register" | "login">("register");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const credentials = { email: String(data.get("email") ?? ""), password: String(data.get("password") ?? "") };
    if (accountMode === "register" && credentials.password !== String(data.get("confirmation") ?? "")) {
      setError(text.mismatch);
      return;
    }
    setBusy(true);
    setError(null);
    const authenticate = user !== null
      ? Promise.resolve()
      : (accountMode === "register" ? register(credentials) : login(credentials));
    void authenticate
      .then(() => hydrateOnboardingDraft(draft))
      .then(() => navigate("/onboarding", { replace: true }))
      .catch((reason: unknown) => setError(authErrorMessage(reason, t)))
      .finally(() => setBusy(false));
  }

  return (
    <main className="public-onboarding public-account-step" dir={language === "fa" ? "rtl" : "ltr"}>
      <section className="public-question-card">
        <p className="eyebrow eyebrow--accent">{text.eyebrow}</p>
        <h1 className="fitsho-display">{text.title}</h1>
        <p>{text.intro}</p>
        <div className="account-providers" aria-label={text.providers}>
          <button type="button" disabled>Google <small>{text.soon}</small></button>
          <button type="button" disabled>Apple <small>{text.soon}</small></button>
          <button type="button" disabled>{text.phone} <small>{text.soon}</small></button>
        </div>
        <div className="account-divider"><span>{text.divider}</span></div>
        <form className="auth-form" onSubmit={submit}>
          <label htmlFor="public-account-email">{text.email}</label>
          <input id="public-account-email" name="email" type="email" autoComplete="email" required />
          <label htmlFor="public-account-password">{text.password}</label>
          <input id="public-account-password" name="password" type="password" minLength={8} maxLength={128} autoComplete={accountMode === "register" ? "new-password" : "current-password"} required />
          {accountMode === "register" && <><label htmlFor="public-account-confirmation">{text.confirmation}</label><input id="public-account-confirmation" name="confirmation" type="password" minLength={8} maxLength={128} autoComplete="new-password" required /></>}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" type="submit" disabled={busy}>{busy ? text.registering : accountMode === "register" ? text.register : text.login}</button>
        </form>
        <button className="text-button" type="button" onClick={() => setAccountMode((mode) => mode === "register" ? "login" : "register")}>{accountMode === "register" ? text.existing : text.newAccount}</button>
      </section>
    </main>
  );
}
