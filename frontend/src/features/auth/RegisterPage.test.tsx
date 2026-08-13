import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  register: vi.fn(),
}));

vi.mock("./AuthContext", () => ({
  useAuth: () => ({ register: auth.register }),
}));

import { RegisterPage } from "./RegisterPage";

beforeEach(() => auth.register.mockReset());

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/register"]}>
      <Routes>
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/dashboard" element={<div>dashboard reached</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

it("keeps registration controls usable without promotional media", () => {
  renderPage();

  expect(screen.queryByTestId("auth-training-accent")).not.toBeInTheDocument();
  expect(document.querySelector(".brand-panel")).not.toBeInTheDocument();
  expect(screen.getByLabelText("ایمیل")).toBeVisible();
  expect(screen.getByRole("button", { name: "ساخت حساب" })).toBeEnabled();
});

it("does not submit when password confirmation differs", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.type(screen.getByLabelText("ایمیل"), "user@example.com");
  await user.type(screen.getByLabelText("رمز عبور"), "long password");
  await user.type(screen.getByLabelText("تکرار رمز عبور"), "different password");
  await user.click(screen.getByRole("button", { name: "ساخت حساب" }));

  expect(auth.register).not.toHaveBeenCalled();
  expect(screen.getByRole("alert")).toHaveTextContent("رمزها یکسان نیستند");
});

it("registers and navigates to the protected dashboard", async () => {
  auth.register.mockResolvedValue(undefined);
  const user = userEvent.setup();
  renderPage();

  await user.type(screen.getByLabelText("ایمیل"), "user@example.com");
  await user.type(screen.getByLabelText("رمز عبور"), "long password");
  await user.type(screen.getByLabelText("تکرار رمز عبور"), "long password");
  await user.click(screen.getByRole("button", { name: "ساخت حساب" }));

  expect(auth.register).toHaveBeenCalledWith({
    email: "user@example.com",
    password: "long password",
  });
  expect(await screen.findByText("dashboard reached")).toBeInTheDocument();
});
