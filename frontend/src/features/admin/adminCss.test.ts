import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const css = readFileSync("src/features/admin/admin.css", "utf8");

describe("AI settings mobile containment", () => {
  it("allows every nested settings surface to shrink to the viewport", () => {
    expect(css).toMatch(
      /\.admin-main--ai-settings[^}]*min-width:\s*0/,
    );
    expect(css).toMatch(
      /\.admin-ai-settings-form[^}]*min-width:\s*0/,
    );
    expect(css).toMatch(
      /\.admin-main--ai-settings \.admin-panel[^}]*min-width:\s*0/,
    );
  });

  it("collapses observability rows to one column on phones", () => {
    expect(css).toMatch(
      /@media \(max-width:\s*760px\)[\s\S]*?\.admin-ai-observability div\s*{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/,
    );
  });
});
