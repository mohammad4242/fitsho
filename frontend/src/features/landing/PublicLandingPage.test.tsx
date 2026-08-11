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
  expect(screen.getAllByRole("link", { name: "Build my plan" }).length).toBeGreaterThanOrEqual(2);
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
  expect(screen.queryByText("Bench Press")).not.toBeInTheDocument();
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

it("uses the supplied body asset and updates interactive muscle callouts", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  expect(screen.getByTestId("fitsho-body-intelligence")).toHaveAttribute(
    "src",
    expect.stringContaining("body"),
  );
  const shoulders = screen.getByRole("button", { name: "سرشانه" });
  const back = screen.getByRole("button", { name: "پشت" });
  expect(shoulders).toHaveAttribute("aria-pressed", "true");

  await user.click(back);

  expect(back).toHaveAttribute("aria-pressed", "true");
  expect(shoulders).toHaveAttribute("aria-pressed", "false");
  expect(screen.getByRole("status")).toHaveTextContent("پشت");
});

it("previews real product areas and repeats the onboarding CTA", () => {
  render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  expect(screen.getByText("امروز")).toBeInTheDocument();
  expect(screen.getByText("برنامه تمرینی")).toBeInTheDocument();
  expect(screen.getByText("هدف تغذیه")).toBeInTheDocument();
  expect(screen.getByText("تحلیل بدن")).toBeInTheDocument();
  expect(screen.getByText("کاتالوگ غذا")).toBeInTheDocument();
  expect(screen.getByText("تمرین امروز")).toBeInTheDocument();
  expect(screen.getByText("۱۶۵ گرم پروتئین")).toBeInTheDocument();
  expect(screen.getByText("سرشانه · اولویت")).toBeInTheDocument();
  expect(screen.getByText("سینه مرغ")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "بدنت تغییر می‌کند. برنامه‌ات هم باید تغییر کند." })).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: "برنامه من را بساز" }).length).toBeGreaterThanOrEqual(2);
});

it("keeps all content visible when reduced motion is requested", () => {
  vi.unstubAllGlobals();
  stubMotion(true);
  render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  expect(screen.getByRole("main")).toHaveAttribute("data-reduced-motion", "true");
  expect(screen.getByRole("heading", { name: "هر بدن، برنامه خودش را می‌خواهد." })).toBeVisible();
  expect(screen.getByRole("heading", { name: "بدنت تغییر می‌کند. برنامه‌ات هم باید تغییر کند." })).toBeVisible();
});

it("opens a compact menu with onboarding and sign-in routes", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  await user.click(screen.getByRole("button", { name: "باز کردن منو" }));

  const menu = screen.getByRole("dialog", { name: "منوی اصلی" });
  expect(within(menu).getByRole("link", { name: "ساخت برنامه" })).toHaveAttribute("href", "/get-started");
  expect(within(menu).getByRole("link", { name: "ورود" })).toHaveAttribute("href", "/login");
});
