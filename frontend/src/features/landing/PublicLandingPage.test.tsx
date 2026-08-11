import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { PublicLandingPage } from "./PublicLandingPage";

function stubMotion(reduced: boolean) {
  vi.stubGlobal("matchMedia", vi.fn(() => ({
    matches: reduced,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })));
}

beforeEach(async () => {
  await i18n.changeLanguage("fa");
  stubMotion(false);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

it("leads with the cinematic Fitsho film and a focused Persian promise", () => {
  render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  const hero = screen.getByRole("region", { name: "هر بدن، برنامه خودش را می‌خواهد." });
  expect(within(hero).getByRole("heading", { name: "هر بدن، برنامه خودش را می‌خواهد." })).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: "برنامه من را بساز" })[0]).toHaveAttribute("href", "/get-started");
  expect(screen.getByTestId("landing-film")).toHaveAttribute("autoplay");
  expect(screen.getByTestId("landing-film")).toHaveProperty("muted", true);
  expect(screen.getByTestId("landing-film")).toHaveAttribute("playsinline");
  expect(screen.getByTestId("landing-film")).toHaveAttribute("loop");
});

it("switches the complete landing direction and primary copy to English", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  await user.click(screen.getByRole("button", { name: "English" }));

  await waitFor(() => expect(screen.getByRole("heading", { name: "Every body needs its own plan." })).toBeInTheDocument());
  expect(screen.getByRole("main")).toHaveAttribute("dir", "ltr");
  expect(screen.getByRole("heading", { name: "Get Started" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Get Started" })).toHaveAttribute("href", "/get-started");
  expect(screen.getByText("Estimate from your meal photo")).toBeInTheDocument();
  expect(screen.getAllByText("Shoulders").length).toBeGreaterThanOrEqual(1);
});

it("presents coach and physician supervision with schematic documents", () => {
  render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  const training = screen.getByRole("region", { name: "برنامه تمرینی، تحت نظر مربی" });
  const nutrition = screen.getByRole("region", { name: "برنامه تغذیه، تحت نظر پزشک" });
  expect(within(training).getByText("TRAINING")).toBeInTheDocument();
  expect(within(training).getByText("Coach supervised")).toBeInTheDocument();
  expect(within(nutrition).getByText("NUTRITION")).toBeInTheDocument();
  expect(within(nutrition).getByText("Physician supervised")).toBeInTheDocument();
  expect(screen.getAllByTestId("verification-seal")).toHaveLength(2);
  expect(screen.getAllByTestId("plan-document")).toHaveLength(2);
  screen.getAllByTestId("plan-document").forEach((document) => {
    expect(document.querySelectorAll(".plan-paper__group")).toHaveLength(3);
  });
  expect(screen.queryByText("Bench Press")).not.toBeInTheDocument();
});

it("continues nutrition into an estimated meal-photo analysis", () => {
  render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  const meal = screen.getByRole("region", { name: "تحلیل عکس غذا" });
  expect(within(meal).getByTestId("meal-photo")).toHaveAttribute(
    "src",
    expect.stringContaining("food"),
  );
  expect(within(meal).getByTestId("meal-scan-line")).toBeInTheDocument();
  expect(within(meal).getByText("≈ ۶۴۰ kcal")).toBeInTheDocument();
  expect(within(meal).getByText("تخمین از روی عکس غذا")).toBeInTheDocument();
  expect(within(meal).getByText("پروتئین")).toBeInTheDocument();
  expect(within(meal).getByText("کربوهیدرات")).toBeInTheDocument();
  expect(within(meal).getByText("چربی")).toBeInTheDocument();
});

it("reveals the four-stage process in its required order without percentages", () => {
  render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  const process = screen.getByRole("region", { name: "فیتشو چگونه برنامه تو را می‌سازد" });
  expect(within(process).getAllByRole("listitem").map((item) => item.dataset.stage)).toEqual([
    "understand", "plan", "train", "adapt",
  ]);
  expect(within(process).queryByText(/%|٪/)).not.toBeInTheDocument();
  expect(within(process).getByText("تو را می‌شناسیم")).toBeInTheDocument();
  expect(within(process).getByText("برنامه‌ات را می‌سازیم")).toBeInTheDocument();
});

it("scans the supplied analysis photo before the interactive body result", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  expect(screen.getByRole("heading", { name: "یک عکس. یک نگاه دقیق‌تر به بدنت." })).toBeInTheDocument();
  expect(screen.getByTestId("body-analysis-photo")).toHaveAttribute(
    "src",
    expect.stringContaining("analyze"),
  );
  expect(screen.getByTestId("body-analysis-scan-line")).toBeInTheDocument();
  expect(screen.getByTestId("fitsho-body-intelligence")).toHaveAttribute(
    "src",
    expect.stringContaining("body"),
  );
  const shoulders = screen.getByRole("button", { name: "سرشانه" });
  const back = screen.getByRole("button", { name: "پشت" });
  const bodyInterface = screen.getByTestId("body-interface");
  const shoulderHighlight = bodyInterface.querySelector('[data-region="shoulders"]');
  const backHighlight = bodyInterface.querySelector('[data-region="back"]');
  expect(shoulders).toHaveAttribute("aria-pressed", "true");
  expect(shoulderHighlight).toHaveAttribute("data-active", "true");
  expect(backHighlight).toHaveAttribute("data-active", "false");

  await user.click(back);

  expect(back).toHaveAttribute("aria-pressed", "true");
  expect(shoulders).toHaveAttribute("aria-pressed", "false");
  expect(shoulderHighlight).toHaveAttribute("data-active", "false");
  expect(backHighlight).toHaveAttribute("data-active", "true");
  expect(screen.getByRole("status")).toHaveTextContent("پشت");

  await user.hover(shoulders);

  expect(shoulders).toHaveAttribute("aria-pressed", "true");
  expect(back).toHaveAttribute("aria-pressed", "false");
});

it("removes generic late sections and ends body intelligence with a minimal start action", () => {
  const { container } = render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  expect(screen.queryByText("یک محصول، یک زبان")).not.toBeInTheDocument();
  expect(screen.queryByText("همان تجربه‌ای که بعد از ورود ادامه پیدا می‌کند.")).not.toBeInTheDocument();
  expect(screen.queryByText("برنامه‌ای که ثابت نمی‌ماند")).not.toBeInTheDocument();
  expect(screen.queryByText("بدنت تغییر می‌کند. برنامه‌ات هم باید تغییر کند.")).not.toBeInTheDocument();

  const sections = [...container.querySelectorAll("main > section")];
  expect(sections.map((section) => section.className)).toEqual([
    "cinematic-story",
    "process-story",
    "body-intelligence",
    "landing-final",
  ]);
  expect(screen.getByRole("heading", { name: "شروع کن" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "شروع کن" })).toHaveAttribute("href", "/get-started");
});

it("keeps all content visible when reduced motion is requested", () => {
  vi.unstubAllGlobals();
  stubMotion(true);
  render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  expect(screen.getByRole("main")).toHaveAttribute("data-reduced-motion", "true");
  expect(screen.getByRole("heading", { name: "هر بدن، برنامه خودش را می‌خواهد." })).toBeVisible();
  expect(screen.getByRole("heading", { name: "شروع کن" })).toBeVisible();
  expect(screen.getByText("≈ ۶۴۰ kcal")).toBeVisible();
});

it("opens a compact menu with onboarding and sign-in routes", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  await user.click(screen.getByRole("button", { name: "باز کردن منو" }));

  const menu = screen.getByRole("dialog", { name: "منوی اصلی" });
  expect(within(menu).getByRole("link", { name: "ساخت برنامه" })).toHaveAttribute("href", "/get-started");
  expect(within(menu).getByRole("link", { name: "ورود" })).toHaveAttribute("href", "/login");
});
