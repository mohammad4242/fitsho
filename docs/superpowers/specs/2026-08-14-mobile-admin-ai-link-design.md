# Mobile Admin AI Link Design

## Goal

Restore access to the existing AI settings page from the mobile `More` page.

## Design

- Add an admin-only `MoreLink` inside the existing `Workspaces` group.
- Use the existing `settings` icon and route `/admin/ai-settings`.
- Display `تنظیمات هوش مصنوعی` in Persian and `AI settings` in English.
- Do not add a second settings page or change the existing admin route.
- Keep the link hidden from non-admin members.

## Tests

- An administrator sees the AI settings link with the correct route.
- A non-admin member does not see the AI settings link.
