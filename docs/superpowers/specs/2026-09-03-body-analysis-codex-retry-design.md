# Body Analysis Retry After Provider Change

## Goal

Allow a submitted Body Analysis session to be tried again after its previous provider
exhausted the retry budget, while reusing the already stored standardized photos.

## Root cause

`BodyAnalysisService._assert_retry_available` currently counts every analysis revision
created after the latest photo change. The limit is therefore shared by all providers and
models. A session with three failed Antigravity revisions cannot be retried after the
administrator switches the Body Photo Analysis task to Codex, even though the new request
would use a different execution path.

## Design

- Count the retry budget within the current provider execution scope and the current photo
  snapshot. The existing provider name is the durable execution-scope identity.
- Keep the existing total of one initial attempt plus `retry_limit` retries within that
  scope. Same-provider retries remain bounded.
- Let a provider change create a new analysis revision using the current runtime config.
- Reuse the prior v4 input snapshot when the three stored photo records are unchanged, so no
  new upload or consent flow is required.
- Preserve all previous analysis rows, photo storage, owner authorization, stale-analysis
  recovery, and safe failure behavior.

## User flow

1. The user opens the existing failed analysis session.
2. The existing retry action calls the owner-scoped retry endpoint.
3. The backend reads the current AI task configuration, which is now Codex.
4. The backend creates a new queued revision and sends the three stored body-photo
   references to Agent Service.
5. The result page continues polling and shows the queued/analyzing/result or safe failure
   state without opening another page or requiring photo re-upload.

## Verification

- Service regression: three failed revisions under an old provider can be retried under a
  new provider with the same stored-photo snapshot.
- Existing retry-limit, stale-analysis, photo-change confirmation, owner authorization,
  and Agent Service stored-image tests remain green.
- Run focused backend tests, frontend Body Analysis tests, lint, build, and a live runtime
  check. Do not claim a real user analysis succeeded unless Agent Service logs and the
  database show the new revision and stored-image request.
