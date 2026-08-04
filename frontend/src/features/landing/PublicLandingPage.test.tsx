import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { PublicLandingPage } from "./PublicLandingPage";

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
  expect(screen.getByLabelText("شبکه‌های اجتماعی")).toHaveTextContent("اینستاگرام");
  expect(screen.getByLabelText("شبکه‌های اجتماعی")).toHaveTextContent("تلگرام");
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
