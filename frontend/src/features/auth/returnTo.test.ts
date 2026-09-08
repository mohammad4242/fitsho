import { describe, expect, it } from "vitest";

import { authPath, safeReturnTo } from "./returnTo";

describe("auth return paths", () => {
  it("keeps only local application paths", () => {
    expect(safeReturnTo("/delete-account")).toBe("/delete-account");
    expect(safeReturnTo("https://evil.example/steal")).toBe("/dashboard");
    expect(safeReturnTo("//evil.example/steal")).toBe("/dashboard");
    expect(safeReturnTo("/delete-account\\evil")).toBe("/dashboard");
  });

  it("builds an encoded login return link", () => {
    expect(authPath("/login", "/delete-account")).toBe(
      "/login?returnTo=%2Fdelete-account",
    );
  });
});
