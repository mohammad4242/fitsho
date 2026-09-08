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
the current repository environment has no Android SDK or emulator, so those
measurements are not claimed by the automated checks above.
