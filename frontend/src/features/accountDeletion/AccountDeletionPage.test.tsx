import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import "../../i18n";
import { ApiError } from "../../shared/apiClient";
import { AccountDeletionPage } from "./AccountDeletionPage";
import { PrivacyPolicyPage } from "./PrivacyPolicyPage";

const api = vi.hoisted(() => ({
  getAccountDeletionStatus: vi.fn(),
  requestAccountDeletion: vi.fn(),
  cancelAccountDeletion: vi.fn(),
}));
const auth = vi.hoisted(() => ({
  user: null as null | { email: string; phone_number: string | null },
  loading: false,
  logout: vi.fn(async () => undefined),
}));

vi.mock("./api", () => api);
vi.mock("../../features/auth/AuthContext", () => ({ useAuth: () => auth }));

const emptyStatus = {
  status: "none" as const,
  request_id: null,
  requested_at: null,
  reauthenticated_at: null,
  grace_period_ends_at: null,
  cancelled_at: null,
  completed_at: null,
};
const pendingStatus = {
  ...emptyStatus,
  status: "pending" as const,
  request_id: "018f0000-0000-7000-8000-000000000001",
  requested_at: "2026-09-08T10:00:00Z",
  reauthenticated_at: "2026-09-08T10:00:00Z",
  grace_period_ends_at: "2026-09-15T10:00:00Z",
};

beforeEach(() => {
  auth.user = null;
  auth.loading = false;
  auth.logout.mockClear();
  api.getAccountDeletionStatus.mockReset();
  api.requestAccountDeletion.mockReset();
  api.cancelAccountDeletion.mockReset();
});

function renderAccountPage(initialEntries = ["/delete-account"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/delete-account" element={<AccountDeletionPage />} />
        <Route path="/login" element={<div>صفحه ورود</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AccountDeletionPage", () => {
  it("provides account deletion access to signed-out visitors", () => {
    renderAccountPage();

    expect(screen.getByRole("heading", { name: "حذف حساب فیتشو" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "ورود برای ادامه" })).toHaveAttribute(
      "href",
      "/login?returnTo=%2Fdelete-account",
    );
    expect(screen.getByRole("link", { name: "سیاست حریم خصوصی" })).toHaveAttribute(
      "href",
      "/privacy",
    );
    expect(api.getAccountDeletionStatus).not.toHaveBeenCalled();
  });

  it("requests deletion only after the exact confirmation is entered", async () => {
    auth.user = { email: "member@example.com", phone_number: null };
    api.getAccountDeletionStatus.mockResolvedValue(emptyStatus);
    api.requestAccountDeletion.mockResolvedValue(pendingStatus);
    const user = userEvent.setup();
    renderAccountPage();

    await screen.findByLabelText("تأیید حذف");
    await user.type(screen.getByLabelText("تأیید حذف"), "DELETE");
    await user.click(screen.getByRole("button", { name: "ثبت درخواست حذف" }));

    await waitFor(() => expect(api.requestAccountDeletion).toHaveBeenCalledWith(undefined));
    expect(await screen.findByText("حساب برای حذف زمان‌بندی شد")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "لغو درخواست حذف" })).toBeInTheDocument();
  });

  it("cancels a pending deletion during the grace period", async () => {
    auth.user = { email: "member@example.com", phone_number: null };
    api.getAccountDeletionStatus.mockResolvedValue(pendingStatus);
    api.cancelAccountDeletion.mockResolvedValue({ ...pendingStatus, status: "cancelled" });
    const user = userEvent.setup();
    renderAccountPage();

    await screen.findByText("حساب برای حذف زمان‌بندی شد");
    await user.click(screen.getByRole("button", { name: "لغو درخواست حذف" }));

    await waitFor(() => expect(api.cancelAccountDeletion).toHaveBeenCalledOnce());
    expect(await screen.findByText("درخواست حذف لغو شد")).toBeInTheDocument();
  });

  it("offers a fresh login when a passwordless web session is old", async () => {
    auth.user = { email: "google@example.com", phone_number: null };
    api.getAccountDeletionStatus.mockResolvedValue(emptyStatus);
    api.requestAccountDeletion.mockRejectedValue(
      new ApiError(403, "RECENT_AUTHENTICATION_REQUIRED"),
    );
    const user = userEvent.setup();
    renderAccountPage();

    await screen.findByLabelText("تأیید حذف");
    await user.type(screen.getByLabelText("تأیید حذف"), "DELETE");
    await user.click(screen.getByRole("button", { name: "ثبت درخواست حذف" }));
    await screen.findByRole("button", { name: "ورود دوباره برای ادامه" });
    await user.click(screen.getByRole("button", { name: "ورود دوباره برای ادامه" }));

    await waitFor(() => expect(auth.logout).toHaveBeenCalledOnce());
    expect(await screen.findByText("صفحه ورود")).toBeInTheDocument();
  });
});

it("renders a public privacy policy with a deletion link", () => {
  render(
    <MemoryRouter initialEntries={["/privacy"]}>
      <PrivacyPolicyPage />
    </MemoryRouter>,
  );

  expect(screen.getByRole("heading", { name: "سیاست حریم خصوصی" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "حذف حساب" })).toHaveAttribute(
    "href",
    "/delete-account",
  );
  expect(screen.getByText(/تصاویر خصوصی بدن/)).toBeInTheDocument();
});
