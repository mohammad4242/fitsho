# AI Model Test Upstream Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist sanitized Zen error metadata for failed model tests and show it to administrators.

**Architecture:** Extend the provider error boundary, persist optional metadata on `AiModelTestRun`, expose it from the existing admin history API, and render it only in the administrator event list.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, React, TypeScript, pytest, Vitest.

## Tasks

1. Add failing provider tests; attach sanitized HTTP status, error type, and message to provider errors.
2. Add test-run columns and Alembic migration; persist and expose the metadata from the existing admin route.
3. Add frontend type, API-fixture, and event rendering tests; render diagnostics for failed model tests.
4. Run backend/frontend suites, restart preview, commit, and push.
