import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { PublicLandingPage } from "./PublicLandingPage";
import i18n from "../../i18n";

type ObserverCallback = (entries: IntersectionObserverEntry[]) => void;

const observers: ObserverCallback[] = [];

class LandingIntersectionObserver {
  constructor(callback: ObserverCallback) {
    observers.push(callback);
  }

  disconnect = vi.fn();
  observe = vi.fn();
  takeRecords = vi.fn(() => []);
  unobserve = vi.fn();
}

beforeEach(() => {
  observers.length = 0;
  void i18n.changeLanguage("fa");
  vi.stubGlobal("IntersectionObserver", LandingIntersectionObserver);
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false })));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

it("uses one fixed film while the product story scrolls", () => {
  render(
    <MemoryRouter>
      <PublicLandingPage />
    </MemoryRouter>,
  );

  const video = screen.getByTestId("landing-film");
  expect(video).toHaveClass("landing-film");
  expect(video.querySelector("source")).toHaveAttribute("src", "/image&videos/landing.mp4");
  expect(screen.getByRole("link", { name: /شروع کن/i })).toHaveAttribute("href", "/get-started");
  expect(screen.getByText(/کم‌هزینه‌تر/)).toBeInTheDocument();
  expect(screen.queryByText("برای ادامه اسکرول کن ↓")).not.toBeInTheDocument();
});

it("renders the landing copy and direction in English after changing language", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <PublicLandingPage />
    </MemoryRouter>,
  );

  await user.click(screen.getByRole("button", { name: "English" }));

  await waitFor(() => expect(screen.getByRole("heading", { name: /Your body\.\s*Your path\./ })).toBeInTheDocument());
  expect(screen.getByRole("main")).toHaveAttribute("dir", "ltr");
  expect(screen.getByRole("link", { name: /Get started/i })).toBeInTheDocument();
});

it("shows stores and social destinations without inventing unavailable links", () => {
  render(
    <MemoryRouter>
      <PublicLandingPage />
    </MemoryRouter>,
  );

  expect(screen.getByText("Google Play")).toBeInTheDocument();
  expect(screen.getByText("کافه‌بازار")).toBeInTheDocument();
  expect(screen.getByText("App Store")).toBeInTheDocument();
  expect(screen.getByAltText("Google Play")).toBeInTheDocument();
  expect(screen.getByAltText("Cafe Bazaar")).toBeInTheDocument();
  expect(screen.getByAltText("App Store")).toBeInTheDocument();
});

it("reveals social destinations only when the final section enters view", () => {
  const { container } = render(
    <MemoryRouter>
      <PublicLandingPage />
    </MemoryRouter>,
  );

  expect(screen.queryByLabelText("شبکه‌های اجتماعی")).not.toBeInTheDocument();
  const downloadSection = container.querySelector("#download");
  expect(downloadSection).not.toBeNull();
  act(() => observers.forEach((callback) => callback([{ isIntersecting: true, target: downloadSection } as IntersectionObserverEntry])));

  const socialCard = screen.getByLabelText("شبکه‌های اجتماعی");
  expect(socialCard).toHaveClass("landing-social-card");
  expect(socialCard).toHaveClass("landing-social-card--fixed");
  expect(screen.queryByText("با فیتشو همراه بمان")).not.toBeInTheDocument();
  expect(socialCard).toHaveTextContent("اینستاگرام");
  expect(socialCard).toHaveTextContent("تلگرام");
  expect(screen.getByAltText("Instagram")).toBeInTheDocument();
  expect(screen.getByAltText("Telegram")).toBeInTheDocument();
  expect(screen.getByAltText("Facebook")).toBeInTheDocument();
  expect(screen.getByAltText("X")).toBeInTheDocument();
});

it("opens a menu with the upcoming articles item", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <PublicLandingPage />
    </MemoryRouter>,
  );

  await user.click(screen.getByRole("button", { name: "باز کردن منو" }));
  expect(screen.getByRole("dialog", { name: "منوی اصلی" })).toBeInTheDocument();
  expect(screen.getByText("مقالات روز دنیا")).toBeInTheDocument();
  expect(screen.getAllByText("به‌زودی").length).toBeGreaterThan(0);
});
