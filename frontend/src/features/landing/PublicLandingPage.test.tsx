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

it("leads with the approved Persian body-led product promise", () => {
  render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  const hero = screen.getByRole("region", { name: "هر بدن، برنامه خودش را می‌خواهد." });
  expect(within(hero).getByRole("heading", { name: "هر بدن، برنامه خودش را می‌خواهد." })).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: "برنامه من را بساز" })[0]).toHaveAttribute("href", "/get-started");
  expect(screen.getByTestId("fitsho-body-hero")).toHaveAttribute(
    "src",
    expect.stringContaining("fitsho-body-hero-3d"),
  );
  expect(within(hero).getByText("در حال ساخت برنامه فیتشو")).toBeInTheDocument();
  expect(within(hero).getByText("اطمینان")).toBeInTheDocument();
  expect(screen.queryByTestId("landing-film")).not.toBeInTheDocument();
  expect(screen.getAllByText("سرشانه").length).toBeGreaterThanOrEqual(2);
  expect(screen.getAllByText("۲۳۴۰ کیلوکالری").length).toBeGreaterThanOrEqual(2);
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

it("explains the real Fitsho inputs and ordered product progression", () => {
  render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  const inputs = screen.getByLabelText("نمونه ورودی‌های واقعی فیتشو");
  const transformation = inputs.closest(".landing-transformation");
  expect(transformation).not.toBeNull();
  expect(within(transformation as HTMLElement).getByLabelText("وضعیت ساخت برنامه فیتشو")).toBeInTheDocument();
  expect(screen.getByText("هدف")).toBeInTheDocument();
  expect(screen.getByText("سطح تجربه")).toBeInTheDocument();
  expect(screen.getAllByText("۴ روز در هفته").length).toBeGreaterThanOrEqual(2);
  expect(screen.getAllByText("۶۰ دقیقه").length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText("ملاحظات تمرینی")).toBeInTheDocument();
  expect(screen.getByText("درک")).toBeInTheDocument();
  expect(screen.getByText("برنامه")).toBeInTheDocument();
  expect(screen.getAllByText("تمرین").length).toBeGreaterThanOrEqual(2);
  expect(screen.getByText("تطبیق")).toBeInTheDocument();
});

it("uses the 3D body identity for the body-intelligence moment", () => {
  render(<MemoryRouter><PublicLandingPage /></MemoryRouter>);

  expect(screen.getByTestId("fitsho-body-intelligence")).toHaveAttribute(
    "src",
    expect.stringContaining("fitsho-body-hero-3d"),
  );
  expect(screen.getByTestId("fitsho-body-highlight")).toBeInTheDocument();
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
