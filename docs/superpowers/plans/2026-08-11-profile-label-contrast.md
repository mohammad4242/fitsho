# Profile Label Contrast Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Profile form questions and helper text readable while preserving the existing dark layout and turquoise section hierarchy.

**Architecture:** Keep the change in the existing Profile stylesheet and scope it to `.profile-form`. Reuse Fitsho semantic color tokens instead of introducing new colors or component state.

**Tech Stack:** React 19, TypeScript, CSS, Vitest, Vite

## Global Constraints

- Do not change layout, spacing, RTL behavior, or form functionality.
- Use `--fitsho-ink` for questions, `--fitsho-muted` for helpers, and `--fitsho-aqua` only for legends/highlights.
- Preserve unrelated working-tree changes.

---

### Task 1: Profile form text hierarchy

**Files:**
- Modify: `frontend/src/features/profile/profile.css`
- Test: `frontend/src/features/profile/profileStyles.test.ts`

**Interfaces:**
- Consumes: Existing `.profile-form`, `.profile-field`, `.profile-field__hint`, and `.profile-fieldset` classes.
- Produces: Scoped semantic color rules for labels, helpers, and legends.

- [ ] **Step 1: Write the failing test**

Import `profile.css?raw` and assert that `.profile-form` rules assign `--fitsho-ink` to labels, `--fitsho-muted` to helper text, and `--fitsho-aqua` to legends.

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- --run src/features/profile/profileStyles.test.ts`

Expected: FAIL because the scoped semantic rules are absent.

- [ ] **Step 3: Write minimal implementation**

```css
.profile-form .profile-field label { color: var(--fitsho-ink); }
.profile-form .profile-field__hint { color: var(--fitsho-muted); }
.profile-form .profile-fieldset legend { color: var(--fitsho-aqua); }
```

- [ ] **Step 4: Run verification**

Run: `npm run test -- --run && npm run lint && npm run build`

Expected: All frontend tests, lint, and build pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/profile/profile.css frontend/src/features/profile/profileStyles.test.ts
git commit -m "fix(profile): improve form label contrast"
```
