import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { ApiError } from "../../shared/apiClient";
import * as api from "./api";
import { ForgotPasswordPage } from "./ForgotPasswordPage";
import { ResetPasswordPage } from "./ResetPasswordPage";

afterEach(() => vi.restoreAllMocks());

it("submits forgot password without revealing whether the email exists", async () => {
  vi.spyOn(api, "forgotPassword").mockResolvedValue({ message: "accepted" });
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <ForgotPasswordPage />
    </MemoryRouter>,
  );

  await user.type(screen.getByLabelText("ایمیل"), "unknown@example.com");
  await user.click(screen.getByRole("button", { name: "ارسال لینک بازیابی" }));

  expect(api.forgotPassword).toHaveBeenCalledWith("unknown@example.com");
  expect(await screen.findByRole("status")).toHaveTextContent(
    "اگر حسابی با این ایمیل وجود داشته باشد، لینک بازیابی ارسال شده است.",
  );
});

it("resets the password with the token from the URL", async () => {
  vi.spyOn(api, "resetPassword").mockResolvedValue();
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/reset-password?token=raw-token"]}>
      <ResetPasswordPage />
    </MemoryRouter>,
  );

  await user.type(screen.getByLabelText("رمز عبور جدید"), "new secure password");
  await user.type(screen.getByLabelText("تکرار رمز عبور جدید"), "new secure password");
  await user.click(screen.getByRole("button", { name: "ذخیره رمز عبور جدید" }));

  expect(api.resetPassword).toHaveBeenCalledWith("raw-token", "new secure password");
  expect(await screen.findByRole("status")).toHaveTextContent("رمز عبور با موفقیت تغییر کرد");
  expect(screen.getByRole("link", { name: "بازگشت به ورود" })).toHaveAttribute(
    "href",
    "/login",
  );
});

it("rejects mismatched passwords before calling the API", async () => {
  vi.spyOn(api, "resetPassword").mockResolvedValue();
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/reset-password?token=raw-token"]}>
      <ResetPasswordPage />
    </MemoryRouter>,
  );

  await user.type(screen.getByLabelText("رمز عبور جدید"), "new secure password");
  await user.type(screen.getByLabelText("تکرار رمز عبور جدید"), "different password");
  await user.click(screen.getByRole("button", { name: "ذخیره رمز عبور جدید" }));

  expect(api.resetPassword).not.toHaveBeenCalled();
  expect(screen.getByRole("alert")).toHaveTextContent("رمزها یکسان نیستند");
});

it("shows the same message for invalid, expired, and reused reset tokens", async () => {
  vi.spyOn(api, "resetPassword").mockRejectedValue(
    new ApiError(400, "Invalid or expired reset token"),
  );
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/reset-password?token=reused-token"]}>
      <ResetPasswordPage />
    </MemoryRouter>,
  );

  await user.type(screen.getByLabelText("رمز عبور جدید"), "new secure password");
  await user.type(screen.getByLabelText("تکرار رمز عبور جدید"), "new secure password");
  await user.click(screen.getByRole("button", { name: "ذخیره رمز عبور جدید" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "لینک بازیابی معتبر نیست یا منقضی شده است.",
  );
});
