import { fireEvent, render, screen } from "@testing-library/react-native";
import { expect, test } from "@jest/globals";

import type { BodyPhoto } from "@fitician/core/body-photos";

import { BodyBeforeAfterComparison } from "./BodyBeforeAfterComparison";

const photos = ["front", "side", "back"].map((view) => ({ view })) as unknown as BodyPhoto[];

test("supports native view selection and before-after touch surface", () => {
  render(
    <BodyBeforeAfterComparison
      afterPhotoUris={{ back: "file:///after-back.jpg", front: "file:///after-front.jpg", side: "file:///after-side.jpg" }}
      afterPhotos={photos}
      beforePhotoUris={{ back: "file:///before-back.jpg", front: "file:///before-front.jpg", side: "file:///before-side.jpg" }}
      beforePhotos={photos}
      currentDate="۱۴۰۵/۰۶/۱۶"
      previousDate="۱۴۰۵/۰۵/۲۹"
    />,
  );

  expect(screen.getByRole("header", { name: "قبل و بعد" })).toBeTruthy();
  expect(screen.getByText("قبل")).toBeTruthy();
  expect(screen.getByText("بعد")).toBeTruthy();
  expect(screen.getByLabelText("موقعیت مقایسهٔ قبل و بعد")).toBeTruthy();

  const sideButton = screen.getByRole("button", { name: "نیمرخ" });
  fireEvent.press(sideButton);
  expect(sideButton.props.accessibilityState.selected).toBe(true);
  expect(screen.getByRole("button", { name: "روبه‌رو" }).props.accessibilityState.selected).toBe(false);
});
