# Fitician Web

The existing `frontend/` package is the Fitician Web App. Run commands from the repository root with npm workspaces:

```bash
npm run dev --workspace frontend
npm run build --workspace frontend
npm run preview --workspace frontend
```

The production build includes an installable PWA manifest, icons, and a generated service worker. Updates are prompted in-app and never reload an active form automatically.

PWA installation and camera access require a reachable HTTPS origin in production. On iPhone or iPad Safari: open the site, use Share, choose **Add to Home Screen**, enable **Open as Web App**, then choose **Add**.

Browser regression tests use a production preview:

```bash
npm run test:e2e --workspace frontend
npm run test:e2e:webkit --workspace frontend
```

Install the Playwright Chromium and WebKit browsers once with `npx playwright install chromium webkit`.

Caching is deliberately conservative. The service worker precaches only the application shell, generated JavaScript/CSS, fonts, manifest, and PWA icons. `/api`, `/media`, uploads, body-analysis data, profile/nutrition photos, and large reports or exercise/MediaPipe assets are network-only and are never stored as runtime user-data cache.
