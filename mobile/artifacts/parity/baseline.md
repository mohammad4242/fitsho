# Web ↔ Native parity baseline

Captured before Phase 0 inventory edits.

| Item | Baseline |
| --- | --- |
| Captured at | 2026-09-09T19:41:19+03:30 (Asia/Tehran) |
| Branch | `main` |
| Commit | `3f55f62bb01468c5e871cc9b1b47e45b97832672` |
| Remote | `origin` → `git@github.com:mohammad4242/fitsho.git` |
| Repository scope | `mobile/` implementation; `frontend/`, backend, contracts, and persisted models read-only |
| Master plan | `FITICIAN_WEB_NATIVE_PARITY_MASTER_PLAN.md` was already untracked at capture time and is preserved as user input |
| Node / npm | `v24.17.0` / `11.18.0` |
| Native package | `@fitician/mobile@0.1.0` |

## Installed native packages

Resolved with `npm ls --workspace @fitician/mobile --depth=0` before this inventory.

| Package | Installed |
| --- | --- |
| `expo` | `57.0.21` |
| `expo-router` | `57.0.20` |
| `expo-dev-client` | `57.0.18` |
| `react` / `react-dom` | `19.2.3` |
| `react-native` | `0.86.3` |
| `@tanstack/react-query` | `5.102.8` |
| `@react-native-community/netinfo` | `12.0.1` |
| `react-native-gesture-handler` | `2.32.0` |
| `react-native-reanimated` | `4.5.1` |
| `react-native-safe-area-context` | `5.7.0` |
| `react-native-screens` | `4.26.2` |
| `react-native-svg` | `15.15.4` |
| `react-native-vision-camera` | `5.2.3` |
| `react-native-vision-camera-worklets` | `5.2.3` |
| `react-native-worklets` | `0.10.1` |
| `@fitician/core` / `@fitician/body-vision` | local workspace packages, `0.1.0` |
| `@testing-library/react-native` | `13.3.3` |
| `jest` / `jest-expo` | `29.7.0` / `57.0.5` |
| `vitest` | `4.1.10` |
| `typescript` | `6.0.3` |

## Device and comparison context

No Android device, emulator, Android SDK, or usable ADB executable was available in this
checkout. Consequently, no screenshots or runtime measurements were taken.

| Context | Recorded value |
| --- | --- |
| Required comparison widths | 360 dp, 390 dp, 430 dp; not device-verified in this phase |
| Stress widths | 320 dp, 200% font scale; not device-verified in this phase |
| Android matrix | API 24 / Nexus 5X low, API 29 / Pixel 2 low, API 33 / Pixel 5 mid, API 36 / Pixel 8 mid |
| Device/model used for screenshots | None available |
| Logical screen width / font scale | Not available without a device |
| Language | Persian-first; startup calls `configureFiticianRtl()` and forces RTL when required |
| Product modes | `training`, `nutrition`, `both` |
| Account state | No authenticated comparison account or test credentials were used |
| Specialist state | Backend-confirmed coach/physician access is modeled; no specialist runtime screenshot was taken |
| Admin state | Web-only by product boundary; no native admin route exists |

## Checks at baseline

| Check | Result |
| --- | --- |
| `git diff --check` | PASS |
| `npm --prefix mobile run typecheck` | PASS |
| `npm --prefix mobile run validate:device-matrix` | PASS — device matrix is valid |
| `npm --prefix mobile run validate:maestro` | PASS — static Maestro flows are valid |
| focused native Jest route/home run | PASS — 2 suites, 4 tests |
| mobile Vitest invocation | BASELINE FAILURE — 130 files passed / 1 suite failed because Vitest attempted the RNTL `.tsx` suite and raised `Unexpected token 'typeof'`; 407 tests passed |

The Vitest result is recorded as existing baseline noise from the current script/configuration;
it is not attributed to Phase 0.

## Exact dirty-path snapshot

Captured with `git status --porcelain=v1` before creating parity artifacts. These paths are
outside the Phase 0 allowlist and must remain untouched.

```text
 M frontend/src/features/auth/api.test.ts
 M mobile/exercises/ExerciseDetailScreen.tsx
 D mobile/expo-env.d.ts
 M mobile/package.json
 M mobile/tsconfig.json
 M package-lock.json
?? "2026-06-11 16-09-09.mkv"
?? "2026-06-11 16-31-02.mkv"
?? Back_man.png
?? Back_woman.png
?? Bod.png
?? FITICIAN_WEB_NATIVE_PARITY_MASTER_PLAN.md
?? Fitsho_Exercise_Videos_Diagnosis_Report.pdf
?? Fitsho_Smart_Coach_Roadmap_FA.pdf
?? Foodcattalog.png
?? Man.png
?? Panel.png
?? Screenshot_20260810_201316_Chrome.jpg
?? Screenshot_20260810_201323_Chrome.jpg
?? Side_man.png
?? Side_woman.png
?? Source.png
?? Women.png
?? analyze.png
?? artifacts/nutrition_engine_100_profiles_audit.pdf
?? artifacts/nutrition_engine_phase5_final.pdf
?? backend/fitsho_20_random_profiles_debug_report.pdf
?? body.png
?? body1/
?? bodyanalysis.jpg
?? exercise_video_stats.jpg
?? fitsho_1000_profiles_audit_report.pdf
?? fitsho_100_profiles_after_soft_duration.pdf
?? fitsho_100_profiles_audit_report.pdf
?? fitsho_100_profiles_v2.pdf
?? fitsho_10_bodyweight_clean_report.pdf
?? fitsho_10_new_users_workout_plans.pdf
?? fitsho_10_random_users_post_fixes_workout_plans.pdf
?? fitsho_10_users_workout_engine_test.pdf
?? fitsho_10_users_workout_plans.pdf
?? fitsho_11_profiles_workout_plans.pdf
?? fitsho_200_profiles_eval_report.pdf
?? fitsho_20_random_profiles_debug_report.pdf
?? fitsho_20_random_profiles_debug_report_v4.pdf
?? fitsho_30_omnivore_nutrition_plans.pdf
?? fitsho_30_omnivore_nutrition_plans.pdf.
?? fitsho_30_profiles_debug_report.pdf
?? food.png
?? foodanalysis.jpg
?? frontend/public/Fitsho_Exercise_Videos_Diagnosis_Report.pdf
?? frontend/public/exercise_video_stats.jpg
?? frontend/public/fitsho_1000_profiles_audit_report.pdf
?? frontend/public/fitsho_100_profiles_audit_report.pdf
?? frontend/public/fitsho_10_bodyweight_clean_report.pdf
?? frontend/public/fitsho_200_profiles_eval_report.pdf
?? frontend/public/fitsho_food_catalogue.pdf
?? frontend/public/fitsho_nutrition_engine_100_profiles_audit.pdf
?? frontend/public/nutrition_engine_phase5_final.pdf
?? frontend/public/workout_engine_11_profiles.pdf
?? home.jpg
?? index.html
?? landfilm.mp4
?? latest.pdf
?? mobile.md
?? mobile/.local-agp.init.gradle
?? mobile/.local-tools/
?? mobile/artifacts/fitician-development-arm64-0.1.0.apk
?? mobile/home/MemberHomeScreen.rntl.test.tsx
?? mobile/modules/fitician-body-vision/android/.cxx/
?? mobile/modules/fitician-body-vision/android/build/
?? mobile/openjdk-21-jdk-headless_21.0.12+8-1~24.04_amd64.deb
?? plans.pdf
?? reports/.audit_after_extract.json
?? reports/.engine_codes.txt
?? reports/1000_preview-001.png
?? reports/1000_preview_p2-002.png
?? reports/11.pdf
?? reports/bw10_preview-01.png
?? reports/bw10_preview-02.png
?? reports/bw10_preview_fixed-02.png
?? reports/fitsho_1000_profiles_audit_report.html
?? reports/fitsho_1000_profiles_audit_report.pdf
?? reports/fitsho_100_profiles_audit_report.html
?? reports/fitsho_100_profiles_audit_report.pdf
?? reports/fitsho_100_profiles_v2.html
?? reports/fitsho_200_profiles_eval_report.html
?? reports/fitsho_200_profiles_eval_report.pdf
?? reports/fitsho_4_5_6_day_template_survival_after_raw.json
?? reports/fitsho_4_5_6_day_template_survival_after_raw.json.gz
?? reports/fitsho_4_5_6_day_template_survival_after_report.html
?? reports/fitsho_4_5_6_day_template_survival_after_report.pdf
?? reports/fitsho_4_5_6_day_template_survival_after_summary.json
?? reports/fitsho_4_5_6_day_template_survival_comparison.md
?? reports/fitsho_4_5_6_day_template_survival_debug_report.html
?? reports/fitsho_4_5_6_day_template_survival_raw.json
?? reports/fitsho_4_5_6_day_template_survival_raw.json.gz
?? reports/fitsho_food_catalogue.pdf
?? reports/fitsho_nutrition_100_profiles_results.json
?? reports/fitsho_nutrition_development_audit.html
?? reports/fitsho_nutrition_development_audit.json
?? reports/fitsho_nutrition_development_audit.pdf
?? reports/fitsho_nutrition_engine_100_profiles_audit.html
?? reports/fitsho_nutrition_engine_100_profiles_audit.pdf
?? reports/fitsho_nutrition_holdout_audit.html
?? reports/fitsho_nutrition_holdout_audit.json
?? reports/fitsho_nutrition_holdout_audit.pdf
?? reports/fitsho_nutrition_stress_audit.html
?? reports/fitsho_nutrition_stress_audit.json
?? reports/fitsho_nutrition_stress_audit.pdf
?? reports/fitsho_specialization_priority_after_raw.json
?? reports/fitsho_specialization_priority_after_raw.json.gz
?? reports/page_preview-01.png
?? reports/page_preview-02.png
?? reports/page_preview_fixed-02.png
?? reports/report.pdf
?? reports/session_coherence_template_audit_after.json
?? reports/session_coherence_template_audit_luna_high.json
?? reports/start_server.py
?? reports/v2_preview-01.png
?? reports/workout_engine_10_profiles.html
?? reports/workout_engine_10_profiles.pdf
?? reports/workout_engine_12_profiles.html
?? reports/workout_engine_12_profiles.pdf
?? taghziye.jpg
?? workout.jpg
?? "\332\251\330\247\330\252\330\247\331\204\331\210\332\257_\330\255\330\261\332\251\330\247\330\252(1).zip"
```
