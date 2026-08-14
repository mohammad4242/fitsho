# Body Analysis Resumable Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate incomplete uploads from submitted analyses and let users resume or delete every incomplete Body Analysis session.

**Architecture:** The frontend classifies existing session responses by `submitted_at` and keeps the backend contract unchanged. The history page owns grouping and deletion, while the wizard loads an existing unsubmitted session, derives completed views from server photos, and resumes at the first missing view.

**Tech Stack:** React 19, TypeScript, React Router, i18next, Vitest, Testing Library

## Global Constraints

- Preserve the owner-scoped Body Photo API and existing session states.
- Preserve uploaded photos when resuming an incomplete session.
- Preserve the headless-photo and no-face-processing privacy contract.
- Do not modify unrelated exercise-catalogue work in the current worktree.

---

### Task 1: Separate and manage incomplete sessions

**Files:**
- Modify: `frontend/src/features/bodyPhotos/BodyProgressPage.tsx`
- Modify: `frontend/src/features/bodyPhotos/BodyProgressPage.test.tsx`
- Modify: `frontend/src/features/bodyPhotos/bodyPhotos.css`
- Modify: `frontend/src/i18n/en.ts`
- Modify: `frontend/src/i18n/fa.ts`

**Interfaces:**
- Consumes: `getBodyPhotoSessions(): Promise<BodyPhotoSessionList>` and `deleteBodyPhotoSession(sessionId: string): Promise<void>`
- Produces: incomplete-upload cards linking to `/body-progress/new?sessionId=<id>` and submitted-analysis cards linking to `/body-progress/<id>`

- [ ] **Step 1: Write failing history tests**

Add tests that return one unsubmitted session and one submitted session, then assert separate headings, the resume URL, no analysis link on the incomplete card, and the latest-analysis marker on the submitted card. Add tests that confirm deletion, remove the card after success, and retain it with an inline error after rejection.

```tsx
expect(await screen.findByRole("heading", { name: "Incomplete uploads" })).toBeVisible();
expect(screen.getByRole("link", { name: "Continue upload" })).toHaveAttribute(
  "href",
  "/body-progress/new?sessionId=incomplete-1",
);
expect(screen.getByText("Latest analysis")).toBeVisible();
```

- [ ] **Step 2: Verify the tests fail**

Run: `npm run test -- src/features/bodyPhotos/BodyProgressPage.test.tsx`
Expected: FAIL because grouping, resume, and deletion controls do not exist.

- [ ] **Step 3: Implement grouping and deletion**

Import `deleteBodyPhotoSession`, split sessions with `submitted_at === null`, render separate sections, and keep per-session deletion state.

```ts
const incompleteSessions = sessions.filter((session) => session.submitted_at === null);
const analysisSessions = sessions.filter((session) => session.submitted_at !== null);

async function removeSession(sessionId: string) {
  if (!window.confirm(t("bodyPhotos.incomplete.confirmDelete"))) return;
  await deleteBodyPhotoSession(sessionId);
  setSessions((current) => current?.filter((session) => session.id !== sessionId) ?? current);
}
```

Add Persian-first copy for incomplete uploads, continue, delete, confirmation, and deletion failure. Add focused card/action styles without changing the analysis result cards.

- [ ] **Step 4: Verify history tests pass**

Run: `npm run test -- src/features/bodyPhotos/BodyProgressPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/bodyPhotos/BodyProgressPage.tsx frontend/src/features/bodyPhotos/BodyProgressPage.test.tsx frontend/src/features/bodyPhotos/bodyPhotos.css frontend/src/i18n/en.ts frontend/src/i18n/fa.ts
git commit -m "feat(body-analysis): distinguish incomplete photo sessions"
```

### Task 2: Resume from the first missing photo

**Files:**
- Modify: `frontend/src/features/bodyPhotos/BodyPhotoWizard.tsx`
- Modify: `frontend/src/features/bodyPhotos/BodyPhotoWizard.test.tsx`

**Interfaces:**
- Consumes: `getBodyPhotoSession(sessionId: string): Promise<BodyPhotoSession>` and existing upload, submit, and analysis-start functions
- Produces: `?sessionId=<id>` resume behavior; the existing `?sessionId=<id>&view=<view>` failed-analysis replacement behavior remains intact

- [ ] **Step 1: Write failing resume tests**

Add tests for a session containing only `front`, a session already containing all three views, and a failed-analysis replacement session. Assert that a partial session opens on `side`, reuses its ID without creating a session, reaches review after uploading missing views, and submits/starts analysis.

```tsx
renderWizard(processor, "/body-progress/new?sessionId=session-2");
expect(await screen.findByRole("heading", { name: /side photo/i })).toBeVisible();
expect(api.createBodyPhotoSession).not.toHaveBeenCalled();
```

- [ ] **Step 2: Verify the tests fail**

Run: `npm run test -- src/features/bodyPhotos/BodyPhotoWizard.test.tsx`
Expected: FAIL because `sessionId` without `view` is ignored.

- [ ] **Step 3: Implement resume hydration and completion**

Load whenever `sessionId` exists. Use uploaded server views together with newly processed views, choose the first missing view, and enter review immediately if no view is missing.

```ts
const uploadedViews = new Set(session?.photos.map((photo) => photo.view) ?? []);
const hasView = (item: BodyPhotoView) => uploadedViews.has(item) || processed[item] !== undefined;
const complete = views.every(hasView);
```

After each upload, select the first remaining missing view from the returned session. Review thumbnails use `processed[view]?.previewUrl` first and the existing server `content_url` otherwise. Keep the explicit-view replacement path unchanged.

- [ ] **Step 4: Verify wizard tests pass**

Run: `npm run test -- src/features/bodyPhotos/BodyPhotoWizard.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run frontend verification**

Run: `npm run test -- src/features/bodyPhotos/BodyProgressPage.test.tsx src/features/bodyPhotos/BodyPhotoWizard.test.tsx`
Run: `npm run lint`
Run: `npm run build`
Expected: all commands pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/bodyPhotos/BodyPhotoWizard.tsx frontend/src/features/bodyPhotos/BodyPhotoWizard.test.tsx
git commit -m "feat(body-analysis): resume incomplete photo uploads"
```
