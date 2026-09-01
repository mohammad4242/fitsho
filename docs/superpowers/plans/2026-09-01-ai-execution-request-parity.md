# AI execution request parity

## Goal

Keep Fitsho task semantics in Backend `StructuredGenerationRequest` builders while
allowing API/OpenRouter and Agent Service to execute the same request.

## Scope

1. Add parity tests for workout, body preflight, body analysis, and food-photo
   requests.
2. Preserve image labels and bytes across the Agent Service multipart boundary.
3. Reuse the production food-photo request builder in smoke infrastructure.
4. Keep `food_price_search` explicitly smoke-only because weekly price updates use
   direct marketplace/public providers and have no production LLM request.
5. Add runner and source-regression tests proving no Agent Service task prompt can
   drift from Backend task definitions.

## Verification

- Focused Backend and Agent Service tests.
- Ruff and mypy for modified Python files.
- Frontend tests/build if the Admin wiring surface changes.
- Final diff and source audit for duplicated task prompts.
