import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { AuthProvider } from "./AuthContext";
import { RegisterPage } from "./RegisterPage";

afterEach(() => vi.restoreAllMocks());

it("shows a retryable localized message when the server cannot be reached", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
    .mockImplementationOnce(
      () =>
        new Promise<Response>((_resolve, reject) => {
          queueMicrotask(() => reject(new TypeError("network failure")));
        }),
    );
  const user = userEvent.setup();
  render(
    <AuthProvider>
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    </AuthProvider>,
  );
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

  await user.type(screen.getByLabelText("ایمیل"), "user@example.com");
  await user.type(screen.getByLabelText("رمز عبور"), "long password");
  await user.type(screen.getByLabelText("تکرار رمز عبور"), "long password");
  await user.click(screen.getByRole("button", { name: "ساخت حساب" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "ارتباط با سرور برقرار نشد. دوباره تلاش کن.",
  );
  expect(screen.queryByText("long password")).not.toBeInTheDocument();
});
