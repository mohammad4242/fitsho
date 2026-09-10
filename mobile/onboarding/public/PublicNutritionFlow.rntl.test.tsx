import { act, fireEvent, render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { createInitialOnboardingState, transitionOnboardingState, type OnboardingState } from "@fitician/core/onboarding";
import type { SharedProfileInput } from "@fitician/core/profile";

jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));

import { PublicNutritionOnboardingFlow } from "./PublicNutritionOnboardingFlow";

const shared = {
  birth_date: "1992-05-12",
  current_weight_kg: 64,
  display_name: "سارا",
  fitness_goal: "lose_weight" as const,
  height_cm: 168,
  sex: "female" as const,
};

function nutritionState(fitnessGoal: SharedProfileInput["fitness_goal"] = shared.fitness_goal): OnboardingState {
  let state = createInitialOnboardingState();
  state = transitionOnboardingState(state, { mode: "nutrition", type: "select_product_mode" });
  return transitionOnboardingState(state, { profile: { ...shared, fitness_goal: fitnessGoal }, type: "save_shared_profile" });
}

function renderFlow(onComplete = jest.fn(), onBack = jest.fn()) {
  return render(
    <SafeAreaProvider
      initialMetrics={{
        frame: { height: 800, width: 390, x: 0, y: 0 },
        insets: { bottom: 0, left: 0, right: 0, top: 0 },
      }}
    >
      <PublicNutritionOnboardingFlow
        mode="nutrition"
        onBack={onBack}
        onComplete={onComplete}
        state={nutritionState()}
      />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  jest.useFakeTimers();
});

test("matches the Web nutrition exercise sequence and skips to safety when exercise is absent", () => {
  const onComplete = jest.fn();
  renderFlow(onComplete);

  expect(screen.getByRole("header", { name: "در حال حاضر تمرین منظم داری؟" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "منظم تمرین می‌کنم" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "تمرین نمی‌کنم" })).toBeTruthy();

  fireEvent.press(screen.getByRole("radio", { name: "تمرین نمی‌کنم" }));
  act(() => jest.advanceTimersByTime(140));

  expect(screen.getByRole("header", { name: "آیا شرایط پزشکی مشخصی داری؟" })).toBeTruthy();
  expect(screen.getByRole("checkbox", { name: "فشار خون کنترل‌شده" })).toBeTruthy();
  expect(screen.getByRole("checkbox", { name: "دیابت با درمان انسولین" })).toBeTruthy();
});

test("keeps the four public nutrition pre-account questions and auto-advances choices", () => {
  const onComplete = jest.fn();
  renderFlow(onComplete);

  fireEvent.press(screen.getByRole("radio", { name: "تمرین نمی‌کنم" }));
  act(() => jest.advanceTimersByTime(140));
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));

  expect(screen.getByRole("header", { name: "میزان فعالیت روزانه‌ات چقدر است؟" })).toBeTruthy();
  fireEvent.press(screen.getByRole("radio", { name: "فعالیت متوسط" }));
  act(() => jest.advanceTimersByTime(140));
  expect(screen.getByRole("header", { name: "بودجه ماهانه غذای تو چقدر است؟" })).toBeTruthy();

  fireEvent.changeText(screen.getByLabelText("بودجه ماهانه غذا (تومان)"), "5000000");
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
  expect(screen.getByRole("header", { name: "چه سبک غذایی را ترجیح می‌دهی؟" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "گیاه‌خوار (به‌زودی)" }).props.accessibilityState).toMatchObject({ disabled: true });

  fireEvent.press(screen.getByRole("radio", { name: "همه‌چیزخوار" }));
  act(() => jest.advanceTimersByTime(140));
  expect(onComplete).toHaveBeenCalledWith(expect.objectContaining({
    nutritionBasics: expect.objectContaining({
      daily_activity_level: "moderate",
      dietary_pattern: "omnivore",
    }),
  }));
});

test("keeps the Web nutrition exercise choices and structured payload", () => {
  const onComplete = jest.fn();
  renderFlow(onComplete);

  fireEvent.press(screen.getByRole("radio", { name: "منظم تمرین می‌کنم" }));
  act(() => jest.advanceTimersByTime(140));
  for (const label of ["تمرین مقاومتی", "تمرین هوازی و استقامتی", "تمرین ترکیبی", "نوع دیگر"]) {
    expect(screen.getByRole("radio", { name: label })).toBeTruthy();
  }
  fireEvent.press(screen.getByRole("radio", { name: "تمرین ترکیبی" }));
  act(() => jest.advanceTimersByTime(140));
  for (let day = 1; day <= 7; day += 1) {
    expect(screen.getByRole("radio", { name: `${new Intl.NumberFormat("fa-IR").format(day)} روز در هفته` })).toBeTruthy();
  }
  fireEvent.press(screen.getByRole("radio", { name: "۳ روز در هفته" }));
  act(() => jest.advanceTimersByTime(140));
  fireEvent.press(screen.getByRole("radio", { name: "۶۰–۷۵ دقیقه" }));
  act(() => jest.advanceTimersByTime(140));
  fireEvent.press(screen.getByRole("radio", { name: "شدید" }));
  act(() => jest.advanceTimersByTime(140));

  expect(screen.getByRole("header", { name: "آیا شرایط پزشکی مشخصی داری؟" })).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
  fireEvent.press(screen.getByRole("radio", { name: "فعالیت متوسط" }));
  act(() => jest.advanceTimersByTime(140));
  fireEvent.changeText(screen.getByLabelText("بودجه ماهانه غذا (تومان)"), "5000000");
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
  fireEvent.press(screen.getByRole("radio", { name: "همه‌چیزخوار" }));
  act(() => jest.advanceTimersByTime(140));

  expect(onComplete).toHaveBeenCalledWith(expect.objectContaining({
    structuredExercise: {
      trains: true,
      exercise_type: "mixed",
      days_per_week: 3,
      minutes_per_session: 75,
      intensity: "vigorous",
    },
  }));
});

test("keeps the Web build-muscle no-training safety block", () => {
  const onComplete = jest.fn();
  render(
    <SafeAreaProvider
      initialMetrics={{
        frame: { height: 800, width: 390, x: 0, y: 0 },
        insets: { bottom: 0, left: 0, right: 0, top: 0 },
      }}
    >
      <PublicNutritionOnboardingFlow
        mode="nutrition"
        onBack={jest.fn()}
        onComplete={onComplete}
        state={nutritionState("build_muscle")}
      />
    </SafeAreaProvider>,
  );

  fireEvent.press(screen.getByRole("radio", { name: "تمرین نمی‌کنم" }));
  expect(screen.getByRole("alert")).toHaveTextContent("برای این هدف باید هدفت را تغییر بدهی یا مسیر تمرینی را انتخاب کنی.");
  expect(onComplete).not.toHaveBeenCalled();
});
