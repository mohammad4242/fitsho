import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { AppIcon } from "../../shared/AppIcon";
import { getCurrentCompletionFeedback, saveCurrentCompletionFeedback } from "./api";
import type {
  WorkoutCycleCompletionFeedbackContext,
  WorkoutCycleCompletionFeedbackInput,
} from "./types";
import "./endCycleFeedback.css";

type CardState = "loading" | "hidden" | "draft" | "completed" | "error";

const emptyDraft: WorkoutCycleCompletionFeedbackInput = {
  overall_difficulty: "appropriate",
  overall_recovery: "good",
  overall_satisfaction: "neutral",
  strength_progress: "unchanged",
  muscle_progress: "unchanged",
  endurance_progress: "unchanged",
  energy_progress: "unchanged",
  performance_changes: null,
  pain_or_limitation_feedback: null,
  note_optional: null,
};

const difficultyOptions = [
  ["too_easy", "خیلی سبک", "Far too easy"],
  ["easy", "سبک", "Easy"],
  ["appropriate", "مناسب", "About right"],
  ["hard", "سنگین", "Hard"],
  ["too_hard", "خیلی سنگین", "Far too hard"],
] as const;

const recoveryOptions = [
  ["good", "خوب", "Good"],
  ["average", "متوسط", "Average"],
  ["poor", "ضعیف", "Poor"],
] as const;

const satisfactionOptions = [
  ["very_dissatisfied", "خیلی ناراضی", "Very dissatisfied"],
  ["dissatisfied", "ناراضی", "Dissatisfied"],
  ["neutral", "معمولی", "Neutral"],
  ["satisfied", "راضی", "Satisfied"],
  ["very_satisfied", "خیلی راضی", "Very satisfied"],
] as const;

const progressOptions = [
  ["declined", "کمتر شد", "Declined"],
  ["unchanged", "بدون تغییر", "Unchanged"],
  ["improved", "بهتر شد", "Improved"],
] as const;

export function EndCycleFeedbackCard() {
  const { i18n, t } = useTranslation();
  const [state, setState] = useState<CardState>("loading");
  const [context, setContext] = useState<WorkoutCycleCompletionFeedbackContext | null>(null);
  const [draft, setDraft] = useState(emptyDraft);
  const [saving, setSaving] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [lockedInfoOpen, setLockedInfoOpen] = useState(false);
  const isEnglish = i18n.resolvedLanguage === "en";
  const l = (fa: string, en: string) => isEnglish ? en : fa;

  useEffect(() => {
    let active = true;
    setState("loading");
    void getCurrentCompletionFeedback()
      .then((loaded) => {
        if (!active) return;
        setContext(loaded);
        if (loaded?.feedback !== null && loaded?.feedback !== undefined) {
          setDraft(loaded.feedback);
          setState("completed");
        } else if (loaded?.is_due === true) {
          setDraft(emptyDraft);
          setState("draft");
        } else {
          setState("hidden");
        }
      })
      .catch(() => {
        if (active) setState("error");
      });
    return () => {
      active = false;
    };
  }, [loadAttempt]);

  function update<K extends keyof WorkoutCycleCompletionFeedbackInput>(
    key: K,
    value: WorkoutCycleCompletionFeedbackInput[K],
  ) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    void saveCurrentCompletionFeedback(draft)
      .then((saved) => {
        setContext(saved);
        setDraft(saved.feedback ?? draft);
        setState("completed");
      })
      .catch(() => setState("error"))
      .finally(() => setSaving(false));
  }

  if (state === "hidden" && context !== null) {
    const weeks = new Intl.NumberFormat(isEnglish ? "en-US" : "fa-IR").format(context.duration_weeks);
    return (
      <section className="end-cycle-feedback end-cycle-feedback--locked" aria-labelledby="end-cycle-feedback-title">
        <button
          className="end-cycle-feedback__locked-trigger"
          type="button"
          aria-controls="end-cycle-feedback-locked-message"
          aria-expanded={lockedInfoOpen}
          aria-label={t("workoutPlan.endCycleFeedback.title")}
          onClick={() => setLockedInfoOpen((open) => !open)}
        >
          <span className="end-cycle-feedback__locked-icon" aria-hidden="true">
            <AppIcon name="feedback" />
            <span className="end-cycle-feedback__lock-badge"><AppIcon name="lock" /></span>
          </span>
          <span className="end-cycle-feedback__locked-copy">
            <span className="eyebrow">{t("workoutPlan.endCycleFeedback.eyebrow")}</span>
            <strong id="end-cycle-feedback-title">{t("workoutPlan.endCycleFeedback.title")}</strong>
          </span>
          <span className="end-cycle-feedback__locked-chevron" aria-hidden="true">⌄</span>
        </button>
        <span
          className="end-cycle-feedback__locked-message"
          id="end-cycle-feedback-locked-message"
          data-visible={lockedInfoOpen}
          role="tooltip"
          aria-hidden={!lockedInfoOpen}
        >
          {t("workoutPlan.endCycleFeedback.locked", { weeks })}
        </span>
      </section>
    );
  }
  if (state === "hidden") return null;
  if (state === "loading") {
    return <section className="end-cycle-feedback end-cycle-feedback--loading" role="status">{t("workoutPlan.endCycleFeedback.loading")}</section>;
  }
  if (state === "error") {
    return (
      <section className="end-cycle-feedback end-cycle-feedback--error" role="alert">
        <p>{t("workoutPlan.endCycleFeedback.loadError")}</p>
        <button type="button" onClick={() => setLoadAttempt((attempt) => attempt + 1)}>{t("common.retry")}</button>
      </section>
    );
  }
  if (state === "completed") {
    return (
      <section className="end-cycle-feedback end-cycle-feedback--completed" aria-labelledby="end-cycle-feedback-title">
        <div className="end-cycle-feedback__header">
          <div>
            <p className="eyebrow">{t("workoutPlan.endCycleFeedback.eyebrow")}</p>
            <h2 id="end-cycle-feedback-title">{t("workoutPlan.endCycleFeedback.title")}</h2>
          </div>
          <span aria-hidden="true">✓</span>
        </div>
        <p>{t("workoutPlan.endCycleFeedback.completed")}</p>
      </section>
    );
  }

  return (
    <section className="end-cycle-feedback" aria-labelledby="end-cycle-feedback-title">
      <div className="end-cycle-feedback__header">
        <div>
          <p className="eyebrow">{t("workoutPlan.endCycleFeedback.eyebrow")}</p>
          <h2 id="end-cycle-feedback-title">{t("workoutPlan.endCycleFeedback.title")}</h2>
          <p>{t("workoutPlan.endCycleFeedback.intro")}</p>
        </div>
        {context !== null && <span>{l(`هفته ${context.current_week}`, `Week ${context.current_week}`)}</span>}
      </div>
      <form onSubmit={submit}>
        <FeedbackSelect
          label={t("workoutPlan.endCycleFeedback.difficulty")}
          value={draft.overall_difficulty ?? "appropriate"}
          options={difficultyOptions}
          isEnglish={isEnglish}
          onChange={(value) => update("overall_difficulty", value as WorkoutCycleCompletionFeedbackInput["overall_difficulty"])}
        />
        <FeedbackSelect
          label={t("workoutPlan.endCycleFeedback.recovery")}
          value={draft.overall_recovery ?? "good"}
          options={recoveryOptions}
          isEnglish={isEnglish}
          onChange={(value) => update("overall_recovery", value as WorkoutCycleCompletionFeedbackInput["overall_recovery"])}
        />
        <FeedbackSelect
          label={t("workoutPlan.endCycleFeedback.satisfaction")}
          value={draft.overall_satisfaction ?? "neutral"}
          options={satisfactionOptions}
          isEnglish={isEnglish}
          onChange={(value) => update("overall_satisfaction", value as WorkoutCycleCompletionFeedbackInput["overall_satisfaction"])}
        />
        {(["strength_progress", "muscle_progress", "endurance_progress", "energy_progress"] as const).map((field) => (
          <FeedbackSelect
            key={field}
            label={t(`workoutPlan.endCycleFeedback.${field}`)}
            value={draft[field] ?? "unchanged"}
            options={progressOptions}
            isEnglish={isEnglish}
            onChange={(value) => update(field, value as WorkoutCycleCompletionFeedbackInput[typeof field])}
          />
        ))}
        <label className="end-cycle-feedback__field">
          <span>{t("workoutPlan.endCycleFeedback.note")}</span>
          <textarea
            aria-label={t("workoutPlan.endCycleFeedback.note")}
            maxLength={4000}
            rows={3}
            value={draft.note_optional ?? ""}
            onChange={(event) => update("note_optional", event.target.value || null)}
          />
        </label>
        <button type="submit" disabled={saving} aria-busy={saving}>
          {saving ? t("workoutPlan.endCycleFeedback.saving") : t("workoutPlan.endCycleFeedback.submit")}
        </button>
      </form>
    </section>
  );
}

function FeedbackSelect({
  label,
  value,
  options,
  isEnglish,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly (readonly [string, string, string])[];
  isEnglish: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="end-cycle-feedback__field">
      <span>{label}</span>
      <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map(([option, fa, en]) => <option key={option} value={option}>{isEnglish ? en : fa}</option>)}
      </select>
    </label>
  );
}
