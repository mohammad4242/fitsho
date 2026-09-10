import { act, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
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
import { authStyles } from "./authStyles";
import RegisterScreen from "../app/(auth)/auth/register";
import SignInScreen from "../app/(auth)/auth/sign-in";

const mockPush = jest.fn();
const mockReplace = jest.fn();
type MockAuth = {
  busy: boolean;
  register: jest.Mock<(credentials: { email: string; password: string }) => Promise<unknown>>;
  sendPhoneOtp: jest.Mock<(phoneNumber: string) => Promise<{ retry_after_seconds: number }>>;
  sessionExpired: boolean;
  signInWithGoogle: jest.Mock<(credential: string) => Promise<unknown>>;
  signInWithPassword: jest.Mock<(credentials: { email: string; password: string }) => Promise<unknown>>;
  startupError: string | null;
  verifyPhoneOtp: jest.Mock<(phoneNumber: string, code: string) => Promise<unknown>>;
};
let mockAuth: MockAuth;
let mockGoogleCredential: jest.Mock<() => Promise<string>>;
const mockUseLocalSearchParams = jest.mocked(useLocalSearchParams);
const mockUseRouter = jest.mocked(useRouter);
const mockUseGoogleSignIn = jest.mocked(useGoogleSignIn);
const mockUseMobileAuth = jest.mocked(useMobileAuth);

function renderScreen(screenComponent: React.ReactElement) {
  return render(
    <SafeAreaProvider
      initialMetrics={{
        frame: { height: 800, width: 390, x: 0, y: 0 },
        insets: { bottom: 0, left: 0, right: 0, top: 0 },
      }}
    >
      {screenComponent}
    </SafeAreaProvider>,
  );
}

function renderSignIn() {
  return renderScreen(<SignInScreen />);
}

function renderRegister() {
  return renderScreen(<RegisterScreen />);
}

beforeEach(() => {
  mockPush.mockClear();
  mockReplace.mockClear();
  mockAuth = {
    busy: false,
    register: jest.fn<MockAuth["register"]>().mockResolvedValue({}),
    sendPhoneOtp: jest.fn<MockAuth["sendPhoneOtp"]>().mockResolvedValue({ retry_after_seconds: 2 }),
    sessionExpired: false,
    signInWithGoogle: jest.fn<MockAuth["signInWithGoogle"]>().mockResolvedValue({}),
    signInWithPassword: jest.fn<MockAuth["signInWithPassword"]>().mockResolvedValue({}),
    startupError: null,
    verifyPhoneOtp: jest.fn<MockAuth["verifyPhoneOtp"]>().mockResolvedValue({}),
  };
  mockGoogleCredential = jest.fn<() => Promise<string>>().mockResolvedValue("google-credential");
  mockUseRouter.mockReturnValue({ push: mockPush, replace: mockReplace } as never);
  mockUseLocalSearchParams.mockReturnValue({} as never);
  mockUseGoogleSignIn.mockReturnValue({
    available: true,
    ready: true,
    signIn: mockGoogleCredential,
  });
  mockUseMobileAuth.mockReturnValue(mockAuth as never);
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

test("uses the quiet Web-aligned scaffold without the old decorative accent rule", () => {
  expect(authStyles.brand).toBeDefined();
  expect("accentRule" in authStyles).toBe(false);
});

test("keeps the phone method inline and preserves the forgot-password source", async () => {
  mockUseLocalSearchParams.mockReturnValue({ source: "public-onboarding" } as never);
  renderSignIn();

  fireEvent.press(screen.getByRole("radio", { name: "شماره موبایل" }));
  expect(screen.getByPlaceholderText("۰۹۱۲۳۴۵۶۷۸۹")).toBeTruthy();
  expect(screen.queryByPlaceholderText("name@example.com")).toBeNull();

  fireEvent.changeText(screen.getByPlaceholderText("۰۹۱۲۳۴۵۶۷۸۹"), "09123456789");
  fireEvent.press(screen.getByRole("button", { name: "ارسال کد ورود" }));
  await waitFor(() => expect(mockAuth.sendPhoneOtp).toHaveBeenCalledWith("09123456789"));
  expect(mockPush).not.toHaveBeenCalledWith("/auth/phone-otp");

  fireEvent.press(screen.getByRole("radio", { name: "ایمیل" }));
  fireEvent.press(screen.getByRole("button", { name: "فراموشی رمز عبور؟" }));

  expect(mockPush).toHaveBeenCalledWith({
    pathname: "/auth/forgot-password",
    params: { source: "public-onboarding" },
  });
});

test("submits the Web email login path to the public onboarding destination", async () => {
  mockUseLocalSearchParams.mockReturnValue({ source: "public-onboarding" } as never);
  renderSignIn();

  fireEvent.changeText(screen.getAllByLabelText("ایمیل")[1], "person@example.com");
  fireEvent.changeText(screen.getByLabelText("رمز عبور"), "abcdefgh");
  fireEvent.press(screen.getByRole("button", { name: "ورود به فیتشو" }));

  await waitFor(() => expect(mockAuth.signInWithPassword).toHaveBeenCalledWith({ email: "person@example.com", password: "abcdefgh" }));
  expect(mockReplace).toHaveBeenCalledWith({
    pathname: "/onboarding",
    params: { source: "public-onboarding" },
  });
});

test("renders inline OTP verification and resend countdown", async () => {
  jest.useFakeTimers();
  try {
    renderSignIn();
    fireEvent.press(screen.getByRole("radio", { name: "شماره موبایل" }));
    fireEvent.changeText(screen.getByPlaceholderText("۰۹۱۲۳۴۵۶۷۸۹"), "09123456789");
    fireEvent.press(screen.getByRole("button", { name: "ارسال کد ورود" }));

    await waitFor(() => expect(screen.getByLabelText("کد ورود")).toBeTruthy());
    expect(screen.getByText("ارسال مجدد تا ۲ ثانیه")).toBeTruthy();

    act(() => jest.advanceTimersByTime(2_000));
    fireEvent.press(screen.getByRole("button", { name: "ارسال مجدد کد" }));
    expect(mockAuth.sendPhoneOtp).toHaveBeenCalledTimes(2);

    fireEvent.changeText(screen.getByLabelText("کد ورود"), "123456");
    fireEvent.press(screen.getByRole("button", { name: "تأیید و ورود" }));
    await waitFor(() => expect(mockAuth.verifyPhoneOtp).toHaveBeenCalledWith("09123456789", "123456"));
  } finally {
    jest.useRealTimers();
  }
});

test("uses Google and keeps the public onboarding destination", async () => {
  mockUseLocalSearchParams.mockReturnValue({ source: "public-onboarding" } as never);
  renderSignIn();

  fireEvent.press(screen.getByRole("button", { name: "ادامه با گوگل" }));

  await waitFor(() => expect(mockAuth.signInWithGoogle).toHaveBeenCalledWith("google-credential"));
  expect(mockReplace).toHaveBeenCalledWith({
    pathname: "/onboarding",
    params: { source: "public-onboarding" },
  });
});

test("keeps Register in the Web field order and validates confirmation", async () => {
  renderRegister();

  expect(screen.getByLabelText("ایمیل")).toBeTruthy();
  expect(screen.getByLabelText("رمز عبور")).toBeTruthy();
  expect(screen.getByLabelText("تکرار رمز عبور")).toBeTruthy();
  expect(screen.getByText("حداقل ۸ نویسه")).toBeTruthy();

  fireEvent.changeText(screen.getByLabelText("رمز عبور"), "abcdefgh");
  fireEvent.changeText(screen.getByLabelText("تکرار رمز عبور"), "different");
  fireEvent.press(screen.getByRole("button", { name: "ساخت حساب" }));

  await waitFor(() => expect(screen.getByText("تکرار رمز عبور یکسان نیست.")).toBeTruthy());
  expect(mockAuth.register).not.toHaveBeenCalled();
});

test("preserves the public onboarding source through Register", async () => {
  mockUseLocalSearchParams.mockReturnValue({ source: "public-onboarding" } as never);
  renderRegister();

  fireEvent.changeText(screen.getByLabelText("ایمیل"), "person@example.com");
  fireEvent.changeText(screen.getByLabelText("رمز عبور"), "abcdefgh");
  fireEvent.changeText(screen.getByLabelText("تکرار رمز عبور"), "abcdefgh");
  fireEvent.press(screen.getByRole("button", { name: "ساخت حساب" }));

  await waitFor(() => expect(mockAuth.register).toHaveBeenCalledWith({ email: "person@example.com", password: "abcdefgh" }));
  expect(mockReplace).toHaveBeenCalledWith({
    pathname: "/onboarding",
    params: { source: "public-onboarding" },
  });
});
