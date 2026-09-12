import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../i18n";

const serviceWorker = vi.hoisted(() => ({
  needRefresh: false,
  setNeedRefresh: vi.fn(),
  updateServiceWorker: vi.fn(),
}));

vi.mock("virtual:pwa-register/react", () => ({
  useRegisterSW: () => ({
    needRefresh: [serviceWorker.needRefresh, serviceWorker.setNeedRefresh],
    updateServiceWorker: serviceWorker.updateServiceWorker,
  }),
}));

import { PwaUpdatePrompt } from "./PwaUpdatePrompt";

describe("PwaUpdatePrompt", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("fa");
    serviceWorker.needRefresh = false;
    serviceWorker.setNeedRefresh.mockReset();
    serviceWorker.updateServiceWorker.mockReset();
    serviceWorker.updateServiceWorker.mockResolvedValue(undefined);
  });

  afterEach(() => {
    serviceWorker.needRefresh = false;
  });

  it("does not render when no update is available", () => {
    render(<PwaUpdatePrompt />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders the Persian update prompt and actions when an update is available", () => {
    serviceWorker.needRefresh = true;
    render(<PwaUpdatePrompt />);

    const prompt = screen.getByRole("dialog", { name: "نسخه جدید فیتیشن آماده است" });
    expect(prompt).toHaveAttribute("aria-describedby", "pwa-update-description");
    expect(screen.getByText("نسخه جدید فیتیشن آماده است")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "به‌روزرسانی" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "بعداً" })).toBeInTheDocument();
  });

  it("dismisses only the prompt when Later is selected", async () => {
    serviceWorker.needRefresh = true;
    const user = userEvent.setup();
    render(
      <>
        <main data-testid="current-route">Current route</main>
        <PwaUpdatePrompt />
      </>,
    );

    await user.click(screen.getByRole("button", { name: "بعداً" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("current-route")).toBeInTheDocument();
    expect(serviceWorker.setNeedRefresh).not.toHaveBeenCalled();
    expect(serviceWorker.updateServiceWorker).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe("/");
  });

  it("activates the waiting service worker when Update is selected", async () => {
    serviceWorker.needRefresh = true;
    const user = userEvent.setup();
    render(<PwaUpdatePrompt />);

    await user.click(screen.getByRole("button", { name: "به‌روزرسانی" }));

    expect(serviceWorker.updateServiceWorker).toHaveBeenCalledOnce();
    expect(serviceWorker.updateServiceWorker).toHaveBeenCalledWith(true);
  });

  it("ignores repeated Update clicks while activation is pending", async () => {
    serviceWorker.needRefresh = true;
    let resolveUpdate!: () => void;
    serviceWorker.updateServiceWorker.mockReturnValue(new Promise<void>((resolve) => {
      resolveUpdate = resolve;
    }));
    const user = userEvent.setup();
    render(<PwaUpdatePrompt />);

    const updateButton = screen.getByRole("button", { name: "به‌روزرسانی" });
    await user.click(updateButton);
    await waitFor(() => expect(updateButton).toBeDisabled());
    await user.click(updateButton);

    expect(serviceWorker.updateServiceWorker).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "بعداً" })).toBeDisabled();

    resolveUpdate();
  });

  it("restores the prompt after an update failure and allows a retry", async () => {
    serviceWorker.needRefresh = true;
    serviceWorker.updateServiceWorker
      .mockRejectedValueOnce(new Error("activation failed"))
      .mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<PwaUpdatePrompt />);

    const updateButton = screen.getByRole("button", { name: "به‌روزرسانی" });
    await user.click(updateButton);
    await waitFor(() => expect(updateButton).not.toBeDisabled());

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(updateButton);
    expect(serviceWorker.updateServiceWorker).toHaveBeenCalledTimes(2);
  });

  it("shows the prompt again after a Later dismissal on remount", async () => {
    serviceWorker.needRefresh = true;
    const user = userEvent.setup();
    const rendered = render(<PwaUpdatePrompt />);

    await user.click(screen.getByRole("button", { name: "بعداً" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    rendered.unmount();
    render(<PwaUpdatePrompt />);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(serviceWorker.setNeedRefresh).not.toHaveBeenCalled();
  });

  it("shows a later update after the needRefresh signal clears and returns", async () => {
    serviceWorker.needRefresh = true;
    const user = userEvent.setup();
    const rendered = render(<PwaUpdatePrompt />);

    await user.click(screen.getByRole("button", { name: "بعداً" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    serviceWorker.needRefresh = false;
    rendered.rerender(<PwaUpdatePrompt />);
    serviceWorker.needRefresh = true;
    rendered.rerender(<PwaUpdatePrompt />);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("preserves English copy", async () => {
    await i18n.changeLanguage("en");
    serviceWorker.needRefresh = true;
    render(<PwaUpdatePrompt />);

    expect(screen.getByRole("dialog", { name: "A new version of Fitician is available" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Update" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Later" })).toBeInTheDocument();
  });
});
