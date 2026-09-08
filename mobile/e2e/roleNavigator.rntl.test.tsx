import { render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";

jest.mock("expo-router", () => ({
  usePathname: jest.fn(),
  useRouter: jest.fn(),
}));

import { usePathname, useRouter } from "expo-router";

import { E2ERoleNavigator } from "./RoleNavigator";

const mockUsePathname = jest.mocked(usePathname);
const mockUseRouter = jest.mocked(useRouter);
const router = { replace: jest.fn() };

beforeEach(() => {
  process.env.EXPO_PUBLIC_E2E = "1";
  mockUsePathname.mockReturnValue("/member");
  mockUseRouter.mockReturnValue(router as never);
  router.replace.mockReset();
});

test("exposes dev-only role navigation for positive specialist flows", () => {
  render(<E2ERoleNavigator />);

  expect(screen.getByRole("button", { name: "E2E: مربی" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "E2E: پزشک" })).toBeTruthy();
});

test("does not expose the harness outside the member landing route", () => {
  mockUsePathname.mockReturnValue("/auth/sign-in");

  render(<E2ERoleNavigator />);

  expect(screen.queryByRole("button", { name: "E2E: مربی" })).toBeNull();
  expect(screen.queryByRole("button", { name: "E2E: پزشک" })).toBeNull();
});
