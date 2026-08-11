import { expect, it } from "vitest";

type FileSystem = {
  readFileSync: (path: string, encoding: "utf8") => string;
};

const nodeProcess = (globalThis as typeof globalThis & {
  process: { getBuiltinModule: (name: "fs") => FileSystem };
}).process;
const profileCss = nodeProcess
  .getBuiltinModule("fs")
  .readFileSync("src/features/profile/profile.css", "utf8");

it("keeps profile questions bright, helpers muted, and section legends turquoise", () => {
  expect(profileCss).toMatch(
    /\.profile-form \.profile-field label\s*\{[^}]*color:\s*var\(--fitsho-ink\)/,
  );
  expect(profileCss).toMatch(
    /\.profile-form \.profile-field__hint\s*\{[^}]*color:\s*var\(--fitsho-muted\)/,
  );
  expect(profileCss).toMatch(
    /\.profile-form \.profile-fieldset legend\s*\{[^}]*color:\s*var\(--fitsho-aqua\)/,
  );
});
