import { expect, it, vi } from "vitest";

import {
  AndroidBackCoordinator,
  type AndroidBackNavigation,
} from "./navigation/backBehavior";

function navigation(canGoBack: boolean) {
  return {
    canGoBack: () => canGoBack,
    exitApp: vi.fn(() => undefined),
    goBack: vi.fn(() => undefined),
  } satisfies AndroidBackNavigation;
}

it("handles overlay, wizard, and upload handlers in priority order", () => {
  const nav = navigation(true);
  const coordinator = new AndroidBackCoordinator(nav);
  const events: string[] = [];

  const removeUpload = coordinator.register("upload", () => {
    events.push("upload");
    return true;
  });
  const removeWizard = coordinator.register("wizard", () => {
    events.push("wizard");
    return true;
  });
  const removeOverlay = coordinator.register("overlay", () => {
    events.push("overlay");
    return true;
  });

  expect(coordinator.handleBack()).toBe(true);
  expect(events).toEqual(["overlay"]);
  removeOverlay();
  expect(coordinator.handleBack()).toBe(true);
  expect(events).toEqual(["overlay", "wizard"]);
  removeWizard();
  expect(coordinator.handleBack()).toBe(true);
  expect(events).toEqual(["overlay", "wizard", "upload"]);
  removeUpload();
  expect(coordinator.handleBack()).toBe(true);
  expect(nav.goBack).toHaveBeenCalledOnce();
  expect(nav.exitApp).not.toHaveBeenCalled();
});

it("continues past an inactive handler and pops the navigation stack", () => {
  const nav = navigation(true);
  const coordinator = new AndroidBackCoordinator(nav);

  coordinator.register("wizard", () => false);
  expect(coordinator.handleBack()).toBe(true);
  expect(nav.goBack).toHaveBeenCalledOnce();
  expect(nav.exitApp).not.toHaveBeenCalled();
});

it("exits only after every handler is inactive and the current route is root", () => {
  const nav = navigation(false);
  const coordinator = new AndroidBackCoordinator(nav);
  const handler = vi.fn(() => false);
  coordinator.register("overlay", handler);

  expect(coordinator.handleBack()).toBe(true);
  expect(handler).toHaveBeenCalledOnce();
  expect(nav.goBack).not.toHaveBeenCalled();
  expect(nav.exitApp).toHaveBeenCalledOnce();
});

it("stops invoking a handler after its registration is removed", () => {
  const nav = navigation(true);
  const coordinator = new AndroidBackCoordinator(nav);
  const overlay = vi.fn(() => true);
  const removeOverlay = coordinator.register("overlay", overlay);

  removeOverlay();
  expect(coordinator.handleBack()).toBe(true);
  expect(overlay).not.toHaveBeenCalled();
  expect(nav.goBack).toHaveBeenCalledOnce();
});
