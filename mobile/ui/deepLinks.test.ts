import { expect, it } from "vitest";

import { normalizeMemberDeepLinkPath } from "./navigation/deepLinks";

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
