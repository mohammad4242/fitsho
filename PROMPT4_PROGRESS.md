# Current stage

Complete - final closeout

# Completed stages

- Stage 0 - discovery and baseline verification
- Stage 1 - canonical exercise semantics
- Stage 2 - substitution metadata audit
- Stage 3 - canonical equipment source
- Stage 4 - curated substitution knowledge
- Stage 5 - canonical substitution policy
- Stage 6 - unified substitution engine
- Stage 7 - migrate all substitution callers
- Stage 8 - limitation-aware regressions
- Stage 9 - home and limited equipment
- Stage 10 - observability and quality
- Stage 11 - final closeout

# Commit SHAs

- Starting SHA: `1f11d48d395e3903c5645cd590d114cbaaa941d2`
- Stage 1: `b8dd608b4bed1ed18c89b19bd86de5a9c94f43be`
- Stage 2: `ee7f38198e2adb3e7aa9bcf5ee9288a6db4623ad`
- Stage 3: `b94c09aadbe7ece224bfcd46563272c0816a2407`
- Stage 4: `c7999b64a0e4eba6157a662954665986256ad99c`
- Stage 5: `055e2a083ce123e833062f1979639a8ee5193cf9`
- Stage 6: `3e20cf8ad757171844241d8daeb7b1b267c4186d`
- Stage 7: `caf52991896d9ff4707af0e63f12f9e1d2c483cf`
- Stage 8: `eedbd47a979ecfd5de373e8657d0434256bff4c2`
- Stage 9: `3bdb347b8bd3611af1ff8c3a48d8487839294bff`
- Stage 10: `eb1e77fc705ab31acd98e9020245b388f963cb7e`
- Stage 11: `a0437bd5c802f63eeec30436be2756db4b6deebe`

# Migrations

- `20260824_107` - add nullable `user_profiles.available_equipment` JSON inventory and preserve legacy setup consistency

# Important decisions

- Existing structured exercise metadata is present; `ExerciseCandidate` lacks only `muscle_focus` from the required semantic role.
- Current request flow is profile snapshot -> legacy home-equipment mapping -> `ProgramGenerationRequest` -> normalized constraints -> hard eligibility -> template or dynamic construction -> prescription/volume repair -> validation/persistence/output.
- Concrete replacement ranking is centralized today in `replacement_ranker.py`, but compatibility policy is independently encoded in `slot_compatibility.py` and caller-specific scopes.
- Replacement callers are template slot resolution and displayed alternatives in `template_sessions.py`, dynamic displayed alternatives in `session_builder.py`, and repair alternatives in `volume_repair.py`.
- Persisted `ExerciseAlternative` is directional knowledge, but the program engine does not load it; router and workout-cycle fallback paths expose it directly when generated substitution IDs are absent.
- `workout_cycles` records user-selected replacements and `adaptation_policy.py` derives historical preference/safety evidence; these are downstream evidence paths, not concrete catalog rankers.
- Equipment resolution is duplicated in `WorkoutCandidateSelector._available_equipment` and `WorkoutGenerationService._available_equipment`; explicit request-time overrides already exist but no persisted profile inventory exists.
- `effective_required_equipment()` is the shared catalog requirement helper and already enforces bodyweight vertical-pull bar requirements; multi-equipment catalog sets use subset matching.
- `ExerciseRoleSignature` is an immutable structured role with canonical secondary-muscle ordering; it excludes IDs, titles, display snapshots, equipment, and user constraints.
- Metadata audit scope is persisted programmable resistance exercises: exercise content, programmable, non-cardio, non-mobility. It never uses name inference or writes catalog rows.
- Role coverage only includes rows with complete persisted role metadata; current live rows therefore report zero complete roles rather than hiding missing metadata with inference.
- Persisted explicit equipment is canonical when present; `NULL` resolves through legacy home setup or the categorized gym inventory.
- `resolve_available_equipment()` is the one profile-to-engine resolver; profile responses, candidate selection, deterministic generation, AI payloads, signatures, and `ProgramGenerationRequest` use the effective inventory.
- User inventory rejects empty, duplicate, unknown, and `Equipment.OTHER` values. Existing categorized equipment enums are supported without adding new enum values.
- Switching training location clears stale inventory in the frontend; legacy `home_training_setup` remains derived and backward-compatible.
- Curated `ExerciseAlternative` knowledge is represented as sorted target-owned IDs on immutable candidates; directionality is preserved and reverse edges are not inferred.
- Curated alternatives are a rank preference only after existing hard eligibility and slot compatibility checks.
- `substitution_policy.py` is the sole movement-degradation policy: exact intent plus controlled back, quadriceps, posterior-chain, and core fallbacks.
- Horizontal and vertical push are not substitution-equivalent; primary-strength roles remain exact-pattern under a strength goal.
- Slot/template compatibility delegates movement-family expansion to the canonical policy, and the legacy concrete ranker intersects caller scope with it.
- `substitution_engine.py` owns hard eligibility, policy application, tier A-D classification, deterministic cause-aware ranking, explanation codes, and explicit no-replacement decisions.
- Cause-aware ordering never overrides semantic tier; all request constraints are hard filters before ranking.
- Template, dynamic, and volume-repair alternatives now call the unified engine directly; `replacement_ranker.py` is forwarding-only.

# Tests/results

- Stage 0 focused replacement/profile/equipment: `147 passed`.
- Stage 0 full Program Engine: `736 passed`.
- Stage 0 mypy scope: `78 source files`, no issues.
- Stage 0 tracked diff and `git diff --check`: clean.
- Stage 0 push: no-op; remote `main` verified at `1f11d48d395e3903c5645cd590d114cbaaa941d2`.
- Stage 1 TDD red: missing semantics module and missing candidate propagation failed as expected.
- Stage 1 focused: `3 passed`; Program Engine plus service/catalog regressions: `821 passed`.
- Stage 1 mypy: `3 source files`, no issues; changed-file Ruff and diff checks passed.
- Stage 1 remote `main` verified at `b8dd608b4bed1ed18c89b19bd86de5a9c94f43be`.
- Stage 2 TDD red: missing audit module failed; Sol review regression reproduced the ORM secondary-muscle crash before correction.
- Stage 2 focused: `3 passed`; exercise catalog plus full Program Engine: `878 passed`.
- Stage 2 mypy and changed-file Ruff passed; `git diff --check` passed.
- Stage 2 live audit: 306 rows; 306 missing persisted substitution groups, axial and impact metadata, 306 without curated outgoing alternatives, 305 missing skill/stability, 306 missing body position/laterality, 49 OTHER patterns, 34 OTHER types, 23 Equipment.OTHER, 3 missing primary muscle, 0 complete role groups.
- Stage 2 report artifact: `backend/var/prompt4-stage2-substitution-audit.json`, SHA-256 `3e5311968ab04bda77eb03a239e9a7a507801dac3bc3313f97d30eef71845006`.
- Stage 2 remote `main` verified at `ee7f38198e2adb3e7aa9bcf5ee9288a6db4623ad`.
- Stage 3 TDD red: missing resolver/import and ten frontend equipment-contract failures occurred before implementation.
- Stage 3 backend focused/broad: `165 passed` and `930 passed`; mypy checked `241 source files`; changed-file Ruff passed.
- Stage 3 frontend: `55 passed`; Oxlint and production build passed.
- Stage 3 migration: upgrade to head, downgrade to `c0b1dd908291`, and re-upgrade verified at `20260824_107`.
- Stage 3 diff checks passed; remote `main` verified at `b94c09aadbe7ece224bfcd46563272c0816a2407`.
- Stage 4 TDD red: curated forward preference failed before the rank-key change.
- Stage 4 focused: `102 passed`; full Program Engine plus workout service: `785 passed`.
- Stage 4 mypy, changed-file Ruff, and diff checks passed; remote `main` verified at `c7999b64a0e4eba6157a662954665986256ad99c`.
- Stage 5 TDD red: the policy module was absent; the first integration run exposed a legacy direct-replacement expectation before caller scope was correctly intersected.
- Stage 5 focused: `87 passed`; full Program Engine: `753 passed`; mypy checked `242 source files`.
- Stage 5 changed-file Ruff and diff checks passed; remote `main` verified at `055e2a083ce123e833062f1979639a8ee5193cf9`.
- Stage 6 TDD red: the unified engine module was absent; initial green work exposed test-fixture constraints for vertical-pull equipment and conservative derived caution tags before correction.
- Stage 6 focused: `8 passed`; full Program Engine: `768 passed`; mypy checked `243 source files`.
- Stage 6 changed-file Ruff and diff checks passed; remote `main` verified at `3e20cf8ad757171844241d8daeb7b1b267c4186d`.
- Stage 7 full Program Engine: `769 passed`; mypy checked `243 source files`; changed-file Ruff, format, and diff checks passed.
- Stage 7 grep verified one concrete production ranker; remote `main` verified at `caf52991896d9ff4707af0e63f12f9e1d2c483cf`.
- Stage 8 focused limitation matrix: `9 passed`; full Program Engine: `778 passed`.
- Stage 8 changed-file Ruff, format, and diff checks passed; remote `main` verified at `eedbd47a979ecfd5de373e8657d0434256bff4c2`.
- Stage 9 exact home-equipment matrix: `13 passed`; full Program Engine: `791 passed`.
- Stage 9 changed-file Ruff, format, and diff checks passed; remote `main` verified at `3bdb347b8bd3611af1ff8c3a48d8487839294bff`.
- Stage 10 focused observability/invariant suite: `110 passed`; full Program Engine: `796 passed`.
- Stage 10 mypy checked `244 source files`; changed-file Ruff, format, diff, and single-ranker checks passed.
- Stage 10 remote `main` verified at `eb1e77fc705ab31acd98e9020245b388f963cb7e`.
- Stage 11 substitution tests: `37 passed`; exercise catalog: `140 passed`; profile/equipment: `139 passed`; template tests: `78 passed`.
- Stage 11 full Program Engine: `796 passed`; full backend: `2230 passed, 1 skipped` (live Zen opt-in only).
- Stage 11 affected frontend: `55 passed`; TypeScript, Oxlint, and production build passed.
- Stage 11 mypy checked `244 source files`; changed-file Ruff, format, and diff checks passed.
- Stage 11 home benchmark baseline -> current: generation `5/8 -> 5/8`, UNSAT `3 -> 3`, comparable substitution success `44/66 -> 39/66`, exact-role count `32 -> 32`, exact-role rate `0.7273 -> 0.8205`, movement-family fallback `11 -> 7`, safety/equipment violations `0 -> 0`, determinism `100% -> 100%`.
- Stage 11 Phase 11.9 baseline -> current: generation `134/150 -> 134/150`, quality pass rate `0.6567 -> 0.6567`, safety/equipment/engine violations `0 -> 0`, determinism `100% -> 100%`; template success `56 -> 54` and fallback activation `78 -> 80` under stricter substitution semantics.
- Stage 11 remote `main` verified at `a0437bd5c802f63eeec30436be2756db4b6deebe`.

# Known unresolved issue

- Pre-existing Ruff findings remain in `app/workouts/program_engine/duration_policy.py:20,22` E402.
- The live catalog lacks persisted substitution metadata broadly; no catalog rows were mass-fixed in Stage 2.
- The home fixture catalog has no populated muscle-focus metadata, so focus preservation is correctly reported as not measurable rather than inferred.
- The pre-existing Phase 11.9 Markdown reporter raises `KeyError: legacy_constrained_duration_count` after successfully writing JSON/CSV; baseline and current have the same reporter failure.
