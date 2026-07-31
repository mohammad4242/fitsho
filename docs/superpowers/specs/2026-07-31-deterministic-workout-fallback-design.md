# Deterministic workout fallback

## Goal

Return a valid workout plan when all configured AI models fail, while preserving AI as the primary generator.

## Architecture

`DeterministicWorkoutPlanGenerator` consumes the already-filtered `CandidateSet`, the user generation profile, and `WorkoutGenerationPolicy`. It selects balanced exercises deterministically, assigns prescriptions from the user's fitness goal and experience, stays inside session-duration limits, and returns the existing `WorkoutPlanModelOutput` contract.

`WorkoutGenerationService` continues trying configured AI providers first. After all provider, output, repair, or semantic-validation failures, it invokes the deterministic generator when `workout_deterministic_fallback_enabled` is true. The existing validator validates the fallback before persistence. Successful fallback plans use model ID `fitsho-deterministic-v1`.

## Rules

- Use only candidates already approved for equipment, difficulty, and cautions.
- Prefer strength compounds, then core/isolation, while rotating movement patterns and muscles across days.
- Use policy-approved sets, repetitions, rest, and RIR values.
- Generate distinct ordered day signatures and remain inside the time budget.
- Never bypass the existing validator.

## Failure boundary

AI availability is no longer required for a valid request. Failures remain possible only for invalid/incomplete profile data, insufficient eligible exercises, concurrent generation, changed inputs, validator defects, or database persistence failures.

## Testing

Unit tests cover determinism, candidate-only output, multi-day uniqueness, duration, and validation. Service tests prove AI success remains primary and provider/output failures activate the fallback.
