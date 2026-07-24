import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { AuthProvider } from "./AuthContext";
import { LoginPage } from "./LoginPage";

afterEach(() => vi.restoreAllMocks());

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
