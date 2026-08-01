# AI model test upstream diagnostics

## Goal

Show why a Zen model test failed without retaining sensitive request data.

## Design

`WorkoutProviderError` will optionally carry the upstream HTTP status, error type/code, and a sanitized upstream error message. The provider extracts those fields only from a JSON `error` object. It never retains request bodies, headers, response bodies, or credentials.

The model-test history stores the three optional diagnostic values and returns them only through the admin API. The admin event view displays them under failed test events. Existing records remain null.

## Safety

Messages are limited to 500 characters and redact bearer tokens, API-key shaped values, and common credential fields before persistence. Non-JSON failures retain only their HTTP status.

## Verification

Tests cover upstream error extraction/redaction, persistence and admin API output, frontend rendering, migration, and full project checks.
