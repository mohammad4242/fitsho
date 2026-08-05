import { type FormEvent, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import type { ProfileFormValues, TrainingCaution } from "../profile/types";

type Props = {
  values: ProfileFormValues;
  onChange: (field: keyof ProfileFormValues, value: string | ProfileFormValues["training_cautions"]) => void;
  onBack: () => void;
  onComplete: () => void;
};

export function GuidedTrainingQuestions({ values, onChange, onBack, onComplete }: Props) {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage === "en" ? "en" : "fa";
  const questions = useMemo(() => ["experience", "days", "location", ...(values.training_location === "home" ? ["home"] : []), "duration", "cautions", "weeks", "limitations"] as const, [values.training_location]);
  const [index, setIndex] = useState(0);
  const question = questions[Math.min(index, questions.length - 1)];
  const title = ({
    experience: language === "en" ? "What is your training experience?" : "چه‌قدر تجربهٔ تمرین داری؟",
    days: language === "en" ? "How many days can you train?" : "چند روز در هفته تمرین می‌کنی؟",
    location: language === "en" ? "Where will you train?" : "کجا تمرین می‌کنی؟",
    home: language === "en" ? "What do you have at home?" : "در خانه چه امکاناتی داری؟",
    duration: language === "en" ? "How long is each workout?" : "برای هر جلسه چقدر زمان داری؟",
    cautions: language === "en" ? "Any training considerations?" : "برای تمرین مورد احتیاطی داری؟",
    weeks: language === "en" ? "How long should this plan run?" : "این برنامه چند هفته باشد؟",
    limitations: language === "en" ? "Anything else your coach should know?" : "مربی دربارهٔ محدودیت جسمی دیگری بداند؟",
  })[question];
  const choice = (field: keyof ProfileFormValues, value: string, label: string) => <button className={values[field] === value ? "is-selected" : ""} key={value} type="button" onClick={() => onChange(field, value)}>{label}</button>;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (index === questions.length - 1) onComplete();
    else setIndex((current) => current + 1);
  }
  function back() { if (index === 0) onBack(); else setIndex((current) => current - 1); }
  const cautions = values.training_cautions ?? [];
  function toggle(caution: TrainingCaution) { onChange("training_cautions", cautions.includes(caution) ? cautions.filter((item) => item !== caution) : [...cautions, caution]); }
  const ready = ({
    experience: values.experience_level !== "",
    days: Number(values.training_days_per_week) >= 2 && Number(values.training_days_per_week) <= 6,
    location: values.training_location !== "",
    home: values.home_training_setup !== "",
    duration: values.session_duration_minutes !== "",
    cautions: true,
    weeks: values.plan_duration_weeks !== "",
    limitations: true,
  })[question];
  const activeStage = question === "experience" ? 0 : ["days", "location", "home", "duration"].includes(question) ? 1 : 2;
  const stages = language === "en" ? ["Experience", "Routine", "Safety"] : ["تجربه", "برنامه", "ایمنی"];

  return <section className="guided-question" aria-labelledby="guided-training-title">
    <ol className="guided-stage-track" aria-label={language === "en" ? "Training sections" : "بخش‌های تمرین"}>{stages.map((stage, stageIndex) => <li className={stageIndex < activeStage ? "is-complete" : stageIndex === activeStage ? "is-active" : ""} key={stage}><span aria-hidden="true">{stageIndex < activeStage ? "✓" : stageIndex + 1}</span>{stage}</li>)}</ol>
    <div className="public-onboarding-progress"><span>{language === "en" ? `Training ${index + 1} of ${questions.length}` : `تمرین ${index + 1} از ${questions.length}`}</span><progress value={index + 1} max={questions.length} /></div>
    <h1 className="fitsho-display" id="guided-training-title">{title}</h1>
    <form className="guided-question__form" onSubmit={submit}>
      {question === "experience" && <div className="guided-choice-grid">{["beginner", "intermediate", "advanced"].map((value) => choice("experience_level", value, t(`onboarding.options.experience.${value}`)))}</div>}
      {question === "days" && <label>{t("onboarding.fields.trainingDays")}<input required type="number" min="2" max="6" value={values.training_days_per_week} onChange={(event) => onChange("training_days_per_week", event.target.value)} /></label>}
      {question === "location" && <div className="guided-choice-grid">{["home", "gym"].map((value) => choice("training_location", value, t(`onboarding.options.trainingLocation.${value}`)))}</div>}
      {question === "home" && <div className="guided-choice-grid">{["bodyweight_only", "dumbbells_available"].map((value) => choice("home_training_setup", value, t(`onboarding.options.homeTrainingSetup.${value}`)))}</div>}
      {question === "duration" && <div className="guided-choice-grid">{[30, 45, 60, 75, 90].map((value) => choice("session_duration_minutes", String(value), t(`onboarding.options.sessionDuration.${value}`)))}</div>}
      {question === "cautions" && <div className="guided-choice-grid">{(["lower_back", "knee", "shoulder", "neck", "wrist", "other"] as TrainingCaution[]).map((value) => <button className={cautions.includes(value) ? "is-selected" : ""} key={value} type="button" onClick={() => toggle(value)}>{t(`onboarding.options.trainingCaution.${value}`)}</button>)}</div>}
      {question === "weeks" && <div className="guided-choice-grid">{[4, 6, 8].map((value) => choice("plan_duration_weeks", String(value), t(`onboarding.options.planDuration.${value}`)))}</div>}
      {question === "limitations" && <label>{t("onboarding.fields.limitations")}<textarea maxLength={1000} value={values.physical_limitations} onChange={(event) => onChange("physical_limitations", event.target.value)} /></label>}
      {(question === "cautions" || question === "limitations") && <button className="text-button" type="submit">{language === "en" ? "Skip this question" : "رد کردن این سؤال"}</button>}
      <div className="profile-actions"><button className="secondary-button" type="button" onClick={back}>{language === "en" ? "Back" : "بازگشت"}</button><button className="primary-button" type="submit" disabled={!ready}>{language === "en" ? "Continue" : "ادامه"}</button></div>
    </form>
  </section>;
}
