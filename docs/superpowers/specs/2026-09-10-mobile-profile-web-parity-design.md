# Mobile Profile Web-Parity Design

## Goal

Bring the Android Profile screen closer to the authenticated Web Profile hierarchy while preserving native touch usability and all existing profile, photo, navigation, and API behavior.

## Scope

- Change only the native profile presentation and mobile-only validation.
- Keep `frontend/`, `backend/`, and `packages/fitician-core/src/profile.ts` unchanged.
- Keep `body_recomposition` as the persisted/API value and show `ریکامپ` in this screen.
- Show only `زن`/`female` and `مرد`/`male` as native sex choices. Legacy persisted sex values remain untouched and are invalid until the user chooses a supported option.

## Composition

`ProfileScreen` will use profile-local native components and styles:

1. A title-only compact `PageHeading`.
2. One account-summary surface with a right-aligned avatar, identity copy, left-side `ویرایش`, and a compact five-stat grid.
3. Compact weight/body-analysis cards matching the Web information hierarchy.
4. `ProfileSectionProgress`, an accessible local radio navigation with a `مرحله X از Y` count, connected icon badges, dynamic `sections`, and existing section switching.
5. Two distinct personal cards: `مشخصات فردی` and `بدن و هدف`.
6. Profile-local compact choice controls and two-column measurement rows.

Training and nutrition retain their existing fields and save flow, but use the same compact group header language. Photo upload, replacement, deletion, route guards, back handling, API methods, and status refresh remain unchanged.

## Visual rules

- Use only `fiticianTokens` colors, spacing, radii, typography, and touch target values.
- Keep Persian copy right-aligned/RTL and all measurements LTR.
- Keep interactive controls at or above the 48px native touch target.
- Use borders, compact padding, and aqua icon badges instead of independent stat cards or oversized segmented buttons.
- Keep the profile page free of horizontal overflow at approximately 390px.

## Validation and tests

`validateProfileSection()` will merge the existing core validation with a native-only supported-sex check. RNTL coverage will verify the rendered hierarchy, supported/removed labels, `ریکامپ`, summary stats, dynamic section navigation, body-analysis route, and update API behavior. Model coverage will verify that legacy `other` and `prefer_not_to_say` values are not converted and require a supported selection.
