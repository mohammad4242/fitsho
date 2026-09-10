import { fireEvent, render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";
import { Animated, StyleSheet, Text } from "react-native";
import { Circle } from "react-native-svg";

jest.mock("expo-router", () => ({
  useFocusEffect: (effect: () => void) => effect(),
}));

import { Button } from "./components/Button";
import { CinematicSurface } from "./components/CinematicSurface";
import { TextField } from "./components/Input";
import { MetricRing } from "./components/MetricRing";
import { Dialog, Sheet } from "./components/Overlay";
import { Notice } from "./components/Feedback";
import { calculateRingGeometry } from "./visualMetrics";

test("renders the shared button with native accessibility and press behavior", () => {
  const onPress = jest.fn();

  render(<Button label="ذخیره" onPress={onPress} />);

  const button = screen.getByRole("button", { name: "ذخیره" });
  expect(button.props.accessibilityState).toMatchObject({ disabled: false, busy: false });
  expect(button.props.style).toEqual(
    expect.arrayContaining([expect.objectContaining({ minHeight: 48, minWidth: 48 })]),
  );

  fireEvent.press(button);
  expect(onPress).toHaveBeenCalledTimes(1);
});

test("announces the Persian loading state while preserving the button state", () => {
  render(<Button label="ذخیره" loading onPress={jest.fn()} />);

  const button = screen.getByRole("button", { name: "ذخیره" });
  expect(button.props.accessibilityState).toMatchObject({ busy: true, disabled: true });
  expect(screen.getByLabelText("در حال بارگذاری")).toBeTruthy();
});

test("keeps screen-reader names, font scaling, and focus order in source order", () => {
  render(
    <>
      <TextField label="ایمیل" />
      <Button label="اول" onPress={jest.fn()} />
      <Button label="دوم" onPress={jest.fn()} />
    </>,
  );

  const field = screen.getByLabelText("ایمیل");
  expect(field.props.allowFontScaling).toBe(true);
  expect(field.props.accessibilityLabel).toBe("ایمیل");
  expect(screen.getAllByRole("button").map((button) => button.props.accessibilityLabel)).toEqual([
    "اول",
    "دوم",
  ]);
});

test("exposes metric progress and its visible value to assistive technology", () => {
  render(<MetricRing label="پیشرفت کالری امروز" progress={0.375} />);

  const ring = screen.getByRole("progressbar", { name: "پیشرفت کالری امروز" });
  expect(ring.props.accessibilityValue).toEqual({ max: 100, min: 0, now: 38 });
  expect(screen.getByText("۳۸٪")).toBeTruthy();
});

test("keeps the shared ring static unless focus animation is explicitly enabled", () => {
  render(<MetricRing label="پیشرفت کالری امروز" progress={0.375} />);

  const progressCircle = screen.UNSAFE_getAllByType(Circle)[1];
  expect(progressCircle.props.strokeDashoffset).toBe(calculateRingGeometry(92, 8, 0.375).dashOffset);
});

test("uses the requested duration for the opt-in focus entrance animation", () => {
  const timing = jest.spyOn(Animated, "timing").mockReturnValue({ start: jest.fn() } as never);

  render(<MetricRing animateOnFocus animationDuration={900} label="پیشرفت کالری امروز" progress={0.375} />);

  expect(timing).toHaveBeenCalledWith(
    expect.anything(),
    expect.objectContaining({ duration: 900, toValue: 0.375, useNativeDriver: false }),
  );
  timing.mockRestore();
});

test("keeps Persian overlays direction-aware", () => {
  const view = render(
    <>
      <Sheet onClose={jest.fn()} title="جزئیات" visible><Text>متن</Text><TextField label="نام" /></Sheet>
      <Dialog message="پیام" onClose={jest.fn()} title="تأیید" visible />
    </>,
  );

  expect(view).toBeTruthy();
});

test("anchors the shared cinematic surface to the RTL layout boundary", () => {
  render(
    <CinematicSurface testID="cinematic-surface">
      <Text>محتوا</Text>
    </CinematicSurface>,
  );

  expect(StyleSheet.flatten(screen.getByTestId("cinematic-surface").props.style)).toMatchObject({
    direction: "rtl",
  });
});

test("announces errors and exposes native modal boundaries", () => {
  const view = render(
    <>
      <Notice message="اتصال برقرار نیست" title="خطا" variant="danger" />
      <Sheet onClose={jest.fn()} title="جزئیات" visible><Text>متن</Text></Sheet>
      <Dialog message="ادامه می‌دهی؟" onClose={jest.fn()} title="تأیید" visible />
    </>,
  );

  const alert = view.UNSAFE_getByProps({ accessibilityRole: "alert" });
  expect(alert.props.accessibilityLiveRegion).toBe("assertive");
  expect(view.getByLabelText("جزئیات").props.accessibilityViewIsModal).toBe(true);
  expect(view.getByLabelText("تأیید").props.accessibilityViewIsModal).toBe(true);
});
