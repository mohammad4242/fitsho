# Public Video Landing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build a premium three-scene video entry page for guests while preserving Fitsho authentication, backend, database, APIs, and every protected route.

**Architecture:** PublicLandingRoute reads the existing auth context: guests receive PublicLandingPage; members are redirected to /dashboard. PublicLandingPage observes three sections and marks one active. LandingVideo receives that state and is the only component allowed to play or pause a video, including a mapped image fallback.

**Tech Stack:** React 19, TypeScript, React Router, Vite static imports, Vitest, Testing Library, CSS, i18next.

## Global Constraints

- Copy only root image_videos media to tracked frontend assets with stable descriptive filenames.
- Guest / is the landing; all three شروع رایگان links go to /register; a signed-in visitor at / goes to /dashboard.
- Keep /login, /register, protected routes, API requests, database models, migrations, and session behavior unchanged.
- Use Lalezar display text, current Vazirmatn/Sora body fonts, dark petrol overlays, existing aqua primary CTA.
- Videos are muted, looped, inline, and active-only. First scene preloads metadata; later scenes use preload="none".
- Reduced motion and video errors use still images without removing copy, CTA, focus, or keyboard behavior.
- Do not stretch portrait photos as unmasked wide desktop backgrounds.
- Apply TDD: red test, minimal implementation, green test. Complete, verify, commit, and push each task separately.

---

## File Structure

- frontend/src/assets/landing/: three supplied MP4 files and five supplied JPEG files, descriptively renamed.
- frontend/src/features/landing/landingContent.ts: LandingScene data, Persian copy, and static media imports.
- frontend/src/features/landing/LandingVideo.tsx: one active scene's media and fallback behavior.
- frontend/src/features/landing/PublicLandingPage.tsx: full-viewport story, observer, header, and CTAs.
- frontend/src/features/landing/PublicLandingRoute.tsx: guest/member root routing.
- frontend/src/features/landing/publicLanding.css: responsive story visuals and motion rules.
- frontend/src/features/landing/*.test.tsx: focused media, observer, reduced-motion, and CTA tests.
- frontend/src/App.tsx and frontend/src/App.test.tsx: root integration.
- frontend/src/shared/AuthShell.tsx and frontend/src/index.css: static owner-photo accent only.

### Task 1: Add owned media and typed landing content

**Files:**
- Create: frontend/src/assets/landing/hero-strength.mp4
- Create: frontend/src/assets/landing/plan-focus.mp4
- Create: frontend/src/assets/landing/progress-drive.mp4
- Create: frontend/src/assets/landing/hero-strength-fallback.jpg
- Create: frontend/src/assets/landing/plan-focus-fallback.jpg
- Create: frontend/src/assets/landing/progress-drive-fallback.jpg
- Create: frontend/src/assets/landing/auth-training-accent.jpg
- Create: frontend/src/assets/landing/app-training-accent.jpg
- Create: frontend/src/features/landing/landingContent.ts
- Test: frontend/src/features/landing/landingContent.test.ts

**Interfaces:**
- Produces LandingScene:
~~~ts
export type LandingScene = {
  id: "strength" | "plan" | "progress";
  eyebrow: string;
  title: string;
  body: string;
  videoSrc: string;
  fallbackSrc: string;
  preload: "metadata" | "none";
};
export const landingScenes: readonly LandingScene[];
~~~

- [ ] **Step 1: Write the failing content test**
~~~tsx
it("defines the three approved landing chapters", () => {
  expect(landingScenes.map(({ id, title, preload }) => ({ id, title, preload }))).toEqual([
    { id: "strength", title: "از امروز، قوی‌تر.", preload: "metadata" },
    { id: "plan", title: "بدون حدس، با برنامه.", preload: "none" },
    { id: "progress", title: "هر تکرار، نزدیک‌تر.", preload: "none" },
  ]);
});
~~~

- [ ] **Step 2: Run red verification**

Run: npm test -- --run frontend/src/features/landing/landingContent.test.ts

Expected: FAIL because landingContent.ts does not exist.

- [ ] **Step 3: Add media mapping**

Copy landing.mp4 to hero-strength.mp4, video_2026-07-29_12-38-17.mp4 to plan-focus.mp4, and video_2026-07-29_12-39-40.mp4 to progress-drive.mp4. Copy the five JPEGs once each into the listed fallback/accent names. Create static imports and exactly these chapters:
~~~ts
export const landingScenes = [
  { id: "strength", title: "از امروز، قوی‌تر.", preload: "metadata" },
  { id: "plan", title: "بدون حدس، با برنامه.", preload: "none" },
  { id: "progress", title: "هر تکرار، نزدیک‌تر.", preload: "none" },
] as const satisfies readonly LandingScene[];
~~~
Fill the remaining fields with short Persian copy and mapped assets.

- [ ] **Step 4: Run green verification**

Run: npm test -- --run frontend/src/features/landing/landingContent.test.ts

Expected: PASS.

- [ ] **Step 5: Commit and push**
~~~bash
git add frontend/src/assets/landing frontend/src/features/landing/landingContent.ts frontend/src/features/landing/landingContent.test.ts
git commit -m "feat(landing): add owner media story assets"
git push
~~~

### Task 2: Add active-only playback and still fallback

**Files:**
- Create: frontend/src/features/landing/LandingVideo.tsx
- Create: frontend/src/features/landing/LandingVideo.test.tsx
- Modify: frontend/src/test/setup.ts

**Interfaces:**
- Consumes LandingScene and props:
~~~ts
type LandingVideoProps = {
  scene: LandingScene;
  active: boolean;
  reducedMotion: boolean;
};
~~~
- Produces LandingVideo. It plays only while active, motion is allowed, and no error has occurred; otherwise it pauses or displays the fallback image.

- [ ] **Step 1: Write failing media tests**
~~~tsx
it("plays only an active non-reduced-motion scene", async () => {
  render(<LandingVideo scene={landingScenes[0]} active reducedMotion={false} />);
  expect(await screen.findByTestId("landing-video-strength")).toHaveAttribute("preload", "metadata");
  expect(HTMLMediaElement.prototype.play).toHaveBeenCalledOnce();
});

it("uses the mapped still for reduced motion", () => {
  render(<LandingVideo scene={landingScenes[1]} active reducedMotion />);
  expect(screen.getByRole("img", { name: /بدون حدس/ })).toBeVisible();
  expect(screen.queryByTestId("landing-video-plan")).not.toBeInTheDocument();
});
~~~
Stub HTMLMediaElement play as a resolved mock and pause as a mock in test setup.

- [ ] **Step 2: Run red verification**

Run: npm test -- --run frontend/src/features/landing/LandingVideo.test.tsx

Expected: FAIL because LandingVideo.tsx does not exist.

- [ ] **Step 3: Implement the media boundary**
~~~tsx
const [hasVideoError, setHasVideoError] = useState(false);
const showFallback = reducedMotion || hasVideoError;
useEffect(() => {
  const video = videoRef.current;
  if (!video) return;
  if (active && !showFallback) void video.play().catch(() => setHasVideoError(true));
  else video.pause();
}, [active, showFallback]);
~~~
Render an img with scene.title alt when showFallback is true. Otherwise render one muted, loop, playsInline video with scene.preload, scene.fallbackSrc poster, source scene.videoSrc, and onError setting hasVideoError.

- [ ] **Step 4: Run green verification**

Run: npm test -- --run frontend/src/features/landing/LandingVideo.test.tsx

Expected: PASS.

- [ ] **Step 5: Commit and push**
~~~bash
git add frontend/src/features/landing/LandingVideo.tsx frontend/src/features/landing/LandingVideo.test.tsx frontend/src/test/setup.ts
git commit -m "feat(landing): add active video fallback behavior"
git push
~~~

### Task 3: Implement root route and three-scene public story

**Files:**
- Create: frontend/src/features/landing/PublicLandingPage.tsx
- Create: frontend/src/features/landing/PublicLandingPage.test.tsx
- Create: frontend/src/features/landing/PublicLandingRoute.tsx
- Create: frontend/src/features/landing/publicLanding.css
- Modify: frontend/src/App.tsx
- Modify: frontend/src/App.test.tsx

**Interfaces:**
- PublicLandingRoute returns loading markup when auth is loading, Navigate to /dashboard for a user, otherwise PublicLandingPage.
- PublicLandingPage renders sections with IDs landing-strength, landing-plan, landing-progress; each one has one Link to /register named شروع رایگان.

- [ ] **Step 1: Write failing root and page tests**
~~~tsx
it("shows three registration CTAs to a guest at root", () => {
  render(<MemoryRouter initialEntries={["/"]}><AppRoutes /></MemoryRouter>);
  const ctas = screen.getAllByRole("link", { name: "شروع رایگان" });
  expect(ctas).toHaveLength(3);
  ctas.forEach((cta) => expect(cta).toHaveAttribute("href", "/register"));
});

it("redirects a signed-in root visitor to Today", async () => {
  auth.value.user = member;
  profile.value.status = "ready";
  profile.value.profile = completedProfile;
  render(<MemoryRouter initialEntries={["/"]}><AppRoutes /></MemoryRouter>);
  expect(await screen.findByRole("heading", { name: /امروز/ })).toBeInTheDocument();
});
~~~
Mock IntersectionObserver in PublicLandingPage.test.tsx. Invoke it for an observed scene and assert its data-active is true. Mock matchMedia with matches true and assert three fallback images.

- [ ] **Step 2: Run red verification**

Run: npm test -- --run frontend/src/features/landing/PublicLandingPage.test.tsx frontend/src/App.test.tsx

Expected: FAIL because the landing route is absent.

- [ ] **Step 3: Implement observer, route, and visual page**
~~~tsx
export function PublicLandingRoute() {
  const { loading, user } = useAuth();
  if (loading) return <main aria-busy="true" className="landing-loading" />;
  return user ? <Navigate to="/dashboard" replace /> : <PublicLandingPage />;
}
~~~
Use one IntersectionObserver with threshold 0.65 to update activeSceneId from the intersecting section. Render a compact brand/language/login header. Map landingScenes to full-screen sections; render LandingVideo, overlay, headline, supporting copy, and Link to /register named شروع رایگان. Replace only App.tsx's current / redirect; do not alter wildcard logic.

- [ ] **Step 4: Add responsive visual rules**

Make each scene min-height: 100svh with absolute media and dark petrol gradient. Animate content only when data-active is true. CTA must be >= 1.125rem, bold, focus-visible, touch-safe, and in every scene. Video uses object-fit cover; portrait fallback uses masked treatment with per-scene object-position. At prefers-reduced-motion reduce, disable motion and scroll snapping.

- [ ] **Step 5: Run green verification**

Run: npm test -- --run frontend/src/features/landing/PublicLandingPage.test.tsx frontend/src/App.test.tsx

Expected: PASS.

- [ ] **Step 6: Commit and push**
~~~bash
git add frontend/src/features/landing frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat(landing): add full-screen public video story"
git push
~~~

### Task 4: Add restricted static photo accent to sign-in

**Files:**
- Modify: frontend/src/shared/AuthShell.tsx
- Modify: frontend/src/index.css
- Modify: frontend/src/features/auth/LoginPage.test.tsx
- Modify: frontend/src/features/auth/RegisterPage.test.tsx

**Interfaces:**
- Consumes auth-training-accent.jpg and existing AuthShell child content.
- Produces unchanged forms plus an aria-hidden, non-interactive image behind the desktop brand panel.

- [ ] **Step 1: Write failing preservation tests**
~~~tsx
expect(screen.getByTestId("auth-training-accent")).toHaveAttribute("aria-hidden", "true");
expect(screen.getByLabelText("ایمیل")).toBeVisible();
expect(screen.getByRole("button", { name: "ورود" })).toBeEnabled();
~~~
Add the corresponding registration assertion.

- [ ] **Step 2: Run red verification**

Run: npm test -- --run frontend/src/features/auth/LoginPage.test.tsx frontend/src/features/auth/RegisterPage.test.tsx

Expected: FAIL because the photo element is absent.

- [ ] **Step 3: Implement the accent**

Add this as the first brand-panel child:
~~~tsx
<img src={authTrainingAccent} alt="" aria-hidden="true" data-testid="auth-training-accent" className="brand-panel__photo" />
~~~
Style it behind brand content with pointer-events none, a petrol blend overlay, and fixed portrait crop. Hide it at the existing mobile breakpoint. Do not modify form markup, validation, auth calls, or routes.

- [ ] **Step 4: Run green verification**

Run:
~~~bash
npm test -- --run frontend/src/features/auth/LoginPage.test.tsx frontend/src/features/auth/RegisterPage.test.tsx
npm run lint
npm run build
~~~

Expected: all commands exit 0.

- [ ] **Step 5: Commit and push**
~~~bash
git add frontend/src/shared/AuthShell.tsx frontend/src/index.css frontend/src/features/auth/LoginPage.test.tsx frontend/src/features/auth/RegisterPage.test.tsx
git commit -m "feat(frontend): add restrained owner photo accents"
git push
~~~

### Task 5: Complete full regression and local review

**Files:**
- Modify: none unless a check finds a minimal, in-scope correction.

- [ ] **Step 1: Run complete automation**
~~~bash
npm test
npm run lint
npm run build
~~~
Expected: all commands exit 0; record Vitest counts.

- [ ] **Step 2: Smoke test local entry points**
~~~bash
curl -I http://localhost:5173/
curl -i http://localhost:8000/api/v1/auth/me
~~~
Expected: Vite root is HTTP 200; unauthenticated auth/me is normal HTTP 401 rather than server error.

- [ ] **Step 3: Review desktop, mobile, and reduced motion**

Open http://localhost:5173/. Verify full first viewport, scroll-driven subsequent scenes, only one active video, visible CTA in all scenes, CTA to /register, no mobile horizontal overflow, and still fallbacks under reduced motion.

- [ ] **Step 4: Commit only a necessary correction**

If verification needs code correction, commit and push only that in-scope change with a specific Conventional Commit message. Otherwise create no empty commit.

## Plan Self-Review

- Spec coverage: media and stable naming (Task 1); active-only playback, errors, reduced motion (Task 2); routing, CTA, scroll story, observer, responsive visual design (Task 3); restrained signed-in imagery (Task 4); regression and manual checks (Task 5).
- Scope protection: no backend, API, schema, migration, session, or protected-route behavior is changed.
- Placeholder scan: every implementation and test step is concrete; no omitted-work markers or generic instructions remain.
- Type consistency: LandingScene, landingScenes, LandingVideo, and PublicLandingRoute retain the same contracts in all tasks.
