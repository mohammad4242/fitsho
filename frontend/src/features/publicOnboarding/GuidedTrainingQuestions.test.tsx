import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { GuidedTrainingQuestions } from "./GuidedTrainingQuestions";

const values = {
  display_name: "Sara", birth_date: "2000-05-14", sex: "female" as const,
  height_cm: "165", current_weight_kg: "62", shoulder_circumference_cm: "",
  waist_circumference_cm: "", hip_circumference_cm: "", fitness_goal: "fat_loss" as const,
  experience_level: "" as const, training_days_per_week: "", training_location: "" as const,
  home_training_setup: "" as const, session_duration_minutes: "", physical_limitations: "",
  training_cautions: null, plan_duration_weeks: "4",
};

function TrainingHarness({ allowNoTraining = false, onNoTraining = vi.fn() }: { allowNoTraining?: boolean; onNoTraining?: () => void }) {
  const [formValues, setFormValues] = useState(values);
  const [completed, setCompleted] = useState(false);
  return <>
    <GuidedTrainingQuestions
      values={formValues}
      onChange={(field, value) => setFormValues((current) => ({ ...current, [field]: value }))}
      onBack={() => undefined}
      onComplete={() => setCompleted(true)}
      allowNoTraining={allowNoTraining}
      onNoTraining={onNoTraining}
    />
    {formValues.training_cautions !== null && <p>cautions-set</p>}
    {completed && <p>completed</p>}
  </>;
}

it("uses fixed experience, weekly-day, and workout-time choices", async () => {
  await i18n.changeLanguage("fa");
  const user = userEvent.setup();
  render(<TrainingHarness />);

  expect(screen.getByRole("heading", { name: "چقدر سابقه تمرین مداوم داری؟" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "مبتدی (زیر ۶ ماه)" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "مبتدی (زیر ۶ ماه)" }));
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.click(screen.getByRole("button", { name: "۴ روز در هفته" }));
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.click(screen.getByRole("button", { name: "باشگاه" }));
  await user.click(screen.getByRole("button", { name: "ادامه" }));

  expect(screen.getByRole("button", { name: "۲۰ تا ۳۰ دقیقه" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "بیش از ۹۰ دقیقه" })).toBeInTheDocument();
  expect(screen.queryByText("مربی دربارهٔ محدودیت جسمی دیگری بداند؟")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "۴۵ تا ۶۰ دقیقه" }));
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  expect(screen.getByText("cautions-set")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "۴ هفته" }));
  await user.click(screen.getByRole("button", { name: "ادامه" }));

  expect(screen.getByText("completed")).toBeInTheDocument();
});

it("offers no-training only for nutrition and skips all training details", async () => {
  await i18n.changeLanguage("fa");
  const user = userEvent.setup();
  const onNoTraining = vi.fn();
  render(<TrainingHarness allowNoTraining onNoTraining={onNoTraining} />);

  await user.click(screen.getByRole("button", { name: "تمرین نمی‌کنم" }));
  await user.click(screen.getByRole("button", { name: "ادامه" }));

  expect(onNoTraining).toHaveBeenCalledOnce();
  expect(screen.queryByRole("heading", { name: "چند روز در هفته تمرین می‌کنی؟" })).not.toBeInTheDocument();
});

it("does not offer no-training in the required training flow", async () => {
  await i18n.changeLanguage("fa");
  render(<TrainingHarness />);

  expect(screen.queryByRole("button", { name: "تمرین نمی‌کنم" })).not.toBeInTheDocument();
});
