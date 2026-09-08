import { expect, it } from "vitest";

import {
  normalizeMemberDeepLinkPath,
  normalizeNativeDeepLinkPath,
} from "./navigation/deepLinks";

it("maps verified member links to native plan, cycle, and exercise destinations", () => {
  expect(normalizeMemberDeepLinkPath("/link/member/plans/plan-1")).toBe(
    "/member/workouts?planId=plan-1",
  );
  expect(normalizeMemberDeepLinkPath("https://app.fitician.example/link/member/cycles/cycle-1")).toBe(
    "/member/workouts?cycleId=cycle-1",
  );
  expect(normalizeMemberDeepLinkPath("fitician://member/exercises/fedb-1%2Fpress")).toBe(
    "/member/exercises/fedb-1%2Fpress",
  );
});

it("supports custom-scheme paths and leaves unknown destinations untouched", () => {
  expect(normalizeMemberDeepLinkPath("member/plans/plan-2")).toBe(
    "/member/workouts?planId=plan-2",
  );
  expect(normalizeMemberDeepLinkPath("/link/member/plans")).toBe("/link/member/plans");
  expect(normalizeMemberDeepLinkPath("/member/profile")).toBe("/member/profile");
});

it("routes allowlisted verification and reset links to native auth screens", () => {
  expect(
    normalizeNativeDeepLinkPath(
      "https://app.fitician.example/link/verify-email?token=verification-token",
    ),
  ).toBe("/auth/verify-email?token=verification-token");
  expect(
    normalizeNativeDeepLinkPath("fitician://auth/reset-password?token=reset%2Ftoken"),
  ).toBe("/auth/reset-password?token=reset%2Ftoken");
});

it("rejects unverified hosts, unallowlisted paths, and incomplete auth links", () => {
  expect(
    normalizeNativeDeepLinkPath("https://evil.example/link/member/plans/plan-1"),
  ).toBe("/");
  expect(
    normalizeNativeDeepLinkPath("https://app.fitician.example/verify-email?token=token"),
  ).toBe("/");
  expect(normalizeNativeDeepLinkPath("fitician://auth/reset-password")).toBe("/");
  expect(normalizeNativeDeepLinkPath("fitician://admin/users")).toBe("/");
});

it("uses the build-time verified App Link host", () => {
  expect(
    normalizeNativeDeepLinkPath(
      "https://preview.fitician.example/link/member/exercises/press",
      { appLinkHost: "preview.fitician.example" },
    ),
  ).toBe("/member/exercises/press");
  expect(
    normalizeNativeDeepLinkPath("https://app.fitician.example/link/member/exercises/press", {
      appLinkHost: "preview.fitician.example",
    }),
  ).toBe("/");
});

it("leaves Expo Development Client control URLs for Expo Router", () => {
  expect(
    normalizeNativeDeepLinkPath(
      "fitician://expo-development-client/?url=exp%3A%2F%2F10.0.2.2%3A8081",
    ),
  ).toBeNull();
});
