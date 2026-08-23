# Phase 11 deterministic resistance-training benchmark

## Scope

This artifact evaluates the complete deterministic resistance-training generation pipeline after the Phase 10 gate. It does not change template scoring, the supported Days x ExperienceLevel matrix, canonical tags, sex logic, duration scoring, dynamic fallback policy, or runtime AI behavior.

## Harness boundary

The benchmark will use deterministic profile fixtures mapped to the existing `ProgramGenerationRequest` contract, the real deterministic exercise-candidate catalog fixture, the real persisted-template reference shape, `RULESET`, and the production `generate_program` entrypoint. The mapping will retain profile-level inputs and the resulting normalized/program traces so the report can distinguish request mapping, template-path behavior, dynamic construction, and final validation.

The supported matrix will contain approximately five diverse profiles per valid cell, covering all 15 cells without creating a Cartesian product. Explicit unsupported combinations will be negative cases and will not count as successful population profiles.

## Outputs

The runner will write:

- machine-readable JSON containing fixture inputs, raw generation result, template trace, final program metrics, audit findings, category, and determinism fingerprints;
- a concise Markdown summary containing population coverage, outcome counts, fallback statistics, quality rates, grouped failures, confirmed fixes, and remaining risks.

Generated artifacts live under `backend/var/benchmarks/phase11/` and are not source fixtures. The committed harness and fixtures remain reproducible without committing generated output.

## Audit contract

Every case receives exactly one outcome category: `PASS`, `PASS_WITH_CONSTRAINTS`, `QUALITY_ISSUE`, `FALLBACK_SUCCESS`, `UNSATISFIED`, or `ENGINE_BUG`. The audit checks safety and availability, structural/template preservation, priority and body-analysis emphasis, volume, prescription, duration, recovery, exercise selection, and cardio. Existing engine quality metrics are recorded without replacing them.

Fallback accounting reports template attempts, template successes, fallback activations, fallback successes, unsatisfied generations, and exact reason codes. Negative matrix cases are reported separately.

## Determinism and bug policy

A representative deterministic subset is run repeatedly. Canonical JSON fingerprints compare template selection, score traces, exercises, prescriptions, schedule, validation, and decision traces. Any mismatch is an `ENGINE_BUG` and is reproduced before a regression test is added.

Only isolated confirmed engine bugs may receive a small fix and permanent regression test. Larger quality findings remain documented in the benchmark report for a later focused phase. No rule is tuned to improve aggregate percentages.

## Verification

Before the benchmark, the branch is reconciled with `origin/main` using a non-destructive merge while preserving unrelated working-tree changes. The Phase 10 integration gate is rerun after reconciliation. The benchmark harness, focused tests, relevant Phase 10 tests, and backend lint/type checks are run before handoff. No Phase 12 work is started.
