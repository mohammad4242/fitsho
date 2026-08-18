import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../../shared/apiClient";
import {
  getCurrentWorkoutCycle,
  getCurrentWeeklyCheckIn,
  saveCurrentWeeklyCheckIn,
} from "./api";
import type {
  WorkoutCyclePerceivedDifficulty,
  WorkoutCycleRecoveryRating,
  WorkoutCycleWeeklyCheckIn,
  WorkoutCycleWeeklyCheckInInput,
  WorkoutPlan,
} from "./types";
import "./weeklyCheckIn.css";

type CheckInState = "loading" | "draft" | "completed" | "error" | "unavailable";

type FormState = {
  sessionsCompleted: number;
  perceivedDifficulty: WorkoutCyclePerceivedDifficulty;
  recoveryRating: WorkoutCycleRecoveryRating;
  hasPainOrLimitation: boolean;
  affectedExerciseId: string;
  painNote: string;
};

const difficultyOptions: Array<{ value: WorkoutCyclePerceivedDifficulty; fa: string; en: string }> = [
  { value: "too_easy", fa: "خیلی سبک", en: "Far too easy" },
  { value: "easy", fa: "سبک", en: "Easy" },
  { value: "appropriate", fa: "مناسب", en: "About right" },
  { value: "hard", fa: "سنگین", en: "Hard" },
  { value: "too_hard", fa: "خیلی سنگین", en: "Far too hard" },
];

const recoveryOptions: Array<{ value: WorkoutCycleRecoveryRating; fa: string; en: string }> = [
  { value: "good", fa: "خوب", en: "Good" },
  { value: "average", fa: "متوسط", en: "Average" },
  { value: "poor", fa: "ضعیف", en: "Poor" },
];

export function WeeklyCheckInCard({ plan }: { plan: WorkoutPlan }) {
  const { i18n, t } = useTranslation();
  const [state, setState] = useState<CheckInState>("loading");
  const [checkIn, setCheckIn] = useState<WorkoutCycleWeeklyCheckIn | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [currentWeek, setCurrentWeek] = useState(1);
  const [formError, setFormError] = useState(false);
  const [submitError, setSubmitError] = useState(false);
  const [form, setForm] = useState<FormState>(() => emptyForm());
  const isEnglish = i18n.resolvedLanguage === "en";
  const l = (fa: string, en: string) => isEnglish ? en : fa;
  const exercises = plan.days.flatMap((day) => day.exercises);
  const number = new Intl.NumberFormat(isEnglish ? "en-US" : "fa-IR");

  useEffect(() => {
    let active = true;
    setState("loading");
    setCheckIn(null);
    setEditing(false);
    void Promise.all([getCurrentWorkoutCycle(), getCurrentWeeklyCheckIn()])
      .then(([cycle, loaded]) => {
        if (!active) return;
        if (cycle === null || cycle.status !== "active") {
          setState("unavailable");
          return;
        }
        setCheckIn(loaded);
        setForm(formFromCheckIn(loaded));
        setCurrentWeek(cycle.current_week);
        setState(loaded === null ? "draft" : "completed");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setState(error instanceof ApiError && error.status === 404 ? "unavailable" : "error");
      });
    return () => {
      active = false;
    };
  }, [loadAttempt, plan.id]);

  function updateForm<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setFormError(false);
    setSubmitError(false);
  }

  function edit() {
    setForm(formFromCheckIn(checkIn));
    setFormError(false);
    setSubmitError(false);
    setEditing(true);
  }

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (form.hasPainOrLimitation && form.affectedExerciseId === "") {
      setFormError(true);
      return;
    }
    const input: WorkoutCycleWeeklyCheckInInput = {
      sessions_completed: form.sessionsCompleted,
      perceived_difficulty: form.perceivedDifficulty,
      recovery_rating: form.recoveryRating,
      has_pain_or_limitation: form.hasPainOrLimitation,
      pain_follow_up: form.hasPainOrLimitation
        ? { workout_plan_exercise_id: form.affectedExerciseId, note_optional: form.painNote.trim() || null }
        : null,
      note_optional: null,
    };
    setSaving(true);
    setSubmitError(false);
    void saveCurrentWeeklyCheckIn(input)
      .then((saved) => {
        setCheckIn(saved);
        setForm(formFromCheckIn(saved));
        setEditing(false);
        setState("completed");
      })
      .catch(() => setSubmitError(true))
      .finally(() => setSaving(false));
  }

  if (state === "unavailable") return null;
  if (state === "loading") {
    return <section className="weekly-check-in weekly-check-in--loading" role="status">{t("workoutPlan.weeklyCheckIn.loading")}</section>;
  }
  if (state === "error") {
    return (
      <section className="weekly-check-in weekly-check-in--error" role="alert">
        <p>{t("workoutPlan.weeklyCheckIn.loadError")}</p>
        <button type="button" onClick={() => setLoadAttempt((attempt) => attempt + 1)}>{t("common.retry")}</button>
      </section>
    );
  }
  if (state === "completed" && !editing && checkIn !== null) {
    return (
      <section className="weekly-check-in weekly-check-in--completed" aria-labelledby="weekly-check-in-title">
        <div className="weekly-check-in__header">
          <div>
            <p className="eyebrow">{t("workoutPlan.weeklyCheckIn.eyebrow")}</p>
            <h2 id="weekly-check-in-title">{t("workoutPlan.weeklyCheckIn.title")}</h2>
          </div>
          <span className="weekly-check-in__check" aria-hidden="true">✓</span>
        </div>
        <p className="weekly-check-in__complete-message">{t("workoutPlan.weeklyCheckIn.completed")}</p>
        <p className="weekly-check-in__summary">
          {t("workoutPlan.weeklyCheckIn.sessionsSummary", { count: number.format(checkIn.sessions_completed) })}
          <span aria-hidden="true"> · </span>
          {l(
            difficultyOptions.find((option) => option.value === checkIn.perceived_difficulty)?.fa ?? "",
            difficultyOptions.find((option) => option.value === checkIn.perceived_difficulty)?.en ?? "",
          )}
        </p>
        <button className="weekly-check-in__edit" type="button" onClick={edit}>{t("workoutPlan.weeklyCheckIn.edit")}</button>
      </section>
    );
  }

  return (
    <section className="weekly-check-in" aria-labelledby="weekly-check-in-title">
      <div className="weekly-check-in__header">
        <div>
          <p className="eyebrow">{t("workoutPlan.weeklyCheckIn.eyebrow")}</p>
          <h2 id="weekly-check-in-title">{t("workoutPlan.weeklyCheckIn.title")}</h2>
          <p>{t("workoutPlan.weeklyCheckIn.intro")}</p>
        </div>
        <span className="weekly-check-in__week">{t("workoutPlan.weeklyCheckIn.week", { count: number.format(currentWeek) })}</span>
      </div>

      <form onSubmit={submit}>
        <fieldset>
          <legend>{t("workoutPlan.weeklyCheckIn.sessionsQuestion")}</legend>
          <div className="weekly-check-in__choices weekly-check-in__choices--sessions">
            {Array.from({ length: plan.days.length + 1 }, (_, sessions) => (
              <label key={sessions}>
                <input
                  type="radio"
                  name={`weekly-check-in-sessions-${plan.id}`}
                  value={sessions}
                  checked={form.sessionsCompleted === sessions}
                  onChange={() => updateForm("sessionsCompleted", sessions)}
                />
                <span>{number.format(sessions)}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <CheckInChoiceGroup
          legend={t("workoutPlan.weeklyCheckIn.difficultyQuestion")}
          name={`weekly-check-in-difficulty-${plan.id}`}
          value={form.perceivedDifficulty}
          options={difficultyOptions}
          isEnglish={isEnglish}
          onChange={(value) => updateForm("perceivedDifficulty", value)}
        />
        <CheckInChoiceGroup
          legend={t("workoutPlan.weeklyCheckIn.recoveryQuestion")}
          name={`weekly-check-in-recovery-${plan.id}`}
          value={form.recoveryRating}
          options={recoveryOptions}
          isEnglish={isEnglish}
          onChange={(value) => updateForm("recoveryRating", value)}
        />

        <fieldset>
          <legend>{t("workoutPlan.weeklyCheckIn.painQuestion")}</legend>
          <div className="weekly-check-in__choices weekly-check-in__choices--binary">
            <ChoiceLabel name={`weekly-check-in-pain-${plan.id}`} value="false" checked={!form.hasPainOrLimitation} label={t("workoutPlan.weeklyCheckIn.no")} onChange={() => updateForm("hasPainOrLimitation", false)} />
            <ChoiceLabel name={`weekly-check-in-pain-${plan.id}`} value="true" checked={form.hasPainOrLimitation} label={t("workoutPlan.weeklyCheckIn.yes")} onChange={() => updateForm("hasPainOrLimitation", true)} />
          </div>
        </fieldset>

        {form.hasPainOrLimitation && (
          <div className="weekly-check-in__pain-follow-up">
            <label className="weekly-check-in__field" htmlFor="weekly-check-in-exercise">
              <span>{t("workoutPlan.weeklyCheckIn.affectedExercise")}</span>
              <select
                id="weekly-check-in-exercise"
                aria-invalid={formError && form.affectedExerciseId === ""}
                value={form.affectedExerciseId}
                onChange={(event) => updateForm("affectedExerciseId", event.target.value)}
              >
                <option value="">{t("workoutPlan.weeklyCheckIn.chooseExercise")}</option>
                {exercises.map((item) => (
                  <option key={item.id} value={item.id}>{isEnglish ? item.exercise.name_en : item.exercise.name_fa}</option>
                ))}
              </select>
            </label>
            <label className="weekly-check-in__field" htmlFor="weekly-check-in-note">
              <span>{t("workoutPlan.weeklyCheckIn.noteLabel")}</span>
              <textarea
                id="weekly-check-in-note"
                value={form.painNote}
                maxLength={240}
                rows={2}
                placeholder={t("workoutPlan.weeklyCheckIn.notePlaceholder")}
                onChange={(event) => updateForm("painNote", event.target.value)}
              />
            </label>
            {formError && <p className="weekly-check-in__validation" role="alert">{t("workoutPlan.weeklyCheckIn.exerciseRequired")}</p>}
          </div>
        )}

        {submitError && <p className="weekly-check-in__validation" role="alert">{t("workoutPlan.weeklyCheckIn.saveError")}</p>}
        <button className="weekly-check-in__submit" type="submit" disabled={saving} aria-busy={saving}>
          {saving ? t("workoutPlan.weeklyCheckIn.saving") : editing ? t("workoutPlan.weeklyCheckIn.saveChanges") : t("workoutPlan.weeklyCheckIn.submit")}
        </button>
      </form>
    </section>
  );
}

function CheckInChoiceGroup<T extends string>({
  legend,
  name,
  value,
  options,
  isEnglish,
  onChange,
}: {
  legend: string;
  name: string;
  value: T;
  options: Array<{ value: T; fa: string; en: string }>;
  isEnglish: boolean;
  onChange: (value: T) => void;
}) {
  return (
    <fieldset>
      <legend>{legend}</legend>
      <div className="weekly-check-in__choices">
        {options.map((option) => (
          <ChoiceLabel key={option.value} name={name} value={option.value} checked={value === option.value} label={isEnglish ? option.en : option.fa} onChange={() => onChange(option.value)} />
        ))}
      </div>
    </fieldset>
  );
}

function ChoiceLabel({ name, value, checked, label, onChange }: { name: string; value: string; checked: boolean; label: string; onChange: () => void }) {
  return (
    <label>
      <input type="radio" name={name} value={value} checked={checked} onChange={onChange} />
      <span>{label}</span>
    </label>
  );
}

function emptyForm(): FormState {
  return {
    sessionsCompleted: 0,
    perceivedDifficulty: "appropriate",
    recoveryRating: "good",
    hasPainOrLimitation: false,
    affectedExerciseId: "",
    painNote: "",
  };
}

function formFromCheckIn(checkIn: WorkoutCycleWeeklyCheckIn | null): FormState {
  if (checkIn === null) return emptyForm();
  return {
    sessionsCompleted: checkIn.sessions_completed,
    perceivedDifficulty: checkIn.perceived_difficulty,
    recoveryRating: checkIn.recovery_rating,
    hasPainOrLimitation: checkIn.has_pain_or_limitation,
    affectedExerciseId: checkIn.pain_follow_up?.workout_plan_exercise_id ?? "",
    painNote: checkIn.pain_follow_up?.note_optional ?? "",
  };
}
