import { act, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("../../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../../auth/GoogleSignIn", () => ({ useGoogleSignIn: jest.fn() }));

import { useGoogleSignIn } from "../../auth/GoogleSignIn";
import { useMobileAuth } from "../../auth/MobileAuthProvider";
import { PublicAccountStep } from "./PublicAccountStep";

const mockUseGoogleSignIn = jest.mocked(useGoogleSignIn);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
type MockAuth = {
  busy: boolean;
  register: jest.Mock<(credentials: { email: string; password: string }) => Promise<unknown>>;
  sendPhoneOtp: jest.Mock<(phoneNumber: string) => Promise<{ retry_after_seconds: number }>>;
  signInWithGoogle: jest.Mock<(credential: string) => Promise<unknown>>;
  signInWithPassword: jest.Mock<(credentials: { email: string; password: string }) => Promise<unknown>>;
  user: null;
  verifyPhoneOtp: jest.Mock<(phoneNumber: string, code: string) => Promise<unknown>>;
};
let mockAuth: MockAuth;
let mockGoogleCredential: jest.Mock<() => Promise<string>>;

function renderAccount(onAuthenticated = jest.fn(), onEdit = jest.fn()) {
  return render(
    <SafeAreaProvider
      initialMetrics={{
        frame: { height: 800, width: 390, x: 0, y: 0 },
        insets: { bottom: 0, left: 0, right: 0, top: 0 },
      }}
    >
      <PublicAccountStep mode="training" onAuthenticated={onAuthenticated} onEdit={onEdit} />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  mockAuth = {
    busy: false,
    register: jest.fn<MockAuth["register"]>().mockResolvedValue({}),
    sendPhoneOtp: jest.fn<MockAuth["sendPhoneOtp"]>().mockResolvedValue({ retry_after_seconds: 2 }),
    signInWithGoogle: jest.fn<MockAuth["signInWithGoogle"]>().mockResolvedValue({}),
    signInWithPassword: jest.fn<MockAuth["signInWithPassword"]>().mockResolvedValue({}),
    user: null,
    verifyPhoneOtp: jest.fn<MockAuth["verifyPhoneOtp"]>().mockResolvedValue({}),
  };
  mockGoogleCredential = jest.fn<() => Promise<string>>().mockResolvedValue("google-credential");
  mockUseMobileAuth.mockReturnValue(mockAuth as never);
  mockUseGoogleSignIn.mockReturnValue({
    available: true,
    ready: true,
    signIn: mockGoogleCredential,
  });
});

test("matches the Web final account hierarchy and email registration handoff", async () => {
  const onAuthenticated = jest.fn();
  const onEdit = jest.fn();
  renderAccount(onAuthenticated, onEdit);

  expect(screen.getByText("آخرین قدم")).toBeTruthy();
  expect(screen.getByRole("header", { name: "حالا حسابت را بساز" })).toBeTruthy();
  expect(screen.getByText("مسیر امن انتقال اطلاعات")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Apple به‌زودی" })).toBeDisabled();

  fireEvent.press(screen.getByRole("button", { name: "بازگشت و ویرایش پاسخ‌ها" }));
  expect(onEdit).toHaveBeenCalledTimes(1);

  fireEvent.changeText(screen.getAllByLabelText("ایمیل")[1], "person@example.com");
  fireEvent.changeText(screen.getByLabelText("رمز عبور"), "abcdefgh");
  fireEvent.changeText(screen.getByLabelText("تکرار رمز عبور"), "abcdefgh");
  fireEvent.press(screen.getByRole("button", { name: "ساخت حساب و ذخیره پاسخ‌ها" }));

  await waitFor(() => expect(mockAuth.register).toHaveBeenCalledWith({ email: "person@example.com", password: "abcdefgh" }));
  expect(onAuthenticated).toHaveBeenCalledTimes(1);
});

test("supports existing-account login, Google, and inline phone OTP resend", async () => {
  jest.useFakeTimers();
  try {
    const onAuthenticated = jest.fn();
    renderAccount(onAuthenticated);

    fireEvent.press(screen.getByRole("button", { name: "قبلاً حساب ساخته‌ام" }));
    expect(screen.queryByLabelText("تکرار رمز عبور")).toBeNull();
    fireEvent.changeText(screen.getAllByLabelText("ایمیل")[1], "person@example.com");
    fireEvent.changeText(screen.getByLabelText("رمز عبور"), "abcdefgh");
    fireEvent.press(screen.getByRole("button", { name: "ورود و ذخیره پاسخ‌ها" }));
    await waitFor(() => expect(mockAuth.signInWithPassword).toHaveBeenCalledWith({ email: "person@example.com", password: "abcdefgh" }));

    fireEvent.press(screen.getByRole("tab", { name: "شماره تلفن" }));
    fireEvent.changeText(screen.getByPlaceholderText("۰۹۱۲۳۴۵۶۷۸۹"), "09123456789");
    fireEvent.press(screen.getByRole("button", { name: "ارسال کد ورود" }));
    await waitFor(() => expect(screen.getByLabelText("کد ورود")).toBeTruthy());
    expect(mockAuth.sendPhoneOtp).toHaveBeenCalledWith("09123456789");

    act(() => jest.advanceTimersByTime(2_000));
    fireEvent.press(screen.getByRole("button", { name: "ارسال دوباره کد" }));
    await waitFor(() => expect(mockAuth.sendPhoneOtp).toHaveBeenCalledTimes(2));

    fireEvent.changeText(screen.getByLabelText("کد ورود"), "123456");
    fireEvent.press(screen.getByRole("button", { name: "تأیید و ذخیره پاسخ‌ها" }));
    await waitFor(() => expect(mockAuth.verifyPhoneOtp).toHaveBeenCalledWith("09123456789", "123456"));

    fireEvent.press(screen.getByRole("tab", { name: "ایمیل" }));
    fireEvent.press(screen.getByRole("button", { name: "Google" }));
    await waitFor(() => expect(mockAuth.signInWithGoogle).toHaveBeenCalledWith("google-credential"));
    expect(onAuthenticated).toHaveBeenCalled();
  } finally {
    jest.useRealTimers();
  }
});
