# Private Media Storage-Key Transport Design

**Status:** Approved implementation direction supplied by the task request.

## Goal

Replace production Body/Food image transfer to the internal Agent Service with
validated storage references. The Backend remains the owner of prompts, task
payloads, schemas, image metadata, and database storage keys. The Agent Service
resolves only those references inside a read-only shared media mount and passes
the original paths to the selected CLI runner.

## Scope and invariants

- Keep `backend/var/private/body-photos` and `backend/var/private/food-photos`
  in place; mount those same host directories read-only into Agent Service.
- Do not change database tables, storage-key values, records, prompts, task
  schemas, model selection, reasoning behavior, authentication, or frontend.
- PostgreSQL receives no private-media mount.
- `ImageInput` represents exactly one inline Base64 source or one stored
  `storage_scope` plus `storage_key` source.
- Production Body and Food requests use stored sources. Inline sources remain
  only for synthetic/compatibility multipart tests and task-smoke fixtures.

## Data flow

Body analysis builds one stored-image tuple from the three `BodyPhoto` rows and
uses that same tuple for photo preflight and analysis. Food photo processing
continues to read, validate, normalize, and store the upload first, then builds
one `food` storage reference from the returned key.

Provider selection remains in the Backend. `build_task_provider` injects a
Backend `PrivateMediaResolver` into `OpenRouterProvider`; OpenRouter resolves
stored references and Base64-encodes only at its external API boundary.
`AgentServiceProvider` sends stored references as JSON to
`POST /v1/analyze-stored-images`, preserving the existing generation metadata
inside a composed `generation` object. It sends inline references through the
existing multipart endpoint and rejects mixed batches.

## Security boundaries

The Backend resolver maps only `body` and `food` scopes to configured Backend
roots. The Agent Service resolver maps the same scopes to
`AGENT_SHARED_PRIVATE_MEDIA_ROOT/body` and `/food`. Both reject absolute keys,
traversal, empty or unexpected path segments, unsupported extensions, missing or
non-file targets, and symlink escapes. The Agent Service also enforces image
count, per-file, total-size, MIME/extension, and decoded-image validity limits.

The Agent Service request workspace remains available for schemas, output, and
small runner metadata only. Stored image files are never copied into it. A
shared runner helper accepts image paths only after they resolve beneath the
current request workspace or the configured shared-media root. Runner-specific
constructors receive that root from `Settings`, never from HTTP input. Existing
CLI sandbox/read-only behavior remains unchanged.

## Agent Service contract

The new JSON body is composed as:

```json
{
  "generation": {
    "agent": "antigravity",
    "model_id": "vision-model",
    "profile_id": "profile-id",
    "system_prompt": "Backend-owned prompt",
    "input_payload": {},
    "response_schema": {},
    "schema_name": "fitsho_task",
    "temperature": 0,
    "max_output_tokens": 512,
    "timeout_seconds": 45
  },
  "images": [
    {
      "label": "front",
      "mime_type": "image/jpeg",
      "storage_scope": "body",
      "storage_key": "ab/abcdef0123456789abcdef0123456789.jpg"
    }
  ]
}
```

`StoredImageReference` and the composed request use `extra="forbid"`. The
endpoint uses the existing internal-auth, request-ID, safe-error, concurrency,
schema-validation, runner capability, output-validation, and telemetry
contracts. Telemetry identifies the new task kind as
`analyze_stored_images` and records the image count without logging paths,
prompts, payloads, or image bytes.

## Prompt ownership

No Fitsho production prompt is added to Agent Service. Runner transport framing
may identify explicitly allowed image paths and permit reading those listed
files, while prohibiting unrelated filesystem inspection or modification.

## Verification

Focused Backend and Agent Service tests cover source exclusivity, provider
routing, OpenRouter external Base64 behavior, body/food storage references,
stored-image endpoint security, original-path passthrough, workspace cleanup,
runner path containment, authentication, capability checks, telemetry, and
prompt ownership. Compose rendering must show exactly the two Agent Service
private-media mounts with `:ro`, while the final source audit confirms no
production Agent Service image-byte transfer or database migration.
