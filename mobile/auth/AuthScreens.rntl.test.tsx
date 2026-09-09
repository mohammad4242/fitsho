import { fireEvent, render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("expo-router", () => ({ useLocalSearchParams: jest.fn(), useRouter: jest.fn() }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("./MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("./GoogleSignIn", () => ({ useGoogleSignIn: jest.fn() }));

import { useLocalSearchParams, useRouter } from "expo-router";

import { useGoogleSignIn } from "./GoogleSignIn";
import { useMobileAuth } from "./MobileAuthProvider";
import SignInScreen from "../app/(auth)/auth/sign-in";

const mockPush = jest.fn();
const mockReplace = jest.fn();
const mockUseLocalSearchParams = jest.mocked(useLocalSearchParams);
const mockUseRouter = jest.mocked(useRouter);
const mockUseGoogleSignIn = jest.mocked(useGoogleSignIn);
const mockUseMobileAuth = jest.mocked(useMobileAuth);

function renderSignIn() {
  return render(
    <SafeAreaProvider
      initialMetrics={{
        frame: { height: 800, width: 390, x: 0, y: 0 },
        insets: { bottom: 0, left: 0, right: 0, top: 0 },
      }}
    >
      <SignInScreen />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  mockPush.mockClear();
  mockReplace.mockClear();
  mockUseRouter.mockReturnValue({ push: mockPush, replace: mockReplace } as never);
  mockUseLocalSearchParams.mockReturnValue({} as never);
  mockUseGoogleSignIn.mockReturnValue({
    available: true,
    ready: true,
    signIn: jest.fn<() => Promise<string>>(),
  });
  mockUseMobileAuth.mockReturnValue({
    busy: false,
    sendPhoneOtp: jest.fn(),
    sessionExpired: false,
    signInWithGoogle: jest.fn(),
    signInWithPassword: jest.fn(),
    startupError: null,
  } as never);
});

test("presents the Web auth hierarchy with native fields and method selection", () => {
  renderSignIn();

  expect(screen.getByText("خوش برگشتی")).toBeTruthy();
  expect(screen.getByRole("header", { name: "ادامهٔ مسیر از همین‌جا" })).toBeTruthy();
  expect(screen.getByTestId("auth-form-panel")).toBeTruthy();
  expect(screen.queryByTestId("auth-cinematic-shell")).toBeNull();
  expect(screen.getByTestId("segmented-control")).toBeTruthy();
  expect(screen.getByRole("radio", { name: "ایمیل" })).toBeTruthy();
  expect(screen.getAllByLabelText("ایمیل")).toHaveLength(2);
  expect(screen.getByRole("button", { name: "ورود به فیتشو" })).toBeTruthy();
  expect(screen.getByText("یا")).toBeTruthy();
  expect(screen.getByText("هنوز حساب نداری؟")).toBeTruthy();
});

test("keeps the phone method and forgot-password route native", () => {
  renderSignIn();

  fireEvent.press(screen.getByRole("radio", { name: "شماره موبایل" }));
  expect(screen.getByPlaceholderText("۰۹۱۲۳۴۵۶۷۸۹")).toBeTruthy();
  expect(screen.queryByPlaceholderText("name@example.com")).toBeNull();

  fireEvent.press(screen.getByRole("radio", { name: "ایمیل" }));
  fireEvent.press(screen.getByRole("button", { name: "فراموشی رمز عبور؟" }));

  expect(mockPush).toHaveBeenCalledWith({ pathname: "/auth/forgot-password", params: undefined });
});
