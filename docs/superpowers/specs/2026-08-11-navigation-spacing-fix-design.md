# Fitsho Navigation Spacing Fix

## Goal

Prevent authenticated navigation items from touching, wrapping into each other, or becoming difficult to scan in Persian and English.

## Desktop header

- Keep at most four primary product routes visible.
- Place remaining routes behind a compact `More` menu.
- Preserve active-route feedback and all existing route permissions.
- Keep the brand, language control, and logout action visually separate from navigation.

## Account menu

- Group links into product, account, social, and administration sections when applicable.
- Use clear section labels, dividers, and a consistent 0.5rem item gap.
- Give every interactive row a minimum 44px touch target.
- Limit height and allow internal scrolling without overlapping page content.
- Keep alignment logical in both RTL and LTR.

## Mobile

- Preserve the existing bottom-navigation model.
- Keep four primary destinations plus `More` when overflow exists.
- Use the same grouped menu rhythm with safe viewport edges and scrollable overflow.

## Accessibility and verification

- Preserve semantic navigation, keyboard focus, active states, labels, permissions, and routes.
- Add regression coverage for grouping and visible primary-route limits.
- Verify Persian RTL and English LTR at mobile and desktop widths.
