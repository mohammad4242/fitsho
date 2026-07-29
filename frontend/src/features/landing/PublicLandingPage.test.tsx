import { render, screen, waitFor } from "@testing-library/react";
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

it("gives every landing chapter a registration CTA", () => {
  render(
    <MemoryRouter>
      <PublicLandingPage />
    </MemoryRouter>,
  );

  const ctas = screen.getAllByRole("link", { name: "شروع رایگان" });
  expect(ctas).toHaveLength(3);
  ctas.forEach((cta) => expect(cta).toHaveAttribute("href", "/register"));
});

it("activates the chapter entering the viewport", async () => {
  render(
    <MemoryRouter>
      <PublicLandingPage />
    </MemoryRouter>,
  );

  const planScene = document.getElementById("landing-plan");
  if (planScene === null) throw new Error("expected plan scene");
  observers[0]([
    { isIntersecting: true, target: planScene } as unknown as IntersectionObserverEntry,
  ]);

  await waitFor(() => expect(planScene).toHaveAttribute("data-active", "true"));
});

it("uses stills for all scenes when reduced motion is requested", () => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true })));

  render(
    <MemoryRouter>
      <PublicLandingPage />
    </MemoryRouter>,
  );

  expect(screen.getAllByRole("img")).toHaveLength(3);
});
