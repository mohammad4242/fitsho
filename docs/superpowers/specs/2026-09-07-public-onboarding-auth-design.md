# Public Onboarding Authentication Design

## Scope

The final account step of the public onboarding flow will become the account handoff point for
Fitsho. A visitor can keep the onboarding draft in the current tab, choose email/password, phone
OTP, or Google, and then continue into the same existing profile hydration flow. Apple remains
visible as a disabled future option.

The change is frontend-only. It reuses the existing `AuthContext`, `api.sendPhoneOtp`,
`api.verifyPhoneOtp`, `AuthContext.loginWithGoogle`, and `GoogleSignInButton` contracts. The
backend `User` and `AuthSession` behavior, standalone login/register routes, and nutrition/training
onboarding data contracts are unchanged.

## Visual direction

The page is a Persian-first "coach checkpoint": the user has just answered personal questions, so
the account card should feel like a calm handoff rather than a generic sign-in screen.

- Palette: canvas black `#020607`, petrol `#091817`, raised surface `#101e1c`, aqua `#50dfce`,
  mist `#e8f4f1`, and coral `#f67859`, using the existing Fitsho tokens.
- Type: existing `Lalezar` display face for Persian headings, `Sora` for English headings, and
  `Vazirmatn` for Persian controls and supporting copy.
- Layout: a centered, responsive account card with a compact brand header, a short progress/status
  cue, an account-method strip, and one focused form area. On small screens it becomes a single
  full-width card with comfortable touch targets.
- Signature: the selected method is shown as an aqua "active route" with a small security cue that
  explains the onboarding answers remain attached to this browser session until account handoff.
- Motion: method changes use a short opacity/position transition; all nonessential motion is
  disabled under `prefers-reduced-motion`.

Conceptual layout:

```text
brand                                      privacy cue

        [ final checkpoint ]
        Your Fitsho path is ready
        short handoff explanation

        [ Email ] [ Phone ]
        [ Google identity button ]
        [ Apple             Coming soon ]
        -------------------------------
        focused email or phone/OTP form
        [ continue and save answers ]
        switch between sign in / create account
```

## Behavior and data flow

`FinalAccountStep` owns the selected method, email register/login mode, phone request/verify step,
phone number, resend countdown, busy state, and generic error state.

1. Email keeps the current register/login behavior and calls `register` or `login`.
2. Phone accepts an Iranian phone number, calls `sendPhoneOtp`, then replaces the request form
   with a six-digit OTP form. Resend honors `retry_after_seconds`. Verification calls
   `loginWithPhone`; the backend creates a phone-only account when the number is new.
3. Google renders the existing Google Identity Services button through `GoogleSignInButton`. Its
   credential callback calls `loginWithGoogle`; no frontend-decoded claims are trusted.
4. Every successful method calls one shared completion function: `hydrateOnboardingDraft(draft)`,
   then navigates to `/dashboard` for training or `/onboarding` for nutrition/both.
5. Existing authenticated users retain the current shortcut: account handoff does not require a
   second credential exchange.
6. Provider errors remain generic through `authErrorMessage`; loading disables duplicate actions;
   switching methods clears stale errors and does not discard the saved onboarding draft.

Google is rendered only when `VITE_GOOGLE_CLIENT_ID` is configured, matching the existing shared
component behavior. It is never labeled as coming soon. Apple remains disabled and labeled
`به‌زودی` / `Coming soon`.

## Components and boundaries

- `PublicOnboardingPage.tsx`: owns final-step auth state and calls existing auth/draft APIs.
- `publicOnboarding.css`: styles only the public onboarding/account-step composition, with explicit
  responsive and reduced-motion rules.
- `PublicOnboardingPage.test.tsx`: covers visible provider state, phone OTP handoff, Google
  credential handoff, email regression, Apple future state, and draft-preserving navigation.

No new backend endpoint, storage mechanism, authentication abstraction, or route is introduced.

## Verification

Use test-first cycles for the new phone and Google interactions. The focused public onboarding
tests must verify that:

- Google and phone are actionable while Apple remains disabled.
- Phone send moves to OTP verification, and successful verification calls draft hydration and the
  correct destination.
- Google credentials call the existing auth method and the same draft completion path.
- Email registration/login behavior and password mismatch validation remain intact.
- RTL/LTR markup, accessible labels, disabled/busy states, and the existing onboarding draft are
  preserved.

Then run the focused public onboarding tests, the full frontend test suite, lint, build, and
`git diff --check`.
