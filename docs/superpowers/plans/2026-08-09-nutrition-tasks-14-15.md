# Nutrition Tasks 14-15 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the completed Nutrition system and deliver reproducible repository-level validation and operating documentation.

**Architecture:** Reuse Fitsho's authenticated FastAPI routes, encrypted AI credential store, PostgreSQL advisory locking, immutable Nutrition records, and private filesystem roots. Add narrowly scoped security services and persisted operational events instead of a new queue or cache service.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, Alembic, cryptography/HMAC, pytest, React, TypeScript, Vitest.

## Global Constraints

- Do not start Task 16 or invent requirements beyond the final Nutrition specification.
- Never expose plaintext credentials, private storage keys, medical free text, or external-provider payloads in metrics or logs.
- Preserve historical plans, quotes, reviews, audits, and unrelated workout behavior.
- Keep OpenRouter restricted to separately consented food-photo estimation.

---

### Task 1: Security and privacy hardening

**Files:**
- Create: `backend/app/nutrition/security.py`
- Create: `backend/tests/nutrition/test_security_hardening.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/nutrition/food_photo_service.py`
- Modify: `backend/app/nutrition/clinical_service.py`
- Modify: `backend/app/nutrition/router.py`

**Interfaces:**
- Produces signed short-lived private-file grants, per-user action limits, retention cleanup, and safe audit events.

- [ ] Write failing ownership, signed-token, expiration, upload-validation, duplicate, rate-limit, and retention tests.
- [ ] Run the focused tests and confirm failures are caused by missing hardening behavior.
- [ ] Implement minimal security services and route integration.
- [ ] Run focused and complete Nutrition tests.
- [ ] Commit and push Task 14.

### Task 2: Reliability and observability hardening

**Files:**
- Create: `backend/alembic/versions/20260809_50_harden_nutrition_operations.py`
- Modify: `backend/app/nutrition/models.py`
- Modify: `backend/app/nutrition/price_update_service.py`
- Modify: `backend/app/nutrition/food_photo_service.py`
- Modify: `backend/app/nutrition/router.py`
- Modify: `backend/tests/nutrition/test_food_pricing.py`
- Modify: `backend/tests/nutrition/test_food_photo_estimation.py`

**Interfaces:**
- Produces persisted provider-health, AI usage/error, private-file access, and cleanup metrics without sensitive payloads.

- [ ] Write failing provider-health, AI usage/error, retry, idempotency, and audit tests.
- [ ] Run focused tests and confirm RED.
- [ ] Add migration, models, and minimal persistence hooks.
- [ ] Verify downgrade/upgrade and tests.
- [ ] Include in the focused Task 14 commit.

### Task 3: Privacy and operations documentation

**Files:**
- Create: `docs/nutrition-security-privacy.md`
- Modify: `.env.example`
- Modify: `docs/nutrition-implementation-design.md`

**Interfaces:** Documents retention, access, incident-safe logging, secrets, scheduler behavior, and manual cleanup.

- [ ] Document implemented controls and configuration with no real secrets.
- [ ] Verify documentation commands against the current CLI.
- [ ] Include in the Task 14 commit.

### Task 4: Final documentation and validation

**Files:**
- Modify: `README.md`
- Modify: `docs/running-locally.md`
- Create: `docs/nutrition-api.md`
- Create: `docs/nutrition-migration-notes.md`
- Create: `docs/nutrition-scientific-policy.md`
- Create: `docs/nutrition-micronutrients.md`
- Create: `docs/nutrition-medical-review.md`
- Modify: `docs/nutrition-food-data-provenance.md`
- Modify: `docs/nutrition-weekly-planner.md`

**Interfaces:** Produces the Task 15 operator/developer handoff and verification record.

- [ ] Complete every document named by section 47 of the specification.
- [ ] Run backend `pytest`, `ruff check`, and `mypy` with repository-required paths.
- [ ] Run frontend test, lint, and build.
- [ ] Verify one-head Alembic, upgrade from revision 49, and a fresh zero-to-head migration.
- [ ] Run workout, Nutrition acceptance, authorization, OpenRouter-disabled, and live-price-unavailable tests.
- [ ] Verify no generated artifacts are staged and preserve unrelated user changes.
- [ ] Commit and push Task 15, report exact evidence, and stop.
