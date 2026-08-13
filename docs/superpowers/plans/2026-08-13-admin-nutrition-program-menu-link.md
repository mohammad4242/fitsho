# Nutrition Program Catalogue Menu Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the existing Nutrition Program Catalogue route to the administrator section of the desktop account menu.

**Architecture:** Extend the existing admin link group in `AuthenticatedHeader` with one React Router link. Reuse the existing translation key and route, and cover the behavior in the existing application navigation test.

**Tech Stack:** React 19, React Router, TypeScript, Vitest, Testing Library

## Global Constraints

- Keep roles, routes, translations, and page behavior unchanged.
- Show the link only inside the existing administrator-only menu group.
- Close the account menu when the link is selected.
- Do not add dependencies.

---

### Task 1: Administrator menu link

**Files:**
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/shared/AuthenticatedHeader.tsx`

**Interfaces:**
- Consumes: `header.adminNutritionPrograms` and route `/admin/nutrition-programs`
- Produces: an administrator-only account-menu link to the existing catalogue page

- [x] **Step 1: Write the failing navigation test**

In the authenticated administrator menu test, locate the `مدیریت` group and assert:

```tsx
expect(
  within(adminGroup).getByRole("link", { name: "کاتالوگ برنامه‌های غذایی" }),
).toHaveAttribute("href", "/admin/nutrition-programs");
```

- [x] **Step 2: Run the focused test and verify RED**

Run: `npm run test -- src/App.test.tsx`

Expected: FAIL because the Administration group does not contain the Nutrition Program Catalogue link.

- [x] **Step 3: Add the menu link**

Add this adjacent to the existing meal-catalogue link:

```tsx
<Link to="/admin/nutrition-programs" onClick={() => setMenuOpen(false)}>
  {t("header.adminNutritionPrograms")}
</Link>
```

- [x] **Step 4: Run focused and full verification**

Run: `npm run test -- src/App.test.tsx`

Expected: PASS.

Run: `npm run test && npm run lint && npm run build`

Expected: all commands exit 0.

- [x] **Step 5: Commit and push**

```bash
git add docs/superpowers/plans/2026-08-13-admin-nutrition-program-menu-link.md frontend/src/App.test.tsx frontend/src/shared/AuthenticatedHeader.tsx
git commit -m "feat(admin): add nutrition programs to account menu"
git push origin main
```
