# Body Analysis Session Delete Dialog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deletion to saved analyses and replace browser confirmation with a responsive custom dialog for every Body Analysis session.

**Architecture:** `BodyProgressPage` owns one selected-session state and one deletion request state. Both card categories open the same modal component, which calls the existing delete API and removes the successful session from the shared list.

**Tech Stack:** React 19, TypeScript, i18next, CSS, Vitest, Testing Library

## Global Constraints

- Use the existing owner-scoped session delete endpoint.
- Preserve grouping, resume, analysis links, and latest-analysis behavior.
- Keep Persian as the primary UI language.
- Preserve unrelated worktree changes.
- Support keyboard dismissal and reduced motion.

---

### Task 1: Shared session-delete dialog

**Files:**
- Modify: `frontend/src/features/bodyPhotos/BodyProgressPage.tsx`
- Modify: `frontend/src/features/bodyPhotos/BodyProgressPage.test.tsx`
- Modify: `frontend/src/features/bodyPhotos/bodyPhotos.css`
- Modify: `frontend/src/i18n/en.ts`
- Modify: `frontend/src/i18n/fa.ts`

**Interfaces:**
- Consumes: `deleteBodyPhotoSession(sessionId: string): Promise<void>`
- Produces: a delete button for every session card and one accessible confirmation dialog controlled by `BodyPhotoSession | null`

- [ ] **Step 1: Write failing interaction tests**

Add an analysis card to the existing fixtures and assert that both card categories expose delete.
Open each delete action and verify its category-specific title. Cover cancel, Escape, success, and
failure followed by retry.

```tsx
await user.click(screen.getByRole("button", { name: "Delete analysis" }));
expect(screen.getByRole("dialog", { name: "Delete saved analysis?" })).toBeVisible();
await user.click(screen.getByRole("button", { name: "Delete permanently" }));
await waitFor(() => expect(api.deleteBodyPhotoSession).toHaveBeenCalledWith("analysis-1"));
```

- [ ] **Step 2: Verify tests fail**

Run: `npm run test -- src/features/bodyPhotos/BodyProgressPage.test.tsx`
Expected: FAIL because analysis deletion and the custom dialog do not exist.

- [ ] **Step 3: Implement shared modal state and actions**

Replace `window.confirm` with selected-session state and render a single dialog after both lists.
The selected session determines copy and request target.

```ts
const [deleteTarget, setDeleteTarget] = useState<BodyPhotoSession | null>(null);
const targetIsIncomplete = deleteTarget?.submitted_at === null;

async function confirmDelete() {
  if (deleteTarget === null) return;
  await deleteBodyPhotoSession(deleteTarget.id);
  setSessions((current) => current?.filter(({ id }) => id !== deleteTarget.id) ?? current);
  setDeleteTarget(null);
}
```

Handle Escape with an effect while the dialog is open. Backdrop and Cancel close only when no
request is active. On failure keep the target selected, show `role="alert"`, and allow retry.

- [ ] **Step 4: Add category-specific Persian and English copy**

Add keys for delete action labels, analysis/upload titles, description, date/status labels,
Cancel, deleting, permanent deletion, and failure. Keep action wording consistent between cards
and dialog.

- [ ] **Step 5: Build the visual treatment**

Add a fixed blurred backdrop, a centered surface panel with a danger rail and icon, compact
session metadata, visible focus states, and a destructive solid button. At `max-width: 640px`,
anchor the panel as a bottom sheet. Under `prefers-reduced-motion`, remove the entrance animation.

- [ ] **Step 6: Verify focused behavior**

Run: `npm run test -- src/features/bodyPhotos/BodyProgressPage.test.tsx`
Expected: PASS.

- [ ] **Step 7: Verify the frontend**

Run: `npm test`
Run: `npm run lint`
Run: `npm run build`
Expected: all commands pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/bodyPhotos/BodyProgressPage.tsx frontend/src/features/bodyPhotos/BodyProgressPage.test.tsx frontend/src/features/bodyPhotos/bodyPhotos.css frontend/src/i18n/en.ts frontend/src/i18n/fa.ts
git commit -m "feat(body-analysis): add session delete dialog"
```
