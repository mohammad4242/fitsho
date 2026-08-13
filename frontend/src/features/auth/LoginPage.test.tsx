import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { AuthProvider } from "./AuthContext";
import { LoginPage } from "./LoginPage";

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function renderPage() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<div>dashboard reached</div>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

it("keeps the login form usable without promotional media", () => {
  renderPage();

  expect(screen.queryByTestId("auth-training-accent")).not.toBeInTheDocument();
  expect(document.querySelector(".brand-panel")).not.toBeInTheDocument();
  expect(document.querySelector(".auth-shell")).toHaveClass("fitsho-page");
  expect(screen.getByLabelText("ایمیل")).toBeVisible();
  expect(screen.getByRole("button", { name: "ورود به فیتشو" })).toBeEnabled();
  expect(screen.getByRole("tab", { name: "ایمیل" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tab", { name: "شماره موبایل" })).toBeVisible();
  expect(screen.getByRole("link", { name: "فراموشی رمز عبور؟" })).toHaveAttribute(
    "href",
    "/forgot-password",
  );
});

it("shows a clear message for invalid credentials", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Invalid email or password" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
  const user = userEvent.setup();
  renderPage();
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

  await user.type(screen.getByLabelText("ایمیل"), "user@example.com");
  await user.type(screen.getByLabelText("رمز عبور"), "wrong password");
  await user.click(screen.getByRole("button", { name: "ورود به فیتشو" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "ایمیل یا رمز عبور درست نیست",
  );
});

it("sends an OTP and exposes countdown and resend state", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ message: "accepted", retry_after_seconds: 60 }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ message: "accepted", retry_after_seconds: 60 }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );
  renderPage();
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

  vi.useFakeTimers();
  fireEvent.click(screen.getByRole("tab", { name: "شماره موبایل" }));
  fireEvent.change(screen.getByLabelText("شماره موبایل"), {
    target: { value: "09123456789" },
  });
  fireEvent.click(screen.getByRole("button", { name: "ارسال کد ورود" }));
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });

  expect(screen.getByLabelText("کد ورود")).toBeVisible();
  const resend = screen.getByRole("button", { name: /ارسال مجدد/ });
  expect(resend).toBeDisabled();
  expect(resend).toHaveTextContent("۶۰");

  act(() => vi.advanceTimersByTime(60_000));
  expect(resend).toBeEnabled();
  fireEvent.click(resend);
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
  expect(fetch).toHaveBeenCalledTimes(3);
});

it("verifies the OTP and reaches the authenticated flow", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ message: "accepted", retry_after_seconds: 60 }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    )
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "phone-user",
          email: null,
          phone_number: "+989123456789",
          created_at: "2026-08-13T00:00:00Z",
          is_admin: false,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
  const user = userEvent.setup();
  renderPage();
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

  await user.click(screen.getByRole("tab", { name: "شماره موبایل" }));
  await user.type(screen.getByLabelText("شماره موبایل"), "09123456789");
  await user.click(screen.getByRole("button", { name: "ارسال کد ورود" }));
  await user.type(await screen.findByLabelText("کد ورود"), "123456");
  await user.click(screen.getByRole("button", { name: "تأیید و ورود" }));

  expect(await screen.findByText("dashboard reached")).toBeVisible();
});

it("shows a generic error for invalid or expired OTP codes", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ message: "accepted", retry_after_seconds: 60 }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Invalid or expired OTP" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
  const user = userEvent.setup();
  renderPage();
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

  await user.click(screen.getByRole("tab", { name: "شماره موبایل" }));
  await user.type(screen.getByLabelText("شماره موبایل"), "09123456789");
  await user.click(screen.getByRole("button", { name: "ارسال کد ورود" }));
  await user.type(await screen.findByLabelText("کد ورود"), "000000");
  await user.click(screen.getByRole("button", { name: "تأیید و ورود" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "کد واردشده معتبر نیست یا منقضی شده است",
  );
});
