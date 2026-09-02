# Antigravity Food-Price Schema Compatibility Design

## Goal

Make the existing Agent Service food-price research request executable by the
configured Antigravity runner and make the interactive price inquiry bounded
enough to complete reliably without changing Backend price authority or direct-
provider behavior.

## Confirmed failure

The canonical Pydantic schema for `FoodPriceResearchOutput` contains a
`Decimal` string branch with a Python regular-expression negative lookahead.
Antigravity sends the schema to a Go/RE2-backed structured-output endpoint. The
endpoint rejects that pattern with `INVALID_ARGUMENT`, before model execution.
The runner currently exposes that process failure as `provider_unavailable`,
which hides the actual cause.

## Constraints

- Agent Service remains the only execution path when `FOOD_PRICE_SEARCH` is
  enabled.
- The LLM remains evidence-only; Backend retains matching, normalization,
  confidence, acceptance, persistence, and review authority.
- The canonical Backend response schema remains the final validation contract.
- Interactive single-food inquiry uses one bounded evidence pass; scheduled
  multi-food price updates retain the existing source-expansion policy.
- The original schema remains the final validation contract.
- No direct-provider fallback is added.
- No secrets, raw provider output, or user data are added to logs or errors.

## Chosen design

Add a small, generic Antigravity transport compatibility step in
`agent-service/app/runners/antigravity.py`:

1. Validate the original JSON schema as today.
2. Create a deep compatibility copy only for the `agy --json-schema` file.
3. Rewrite the known Pydantic `Decimal` string pattern to an equivalent
   RE2-compatible numeric pattern. Preserve the number branch, nullability,
   bounds, required fields, and all unrelated schema keywords.
4. Keep validating the returned payload against the original request schema.
5. Classify provider CLI schema/argument errors as `invalid_request` and map
   explicit authentication failures, including `authentication required` and
   `not logged into`, to `unauthorized`.
6. Set Antigravity's cache to the writable, executable Agent Service volume;
   the compose `/tmp` mount is `noexec`, and the default home cache may be
   root-owned in an existing named volume.

The interactive price prompt uses a compact public Torob JSON search endpoint.
Backend builds its URL per request with the canonical Persian food name, a
fresh search session, and a small result window. Agent may use the URL-content
tool once and open that tool's returned response file once; it must not follow
product pages, request offsets, or enter a web-research loop. The second source
expansion request is disabled only for the interactive single-food inquiry, so
one valid quote can be shown as a candidate while Backend still owns matching,
normalization, and review status.

The runner remains task-agnostic: it does not know food-price fields or prompts.
The only transport-specific knowledge is compatibility for the exact unsupported
regular-expression form emitted by the shared Pydantic serializer.

## Data flow

```text
Backend canonical request with fresh compact Torob search URL
        |
        v
Agent Service validates original schema
        |
        v
Antigravity runner writes compatible copy to agy
        |
        v
agy performs structured generation/web search
        |
        v
Runner validates output with original schema
        |
        v
Backend applies price evidence policy and persistence rules
```

## Error handling

- Unsupported schema syntax is a safe `invalid_request` error.
- Missing/expired Agent authorization is a safe `unauthorized` error.
- Provider outages remain `provider_unavailable`.
- Browser and embedded search tools use the executable cache path supplied by
  the runner instead of the `noexec` temporary filesystem.
- A single-food inquiry may return one accepted Torob quote as a candidate;
  scheduled updates still record insufficient independent sources for review
  rather than treating one quote as a trusted market cluster.
- The Backend price researcher continues to preserve its current bounded
  failure behavior and does not fall back to direct providers.

## Tests and acceptance

Add runner tests that:

- prove the incompatible Decimal pattern is rewritten only in the CLI schema
  file;
- prove the original request schema is still accepted for output validation;
- classify invalid schema arguments as `invalid_request`;
- classify authentication-required text as `unauthorized`.

Add Backend request tests for the compact Torob URL, fresh session parameters,
and single-food no-expansion behavior. Run the focused Agent Service and
Backend price tests, then run a live read-only egg research request through the
production Backend provider path. The live check must show that Agent Service
reaches model execution, returns a matching quote, and writes no catalogue
data. Also smoke the AI workout-program task to confirm its normal structured
schema path is unaffected.
