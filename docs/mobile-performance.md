# Fitician mobile performance acceptance

`mobile/platform/performance.ts` is the authoritative budget registry. Samples
are bounded, numeric, and contain no route, request, account, media, laboratory,
or medical payload.

| Metric | Budget | Runtime measurement |
| --- | --- | --- |
| Cold start | ≤ 3,000 ms | Root layout completion |
| Screen transition | ≤ 300 ms | Route change until native interactions settle |
| Large list render | ≤ 250 ms | Exercise catalogue page commit |
| Image processing | ≤ 1,500 ms | Privacy-cropped body-photo encoding |
| Peak memory | ≤ 200 MB | `recordMemoryPeak` from the device profiler |
| Battery drain | ≤ 8% per hour | `recordBatteryDrain` from a controlled device run |
| Video cache hit | ≤ 150 ms | Persisted public exercise-video lookup |
| Upload | ≤ 30,000 ms | Multipart executor duration |

Release acceptance records p95 for each metric, with every recorded sample also
required to remain within its budget. A launch cohort is accepted at ≥99.5%
crash-free launches across at least 100 clean launches per representative device
tier. The launch denominator, crash count, OS/API level, device model, app
version, commit, and build profile are retained with the report.
`buildMobilePerformanceReport` calculates p95, reports missing metrics, validates
the cohort fields, and accepts a report only when all metrics and the launch
cohort satisfy these rules.

The automated harness covers budget evaluation, bounded samples, cold-start
completion, route transitions, list commits, privacy image processing, video
cache reads, uploads, and resource sample units:

```bash
npm --prefix mobile run test
npm --prefix mobile run test:native
npm --prefix mobile run typecheck
npm --prefix mobile run validate
```

Physical API 24, 29, 33, and 36 runs and low/mid-range device measurements are
release-gate evidence. They require an Android development build and profiler;
the current repository environment has Android SDK/ADB tooling but no attached
device or configured AVD. Those measurements are not claimed by the automated
checks above.

## Web-native parity Phase 27 verification

- Cold start and route transitions are measured from the native root layout and
  `InteractionManager`-settled pathname changes.
- Exercise catalogue commits are measured around a bounded 12-item page. Long
  nutrition and specialist collections keep their existing API-owned bounds and
  are not replaced with unbounded decorative rendering.
- Catalogue media does not autoplay. The public exercise-video cache remains
  hashed, LRU-bounded to 50 entries/128 MiB, validates public video paths, and
  records persisted cache reads against the 150 ms budget. Exercise detail
  playback prefers the persisted local URI and exposes native download/remove
  actions while retaining online playback as fallback.
- Privacy-cropped body-photo encoding and multipart uploads use the shared
  recorder. User query persistence remains restricted to the allowlisted
  workout/nutrition plan policies.
- No WebView, blur layer, animation library, or list-wide gradient/shadow
  expansion was added for visual parity. Cold-start, transition, scroll,
  media, memory, camera, and low/mid-range device measurements still require
  the physical Android matrix.
