import { expect, it } from "vitest";

type FileSystem = {
  readFileSync: (path: string, encoding: "utf8") => string;
};

const nodeProcess = (globalThis as typeof globalThis & {
  process: { getBuiltinModule: (name: "fs") => FileSystem };
}).process;
const adminCss = nodeProcess
  .getBuiltinModule("fs")
  .readFileSync("src/features/admin/admin.css", "utf8");
const exerciseCss = nodeProcess
  .getBuiltinModule("fs")
  .readFileSync("src/features/exercises/exercises.css", "utf8");

it("keeps the meal image dialog fixed above the mobile header", () => {
  expect(adminCss).toMatch(
    /\.admin-page\s*>\s*\.admin-meal-image-dialog\s*\{[^}]*position:\s*fixed;[^}]*z-index:\s*70;/,
  );
});

it("keeps an open account menu above admin page content", () => {
  expect(adminCss).toMatch(
    /\.admin-page\s*>\s*\.dashboard-header--menu-open\s*\{[^}]*z-index:\s*50;/,
  );
});

it("renders the exercise-card Edit action with white text", () => {
  expect(exerciseCss).toMatch(
    /\.exercise-card__edit\s*\{[^}]*color:\s*(?:#fff(?:fff)?|white|var\(--paper\));/,
  );
});
