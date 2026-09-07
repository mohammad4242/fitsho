# Public Onboarding Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let visitors finish public onboarding with email, phone OTP, or Google on a polished Persian-first account handoff screen while keeping Apple as a disabled future option.

**Architecture:** Extend only `FinalAccountStep` in the existing public onboarding page. Reuse the current auth context, phone API, Google Identity button, onboarding draft hydration, and destination routing; a shared completion helper keeps all successful methods on one draft-preserving path.

**Tech Stack:** React 19, TypeScript, React Router, Vitest, React Testing Library, existing Fitsho CSS tokens, and Google Identity Services through the existing `GoogleSignInButton`.

**Spec:** `docs/superpowers/specs/2026-09-07-public-onboarding-auth-design.md`

## Global Constraints

- Preserve the existing `User` + `AuthSession` backend contracts and do not add auth endpoints.
- Preserve the existing onboarding draft storage, hydration API, and `/dashboard` versus `/onboarding` destinations.
- Use `api.sendPhoneOtp`, `useAuth().loginWithPhone`, and `useAuth().loginWithGoogle`; do not duplicate auth transport logic.
- Keep Apple visible but disabled with the existing Persian/English coming-soon label.
- Never trust Google claims in the frontend; pass the GIS credential to the existing backend auth method.
- Keep Persian-first RTL and English LTR behavior, keyboard focus, duplicate-submit protection, generic errors, and reduced-motion support.
- Stage only the three public onboarding task files; preserve the existing user change in `frontend/src/features/auth/api.test.ts` and all unrelated WIP.

---

### Task 1: Add failing public onboarding auth regressions

**Files:**
- Modify: `frontend/src/features/publicOnboarding/PublicOnboardingPage.test.tsx`

**Interfaces:**
- Consumes: `PublicOnboardingPage`, existing `AuthContext` test seam, `onboardingDraft` storage, and the `GoogleSignInButton` child boundary.
- Produces: failing tests that define enabled Google/phone providers, disabled Apple, phone OTP state transition, Google credential handoff, and destination preservation.

- [ ] **Step 1: Extend the test auth seam and mock transport boundaries**

Add `loginWithPhone` and `loginWithGoogle` to the hoisted auth object, mock `../auth/api` with
`sendPhoneOtp`, and mock `../auth/GoogleSignInButton` with a real test button that invokes the
credential callback. Mock only `hydrateOnboardingDraft` while keeping the draft loader and storage
helpers real:

```tsx
const auth = vi.hoisted(() => ({
  register: vi.fn(),
  login: vi.fn(),
  loginWithPhone: vi.fn(),
  loginWithGoogle: vi.fn(),
}));

const authApi = vi.hoisted(() => ({ sendPhoneOtp: vi.fn() }));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ ...auth, user: null, loading: false, startupError: false }),
}));

vi.mock("../auth/api", () => authApi);

vi.mock("../auth/GoogleSignInButton", () => ({
  GoogleSignInButton: ({
    onCredential,
    disabled,
  }: {
    onCredential: (credential: string) => void;
    disabled: boolean;
  }) => (
    <button type="button" disabled={disabled} onClick={() => onCredential("signed-google-token")}>
      Google
    </button>
  ),
}));

vi.mock("./onboardingDraft", async () => {
  const actual = await vi.importActual<typeof import("./onboardingDraft")>("./onboardingDraft");
  return { ...actual, hydrateOnboardingDraft: vi.fn().mockResolvedValue(undefined) };
});
```

Reset `authApi.sendPhoneOtp`, `auth.loginWithPhone`, and `auth.loginWithGoogle` in `beforeEach`,
and make each successful auth mock resolve to `undefined` before the new flow tests.

- [ ] **Step 2: Replace the obsolete disabled-provider assertion with the new contract**

Keep the existing seeded ready draft and email assertions, then assert that the active providers are
enabled and Apple alone remains disabled:

```tsx
expect(screen.getByRole("button", { name: "Google" })).toBeEnabled();
expect(screen.getByRole("button", { name: "شماره تلفن" })).toBeEnabled();
expect(screen.getByRole("button", { name: /Apple/ })).toBeDisabled();
expect(screen.getByText("مسیر امن انتقال اطلاعات")).toBeInTheDocument();
```

- [ ] **Step 3: Add the phone send/verify red test**

Seed the same training draft, resolve `authApi.sendPhoneOtp` with
`{ message: "accepted", retry_after_seconds: 60 }`, render the page, select the phone method,
enter `09123456789`, send the code, enter `123456`, and submit. Assert that the request moved to
the OTP step, `loginWithPhone` received the original number and code, the mocked hydration was
called with the stored draft, and the training destination rendered:

```tsx
it("finishes the onboarding handoff with phone OTP", async () => {
  const user = userEvent.setup();
  auth.loginWithPhone.mockResolvedValue(undefined);
  authApi.sendPhoneOtp.mockResolvedValue({ message: "accepted", retry_after_seconds: 60 });
  seedReadyTrainingDraft();

  render(<MemoryRouter initialEntries={["/onboarding"]}><Routes>
    <Route path="/onboarding" element={<PublicOnboardingPage />} />
    <Route path="/dashboard" element={<div>dashboard reached</div>} />
  </Routes></MemoryRouter>);

  await user.click(screen.getByRole("button", { name: "شماره تلفن" }));
  await user.type(screen.getByLabelText("شماره موبایل"), "09123456789");
  await user.click(screen.getByRole("button", { name: "ارسال کد ورود" }));
  expect(await screen.findByLabelText("کد ورود")).toBeInTheDocument();

  await user.type(screen.getByLabelText("کد ورود"), "123456");
  await user.click(screen.getByRole("button", { name: "تأیید و ذخیره پاسخ‌ها" }));

  expect(auth.loginWithPhone).toHaveBeenCalledWith("09123456789", "123456");
  expect(await screen.findByText("dashboard reached")).toBeInTheDocument();
});
```

- [ ] **Step 4: Add the Google credential red test**

Seed a training draft, resolve `auth.loginWithGoogle`, click the mocked Google button, and assert
that the exact credential reaches the existing auth method and the same dashboard handoff completes:

```tsx
it("finishes the onboarding handoff with Google", async () => {
  const user = userEvent.setup();
  auth.loginWithGoogle.mockResolvedValue(undefined);
  seedReadyTrainingDraft();

  render(<MemoryRouter initialEntries={["/onboarding"]}><Routes>
    <Route path="/onboarding" element={<PublicOnboardingPage />} />
    <Route path="/dashboard" element={<div>dashboard reached</div>} />
  </Routes></MemoryRouter>);

  await user.click(screen.getByRole("button", { name: "Google" }));

  expect(auth.loginWithGoogle).toHaveBeenCalledWith("signed-google-token");
  expect(await screen.findByText("dashboard reached")).toBeInTheDocument();
});
```

- [ ] **Step 5: Run the focused tests and verify the expected red state**

Run:

```bash
cd frontend
npm run test -- --run src/features/publicOnboarding/PublicOnboardingPage.test.tsx
```

Expected: the updated provider assertion and the new phone/Google tests fail because the current
page still disables the providers and has no phone/Google handlers in `FinalAccountStep`.

### Task 2: Connect phone and Google through the existing auth contracts

**Files:**
- Modify: `frontend/src/features/publicOnboarding/PublicOnboardingPage.tsx`
- Modify: `frontend/src/features/publicOnboarding/PublicOnboardingPage.test.tsx`

**Interfaces:**
- Consumes: `sendPhoneOtp(phoneNumber)`, `useAuth().loginWithPhone(phoneNumber, code)`,
  `useAuth().loginWithGoogle(credential)`, `hydrateOnboardingDraft(draft)`, and the current
  `GoogleSignInButton` props.
- Produces: one final-step account flow where email, phone OTP, and Google all invoke the same
  draft hydration and navigation completion.

- [ ] **Step 1: Add the minimal state and imports before changing markup**

Import `useCallback`, `* as api` from `../auth/api`, and `GoogleSignInButton`. Add these local
types and state values beside the existing email state:

```tsx
type AccountMethod = "email" | "phone";
type PhoneStep = "request" | "verify";

const [method, setMethod] = useState<AccountMethod>("email");
const [phoneStep, setPhoneStep] = useState<PhoneStep>("request");
const [phoneNumber, setPhoneNumber] = useState("");
const [countdown, setCountdown] = useState(0);
```

Add the same interval cleanup used by `LoginPage` to decrement `countdown` once per second.

- [ ] **Step 2: Add method selection, common completion, and phone handlers**

Implement method switching so it clears only the current error, then centralize the successful
handoff:

```tsx
function selectMethod(nextMethod: AccountMethod) {
  setMethod(nextMethod);
  setError(null);
}

function finishAuthentication(authentication: Promise<void>) {
  setBusy(true);
  setError(null);
  void authentication
    .then(() => hydrateOnboardingDraft(draft))
    .then(() => navigate(draft.mode === "training" ? "/dashboard" : "/onboarding", { replace: true }))
    .catch((reason: unknown) => setError(authErrorMessage(reason, t)))
    .finally(() => setBusy(false));
}

function sendOtp(number: string) {
  setBusy(true);
  setError(null);
  void api.sendPhoneOtp(number)
    .then((result) => {
      setPhoneNumber(number);
      setPhoneStep("verify");
      setCountdown(result.retry_after_seconds);
    })
    .catch((reason: unknown) => setError(authErrorMessage(reason, t)))
    .finally(() => setBusy(false));
}
```

Handle phone submit exactly as a two-step form: request sends the OTP; verify calls
`loginWithPhone` (or resolves immediately for an already authenticated user), then delegates to
`finishAuthentication`. Google's credential callback uses the same helper, and its error callback
sets the generic auth error.

- [ ] **Step 3: Replace disabled provider placeholders with real controls**

Render an account-method strip in which email and phone are selectable, Google uses the existing
GIS component, and Apple stays disabled:

```tsx
<div className="account-methods" role="tablist" aria-label={text.providers}>
  <button type="button" role="tab" aria-selected={method === "email"} onClick={() => selectMethod("email")}>
    {text.emailMethod}
  </button>
  <button type="button" role="tab" aria-selected={method === "phone"} onClick={() => selectMethod("phone")}>
    {text.phone}
  </button>
</div>
<div className="account-provider-grid" aria-label={text.providers}>
  <div className="account-provider account-provider--google">
    <span className="account-provider__label">Google</span>
    <GoogleSignInButton onCredential={handleGoogleCredential} onError={handleGoogleError} disabled={busy} />
  </div>
  <button className="account-provider account-provider--future" type="button" disabled>
    <span>Apple</span><small>{text.soon}</small>
  </button>
</div>
```

Keep the current email form under the email tab. Under the phone tab render the number input,
verification input after `phoneStep === "verify"`, resend button with the countdown, and a submit
label of `text.sendOtp` or `text.verifyOtp`. The submit button must keep `disabled={busy}`.

- [ ] **Step 4: Preserve the current account mode and already-authenticated shortcut**

Replace the existing inline `authenticate` chain with:

```tsx
const authentication = user !== null
  ? Promise.resolve()
  : accountMode === "register" ? register(credentials) : login(credentials);
finishAuthentication(authentication);
```

Use the same shortcut for phone verification and Google callbacks so an authenticated user can
attach the draft without an unnecessary second provider request. Keep password mismatch validation
before `setBusy(true)`.

- [ ] **Step 5: Run the focused tests and verify green behavior**

Run:

```bash
cd frontend
npm run test -- --run src/features/publicOnboarding/PublicOnboardingPage.test.tsx
```

Expected: all public onboarding tests pass, including the phone send/verify transition, exact
Google credential forwarding, Apple disabled state, email register/login behavior, and training
destination.

- [ ] **Step 6: Commit the behavior change**

```bash
git add frontend/src/features/publicOnboarding/PublicOnboardingPage.tsx frontend/src/features/publicOnboarding/PublicOnboardingPage.test.tsx
git commit -m "feat(auth): connect public onboarding phone and Google sign-in"
git push
```

### Task 3: Refresh the account handoff visual composition

**Files:**
- Modify: `frontend/src/features/publicOnboarding/PublicOnboardingPage.tsx`
- Modify: `frontend/src/features/publicOnboarding/publicOnboarding.css`
- Modify: `frontend/src/features/publicOnboarding/PublicOnboardingPage.test.tsx`

**Interfaces:**
- Consumes: the behavior from Task 2 and existing Fitsho design tokens, typography, and focus rules.
- Produces: responsive Persian-first account card styling with active method state, security cue,
  accessible provider labels, and Apple future-state styling.

- [ ] **Step 1: Add the visible handoff cue regression before styling**

Extend the ready-draft test to assert the new structural labels and state classes:

```tsx
expect(screen.getByText("مسیر امن انتقال اطلاعات")).toBeInTheDocument();
expect(screen.getByRole("tab", { name: "ایمیل" })).toHaveAttribute("aria-selected", "true");
expect(screen.getByRole("tab", { name: "شماره تلفن" })).toHaveAttribute("aria-selected", "false");
expect(document.querySelector(".public-account-step__card")).toBeInTheDocument();
```

- [ ] **Step 2: Add the account-card markup and bilingual copy**

Wrap the final-step content in `.public-account-step__card`, add a compact status row using
`AppIcon name="shield"`, and add explicit local copy keys for email method, phone OTP actions,
verification copy, and the security cue in both `fa` and `en`. Keep the existing edit action,
account-mode toggle, and error role.

- [ ] **Step 3: Implement the focused CSS composition**

Use the existing tokens with a centered card, aqua active route, quiet raised surfaces, and
touch-sized controls. The account-step rules must include:

```css
.public-account-step {
  position: relative;
  isolation: isolate;
  min-height: 100svh;
  display: grid;
  place-items: center;
  overflow: hidden;
  padding: clamp(1rem, 4vw, 3rem);
  background: radial-gradient(circle at 12% 18%, rgb(80 223 206 / 10%), transparent 32rem), var(--fitsho-canvas);
}

.public-account-step__card {
  width: min(100%, 52rem);
  padding: clamp(1.25rem, 4vw, 3rem);
  border: 1px solid var(--fitsho-line-strong);
  border-radius: var(--fitsho-radius-xl);
  background: linear-gradient(145deg, rgb(16 30 28 / 96%), rgb(5 11 12 / 98%));
  box-shadow: var(--fitsho-shadow);
}

.account-methods [aria-selected="true"] {
  color: #071313;
  background: var(--fitsho-aqua);
  box-shadow: var(--fitsho-shadow-glow);
}

.account-provider--future {
  opacity: 0.6;
}

@media (prefers-reduced-motion: reduce) {
  .public-account-step *,
  .public-account-step *::before,
  .public-account-step *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
}
```

Add mobile rules below the existing public-onboarding media query so the card fills the viewport
width, provider controls stack without horizontal overflow, inputs remain at least 3.25rem high,
and the email/phone tabs remain easy to tap. Add explicit `:focus-visible` and disabled styles
without overriding global focus contrast.

- [ ] **Step 4: Run focused tests, lint, and build**

Run:

```bash
cd frontend
npm run test -- --run src/features/publicOnboarding/PublicOnboardingPage.test.tsx
npm run lint
npm run build
```

Expected: the focused tests pass, lint reports no new issues, and the production bundle builds.

- [ ] **Step 5: Inspect the rendered final step at RTL and LTR widths**

Run the frontend preview/dev server using the repository command, seed a ready onboarding draft in
the browser session, and inspect the final account step at a desktop width and a narrow phone
width. Confirm Google is rendered when `VITE_GOOGLE_CLIENT_ID` is configured, phone reaches the OTP
state, Apple remains visibly future-only, and no horizontal scroll or clipped Persian text appears.

- [ ] **Step 6: Commit the visual refresh**

```bash
git add frontend/src/features/publicOnboarding/PublicOnboardingPage.tsx frontend/src/features/publicOnboarding/publicOnboarding.css frontend/src/features/publicOnboarding/PublicOnboardingPage.test.tsx
git commit -m "feat(ui): modernize public onboarding account handoff"
git push
```

### Task 4: Run final regression verification and inspect the exact diff

**Files:**
- Verify only: `frontend/src/features/publicOnboarding/PublicOnboardingPage.tsx`
- Verify only: `frontend/src/features/publicOnboarding/publicOnboarding.css`
- Verify only: `frontend/src/features/publicOnboarding/PublicOnboardingPage.test.tsx`

**Interfaces:**
- Consumes: the two focused commits from Tasks 2 and 3.
- Produces: fresh evidence that public onboarding auth works and unrelated working-tree changes
  remain untouched.

- [ ] **Step 1: Run the focused and full frontend tests**

```bash
cd frontend
npm run test -- --run src/features/publicOnboarding/PublicOnboardingPage.test.tsx
npm run test -- --run
```

- [ ] **Step 2: Run static checks and whitespace validation**

```bash
cd frontend
npm run lint
npm run build
cd ..
git diff --check
```

- [ ] **Step 3: Inspect the final staged scope and Git state**

```bash
git diff --stat origin/main...HEAD
git status --short --branch
git log -4 --oneline --decorate
```

Confirm the two task commits contain only the public onboarding files plus the committed design and
plan documents, while the pre-existing `frontend/src/features/auth/api.test.ts` modification and
untracked user WIP remain unstaged.

- [ ] **Step 4: Report exact manual test handoff**

Tell the user to start the configured frontend/backend, complete public onboarding, then test
email register/login, phone OTP with a real or fake configured SMS provider, Google with a configured
`VITE_GOOGLE_CLIENT_ID`, and Apple's disabled future state. State separately if real SMS or Google
provider delivery is not available in the current environment.
