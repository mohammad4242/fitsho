# Single-Column Account Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the split promotional account layout with one centered form layout at every viewport width.

**Architecture:** Keep `AuthShell` as the shared layout for every public account flow, but remove its promotional section and make its navigation/form panel the only structure. Express the behavior through a focused component test, while CSS makes the single panel fill the viewport without changing any page logic.

**Tech Stack:** React 19, TypeScript, CSS, Vitest, Testing Library

## Global Constraints

- Apply the layout to every page that consumes `AuthShell`.
- Preserve routes, authentication behavior, validation, translations, and API calls.
- Keep the brand link, language switcher, and bounded form width at all viewport sizes.
- Do not add dependencies.

---

### Task 1: Shared single-column account shell

**Files:**
- Create: `frontend/src/shared/AuthShell.test.tsx`
- Modify: `frontend/src/shared/AuthShell.tsx`
- Modify: `frontend/src/index.css`
- Modify: `frontend/src/features/auth/LoginPage.test.tsx`

**Interfaces:**
- Consumes: `AuthShell({ children }: { children: ReactNode }): JSX.Element`
- Produces: the same component API with a single full-width form panel and persistent account navigation

- [x] **Step 1: Write the failing shared-shell test**

```tsx
import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { AuthShell } from "./AuthShell";

it("shows only account navigation and form content", () => {
  render(<AuthShell><p>account form</p></AuthShell>);

  expect(screen.getByRole("main")).toHaveClass("auth-shell", "fitsho-page");
  expect(screen.getByRole("link", { name: "فیتشو" })).toHaveAttribute("href", "/");
  expect(screen.getByRole("button", { name: "English" })).toBeVisible();
  expect(screen.getByText("account form")).toBeVisible();
  expect(screen.queryByTestId("auth-training-accent")).not.toBeInTheDocument();
  expect(document.querySelector(".brand-panel")).not.toBeInTheDocument();
});
```

Update the first login-page test to assert the form remains usable without promotional media.

- [x] **Step 2: Run the focused tests and verify RED**

Run: `npm run test -- src/shared/AuthShell.test.tsx src/features/auth/LoginPage.test.tsx`

Expected: FAIL because `AuthShell` still renders `auth-training-accent` and `.brand-panel`, and the login test still expects the image.

- [x] **Step 3: Implement the minimal single-column shell**

Remove the landing image import and `brand-panel` section from `AuthShell.tsx`. Keep one `form-panel`, render `form-panel__mobile-nav` as the always-visible account navigation, and keep `form-wrap` around `children`.

In `index.css`:

```css
.auth-shell {
  min-height: 100svh;
  display: block;
}

.form-panel {
  min-height: 100svh;
  display: grid;
  grid-template-rows: auto 1fr;
  padding: 1.2rem clamp(1rem, 6vw, 5rem) 3rem;
}

.form-panel__mobile-nav {
  display: flex;
}

.form-wrap {
  align-self: center;
  justify-self: center;
}
```

Remove obsolete responsive overrides that hide/show the deleted split layout. Retain the existing mobile spacing for the navigation and the existing `form-wrap` width.

- [x] **Step 4: Run focused and full frontend verification**

Run: `npm run test -- src/shared/AuthShell.test.tsx src/features/auth/LoginPage.test.tsx`

Expected: PASS.

Run: `npm run test && npm run lint && npm run build`

Expected: all commands exit 0.

- [x] **Step 5: Commit and push**

```bash
git add frontend/src/shared/AuthShell.test.tsx frontend/src/shared/AuthShell.tsx frontend/src/index.css frontend/src/features/auth/LoginPage.test.tsx frontend/src/features/auth/RegisterPage.test.tsx docs/superpowers/plans/2026-08-13-auth-pages-single-column.md
git commit -m "feat(auth): simplify account pages to one column"
git push origin main
```
