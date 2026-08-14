# Mobile Admin AI Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the existing AI settings route to the mobile administrator workspace list.

**Architecture:** Add one admin-only `MoreLink` to the existing `MorePage`; retain the existing route, icon system, authorization guard, and bilingual inline copy.

**Tech Stack:** React 19, TypeScript, React Router, Vitest, Testing Library

## Global Constraints

- Route must remain `/admin/ai-settings`.
- Link must be visible only when `user.is_admin` is true.
- No second AI settings page or API is introduced.

---

### Task 1: Restore Mobile AI Settings Navigation

**Files:**
- Modify: `frontend/src/pages/MorePage.tsx`
- Test: `frontend/src/pages/MorePage.test.tsx`

**Interfaces:**
- Consumes: `user.is_admin`, `MoreLink`, `l(fa, en)`, and the existing `settings` icon.
- Produces: an admin-only link to `/admin/ai-settings`.

- [ ] **Step 1: Write failing navigation tests**

Add an administrator assertion:

```ts
expect(screen.getByRole("link", { name: /تنظیمات هوش مصنوعی/ })).toHaveAttribute(
  "href",
  "/admin/ai-settings",
);
```

Add a non-admin assertion that the same link is absent.

- [ ] **Step 2: Run the test and verify RED**

```bash
npm run test -- --run src/pages/MorePage.test.tsx
```

Expected: the administrator test fails because the link is missing.

- [ ] **Step 3: Add the existing-route link**

Inside the admin portion of `Workspaces`, add:

```tsx
<MoreLink
  to="/admin/ai-settings"
  icon="settings"
  title={l("تنظیمات هوش مصنوعی", "AI settings")}
/>
```

- [ ] **Step 4: Run focused and complete verification**

```bash
npm run test -- --run src/pages/MorePage.test.tsx
npm run test -- --run
npm run lint
npm run build
git diff --check
```

Expected: all tests, lint, build, and whitespace checks pass.

- [ ] **Step 5: Commit, push, and verify runtime**

```bash
git add frontend/src/pages/MorePage.tsx frontend/src/pages/MorePage.test.tsx
git commit -m "fix(admin): restore mobile AI settings link"
git push origin main
```

Confirm the Vite-served `MorePage.tsx` contains `/admin/ai-settings`, frontend `5173` returns
`200`, and local `main` equals `origin/main`.
