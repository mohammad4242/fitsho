import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import type { ProfileFormValues } from "../profile/types";

type Props = {
  values: ProfileFormValues;
  onChange: (field: keyof ProfileFormValues, value: string) => void;
  onBack: () => void;
  onComplete: () => void;
};

const sexes = ["female", "male"] as const;
const goals = [
  ["lose_weight", "🔻⬆️"],
  ["gain_weight", "🔺️⬇️"],
  ["fat_loss", "🔥"],
  ["build_muscle", "💪"],
  ["body_recomposition", "🔥💪"],
] as const;

export function GuidedSharedProfileQuestions({ values, onChange, onBack, onComplete }: Props) {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage === "en" ? "en" : "fa";
  const [question, setQuestion] = useState(0);
  const [showBodyConfirmation, setShowBodyConfirmation] = useState(false);
  const [bodyValuesConfirmed, setBodyValuesConfirmed] = useState(false);
  const [birthParts, setBirthParts] = useState(() => {
    const [year = "", month = "", day = ""] = values.birth_date.split("-");
    return { year, month, day };
  });
  const labels = language === "en"
    ? ["What should we call you?", "When were you born?", "What is your sex?", "What are your height and weight?", "What is your main goal?"]
    : ["دوست داری چه صدایت کنیم؟", "چه تاریخی به دنیا آمدی؟", "جنسیتت چیست؟", "قد و وزنت چقدر است؟", "هدف اصلی تو چیست؟"];
  const years = useMemo(() => Array.from({ length: 83 }, (_, index) => String(new Date().getFullYear() - 18 - index)), []);
  const daysInSelectedMonth = birthParts.year && birthParts.month
    ? new Date(Number(birthParts.year), Number(birthParts.month), 0).getDate()
    : 31;
  const next = language === "en" ? "Continue" : "ادامه";
  const back = language === "en" ? "Back" : "بازگشت";
  const activeStage = question <= 2 ? 0 : question === 3 ? 1 : 2;
  const stages = language === "en" ? ["Personal", "Body", "Goal"] : ["شخصی", "بدن", "هدف"];
  const ready = [
    values.display_name.trim().length >= 2,
    Boolean(birthParts.year && birthParts.month && birthParts.day),
    values.sex !== "",
    Number(values.height_cm) >= 120 && Number(values.height_cm) <= 230
      && Number(values.current_weight_kg) >= 35 && Number(values.current_weight_kg) <= 300,
    values.fitness_goal !== "",
  ][question];
  const needsBodyConfirmation = Number(values.height_cm) < 140 || Number(values.height_cm) > 210
    || Number(values.current_weight_kg) < 40 || Number(values.current_weight_kg) > 180;

  useEffect(() => {
    if (Number(birthParts.day) > daysInSelectedMonth) {
      setBirthParts((current) => ({ ...current, day: "" }));
    }
  }, [birthParts.day, daysInSelectedMonth]);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (question === 1) {
      if (!birthParts.year || !birthParts.month || !birthParts.day) return;
      onChange("birth_date", `${birthParts.year}-${birthParts.month.padStart(2, "0")}-${birthParts.day.padStart(2, "0")}`);
    }
    if (question === 3 && needsBodyConfirmation && !bodyValuesConfirmed) {
      setShowBodyConfirmation(true);
      return;
    }
    if (question === labels.length - 1) onComplete();
    else setQuestion((current) => current + 1);
  }

  function updateBodyValue(field: "height_cm" | "current_weight_kg", value: string) {
    setShowBodyConfirmation(false);
    setBodyValuesConfirmed(false);
    onChange(field, value);
  }

  return (
    <section className="guided-question" aria-labelledby="guided-question-title">
      <ol className="guided-stage-track" aria-label={language === "en" ? "Profile sections" : "بخش‌های پروفایل"}>{stages.map((stage, index) => <li className={index < activeStage ? "is-complete" : index === activeStage ? "is-active" : ""} key={stage}><span aria-hidden="true">{index < activeStage ? "✓" : index + 1}</span>{stage}</li>)}</ol>
      <div className="public-onboarding-progress" aria-label={language === "en" ? "Personal details progress" : "پیشرفت اطلاعات شخصی"}>
        <span>{language === "en" ? `Step ${question + 1} of ${labels.length}` : `مرحله ${question + 1} از ${labels.length}`}</span>
        <progress value={question + 1} max={labels.length} />
      </div>
      <h1 className="fitsho-display" id="guided-question-title">{labels[question]}</h1>
      <form className="guided-question__form" onSubmit={submit}>
        {question === 0 && <label>{t("onboarding.fields.displayName")}<input name="display_name" autoFocus required minLength={2} maxLength={80} value={values.display_name} onChange={(event) => onChange("display_name", event.target.value)} /></label>}
        {question === 1 && <fieldset className="birth-date-picker"><legend>{t("onboarding.fields.birthDate")}</legend>
          <label>{language === "en" ? "Day" : "روز"}<select className="birth-date-picker__select" required value={birthParts.day} onChange={(event) => setBirthParts((current) => ({ ...current, day: event.target.value }))}><option value="" />{Array.from({ length: daysInSelectedMonth }, (_, index) => <option key={index + 1} value={index + 1}>{index + 1}</option>)}</select></label>
          <label>{language === "en" ? "Month" : "ماه"}<select className="birth-date-picker__select" required value={birthParts.month} onChange={(event) => setBirthParts((current) => ({ ...current, month: event.target.value }))}><option value="" />{Array.from({ length: 12 }, (_, index) => <option key={index + 1} value={index + 1}>{index + 1}</option>)}</select></label>
          <label>{language === "en" ? "Year" : "سال"}<select className="birth-date-picker__select" required value={birthParts.year} onChange={(event) => setBirthParts((current) => ({ ...current, year: event.target.value }))}><option value="" />{years.map((year) => <option key={year} value={year}>{year}</option>)}</select></label>
        </fieldset>}
        {question === 2 && <div className="guided-choice-grid guided-choice-grid--sex">{sexes.map((sex) => <button className={values.sex === sex ? "is-selected" : ""} key={sex} type="button" onClick={() => onChange("sex", sex)}>{t(`onboarding.options.sex.${sex}`)}</button>)}</div>}
        {question === 3 && <div className="guided-body-fields">
          <label>{t("onboarding.fields.height")}<input aria-label={t("onboarding.fields.height")} name="height_cm" type="number" inputMode="numeric" required min={120} max={230} value={values.height_cm} onChange={(event) => updateBodyValue("height_cm", event.target.value)} /><small>{language === "en" ? "120–230 cm" : "۱۲۰ تا ۲۳۰ سانتی‌متر"}</small></label>
          <label>{t("onboarding.fields.weight")}<input aria-label={t("onboarding.fields.weight")} name="current_weight_kg" type="number" inputMode="decimal" required min={35} max={300} step="0.01" value={values.current_weight_kg} onChange={(event) => updateBodyValue("current_weight_kg", event.target.value)} /><small>{language === "en" ? "35–300 kg" : "۳۵ تا ۳۰۰ کیلوگرم"}</small></label>
          {showBodyConfirmation && <label className="guided-body-confirmation"><input type="checkbox" checked={bodyValuesConfirmed} onChange={(event) => setBodyValuesConfirmed(event.target.checked)} />{language === "en" ? "These values are correct." : "این مقادیر درست هستند."}</label>}
        </div>}
        {question === 4 && <div className="guided-choice-grid">{goals.map(([goal, emoji]) => <button className={values.fitness_goal === goal ? "is-selected" : ""} key={goal} type="button" onClick={() => onChange("fitness_goal", goal)}>{t(`onboarding.options.fitnessGoal.${goal}`)} {emoji}</button>)}</div>}
        <div className="profile-actions">
          <button className="secondary-button" type="button" onClick={() => question === 0 ? onBack() : setQuestion((current) => current - 1)}>{back}</button>
          <button className="primary-button" type="submit" disabled={!ready}>{next}</button>
        </div>
      </form>
    </section>
  );
}
