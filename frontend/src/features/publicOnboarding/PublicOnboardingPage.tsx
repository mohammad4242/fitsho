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

export function PublicOnboardingPage() {
  const [draft, setDraft] = useState<OnboardingDraft | null>(() => loadOnboardingDraft());

  function updateDraft(next: OnboardingDraft | null) {
    setDraft(next);
    if (next === null) clearOnboardingDraft();
    else saveOnboardingDraft(next);
  }

  if (draft?.readyForAuth) return <FinalAccountStep draft={draft} />;

  return (
    <main className="public-onboarding">
      <header className="public-onboarding__header">
        <Link className="brand-mark" to="/"><span className="brand-mark__pulse" aria-hidden="true" />فیتشو</Link>
        <span>اطلاعاتت تا زمان ساخت حساب فقط در همین تب نگه‌داری می‌شود.</span>
      </header>
      <div className="public-onboarding__stage">
        {draft === null && <ModeSelection onChoose={(mode) => updateDraft({ mode })} />}
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

function ModeSelection({ onChoose }: { onChoose: (mode: ProductMode) => void }) {
  const modes = [
    ["training", "تمرین", "برنامه ورزشی براساس بدن، هدف، زمان و تجهیزات"],
    ["nutrition", "تغذیه", "اطلاعات ضروری برای یک مسیر غذایی متناسب و ایمن"],
    ["both", "تمرین و تغذیه", "دو مسیر هماهنگ برای نتیجه‌ای یکپارچه"],
  ] as const;
  return (
    <section className="public-mode-selection">
      <p className="eyebrow eyebrow--accent">شروع با مربی فیتشو</p>
      <h1 className="fitsho-display">تو چه زمینه‌ای به کمک نیاز داری؟</h1>
      <p>یکی را انتخاب کن؛ فقط سؤال‌های مرتبط با همان مسیر را از تو می‌پرسیم.</p>
      <div className="product-mode-cards">
        {modes.map(([mode, title, description]) => (
          <button
            key={mode}
            className={`product-mode-card ${mode === "both" ? "is-recommended" : ""}`}
            type="button"
            aria-label={title}
            onClick={() => onChoose(mode)}
          >
            {mode === "both" && <span>پیشنهاد فیتشو</span>}
            <strong>{title}</strong><small>{description}</small>
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
      <p className="eyebrow eyebrow--accent">مربی فیتشو · مرحله {step} از ۳</p>
      <h1 className="fitsho-display">{["اول کمی آشنا شویم", "بدن و هدفت", "سبک تمرین تو"][step - 1]}</h1>
      <p>آرام و قدم‌به‌قدم جلو می‌رویم؛ سؤال‌های اختیاری را می‌توانی رد کنی.</p>
      <form className="profile-form" noValidate onSubmit={submit}>
        {step === 1 && <PersonalFields values={values} errors={errors} onChange={update} />}
        {step === 2 && <><BodyGoalFields values={values} errors={errors} onChange={update} /><button className="text-button" type="button" onClick={() => { update("shoulder_circumference_cm", ""); update("waist_circumference_cm", ""); update("hip_circumference_cm", ""); }}>رد کردن اندازه‌گیری‌های اختیاری</button></>}
        {step === 3 && <><ExperienceFields values={values} errors={errors} onChange={update} /><button className="text-button" type="button" onClick={() => update("physical_limitations", "")}>رد کردن توضیحات اختیاری</button></>}
        <div className="profile-actions">
          <button className="secondary-button" type="button" onClick={() => step === 1 ? onExit() : setStep((step - 1) as 1 | 2)}>بازگشت</button>
          <button className="primary-button" type="submit">{step === 3 ? "ادامه و ساخت حساب" : "ادامه"}</button>
        </div>
      </form>
    </section>
  );
}

function FinalAccountStep({ draft }: { draft: OnboardingDraft }) {
  const { t } = useTranslation();
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
      setError("تکرار رمز عبور با رمز عبور یکسان نیست.");
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
    <main className="public-onboarding public-account-step">
      <section className="public-question-card">
        <p className="eyebrow eyebrow--accent">آخرین قدم</p>
        <h1 className="fitsho-display">حالا حسابت را بساز</h1>
        <p>پاسخ‌ها بعد از ورود امن به حساب فیتشو منتقل می‌شوند.</p>
        <div className="account-providers" aria-label="روش‌های ورود">
          <button type="button" disabled>Google <small>به‌زودی</small></button>
          <button type="button" disabled>Apple <small>به‌زودی</small></button>
          <button type="button" disabled>شماره تلفن <small>به‌زودی</small></button>
        </div>
        <div className="account-divider"><span>ایمیل فعال است</span></div>
        <form className="auth-form" onSubmit={submit}>
          <label htmlFor="public-account-email">ایمیل</label>
          <input id="public-account-email" name="email" type="email" autoComplete="email" required />
          <label htmlFor="public-account-password">رمز عبور</label>
          <input id="public-account-password" name="password" type="password" minLength={8} maxLength={128} autoComplete={accountMode === "register" ? "new-password" : "current-password"} required />
          {accountMode === "register" && <><label htmlFor="public-account-confirmation">تکرار رمز عبور</label><input id="public-account-confirmation" name="confirmation" type="password" minLength={8} maxLength={128} autoComplete="new-password" required /></>}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" type="submit" disabled={busy}>{busy ? "در حال ثبت…" : accountMode === "register" ? "ساخت حساب و ذخیره پاسخ‌ها" : "ورود و ذخیره پاسخ‌ها"}</button>
        </form>
        <button className="text-button" type="button" onClick={() => setAccountMode((mode) => mode === "register" ? "login" : "register")}>{accountMode === "register" ? "قبلاً حساب ساخته‌ام" : "حساب جدید می‌سازم"}</button>
      </section>
    </main>
  );
}
