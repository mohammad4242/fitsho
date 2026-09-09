import { fireEvent, render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";

const mockPush = jest.fn();
jest.mock("expo-router", () => ({ useRouter: jest.fn(() => ({ push: mockPush })) }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));

import { NutritionDoctorSupervision } from "./NutritionDoctorSupervision";

test("shows the compact doctor card without inventing pending plan state", () => {
  render(<NutritionDoctorSupervision plan={null} />);

  const disclosure = screen.getByRole("button", { name: "تحت نظر پزشک" });
  expect(screen.getByText("خدمات و وضعیت بررسی پزشکی در یک نگاه")).toBeTruthy();
  expect(screen.queryByText("پس از ساخت برنامه")).toBeNull();
  fireEvent.press(disclosure);

  expect(screen.getByText("مکمل‌های من")).toBeTruthy();
  expect(screen.getByText("آزمایشات من")).toBeTruthy();
  expect(screen.getByText("تأیید برنامه غذایی")).toBeTruthy();
  expect(screen.getByText("راهنمایی‌های پزشک")).toBeTruthy();
  expect(screen.getByText("پس از ساخت برنامه")).toBeTruthy();

  fireEvent.press(screen.getByRole("button", { name: "مکمل‌های من" }));
  expect(mockPush).toHaveBeenCalledWith("/member/nutrition-supplements");
  fireEvent.press(screen.getByRole("button", { name: "آزمایشات من" }));
  expect(mockPush).toHaveBeenCalledWith("/member/nutrition-labs");
});
