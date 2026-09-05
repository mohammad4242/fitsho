# Fitsho Agent Service — Architecture & Implementation Plan

> **For Sol (supervisor/orchestrator):** این سند باید task-by-task اجرا شود. Sol مالک معماری، قراردادها، امنیت، migrationها، تصمیم‌های بین‌ماژولی و بازبینی نهایی است. برای کارهای محدود و مستقل، Sol باید subagentهای Luna Low / Medium / High را اجرا کند، خروجی هر Luna را خودش review کند، تست‌های مرتبط را اجرا کند و اگر implementation با قرارداد این سند ناسازگار بود خودش اصلاح کند.
>
> **قانون اصلی اجرا:** هیچ Luna اجازه ندارد معماری، schema عمومی، migration strategy، قرارداد HTTP، security boundary یا semantics موجود Fitsho را خودسرانه تغییر دهد. Luna فقط در محدوده فایل‌ها و interfaceهایی که Sol برای همان task مشخص می‌کند کار می‌کند.

**Goal:** اضافه‌کردن یک مسیر اجرای دوم برای AIهای Fitsho به نام `agent_service` در کنار مسیر فعلی API/OpenRouter، به‌طوری‌که ادمین برای هر AI task بتواند انتخاب کند درخواست از API اجرا شود یا از Agent Service، و در Agent Service یکی از Antigravity، Codex یا Claude و مدل موردنظر را انتخاب کند.

**Architecture:** Backend فقط دو execution backend می‌شناسد: `api` و `agent_service`. در حالت API رفتار فعلی OpenRouter بدون تغییر باقی می‌ماند. در حالت Agent Service، Backend فقط با یک سرویس داخلی HTTP روی `agent-service:9001` حرف می‌زند؛ جزئیات `agy`, `codex`, `claude` کاملاً داخل Agent Service پنهان می‌ماند. Agent Service یک container دارد و هر سه CLI داخل همان image نصب می‌شوند، ولی هیچ‌کدام port جدا ندارند؛ فقط FastAPI Agent Service روی پورت 9001 گوش می‌دهد و runner مناسب را به صورت subprocess اجرا می‌کند.

**Tech Stack:** FastAPI, Pydantic, httpx, asyncio subprocess, Docker/Compose, PostgreSQL, SQLAlchemy/Alembic, React 19, TypeScript, Vitest, pytest.

**Scope for first production-capable iteration:**
- `BODY_PHOTO_ANALYSIS`
- `WORKOUT_PLAN_GENERATION`
- `FOOD_PHOTO_ESTIMATION`

**Explicitly out of scope for this iteration:**
- `PROGRESS_COMPARISON`: در کد فعلی deterministic است و pixel تصویر را نمی‌خواند.
- `FOOD_PRICE_SEARCH`: مسیر provider/scheduler جدا دارد و نباید بی‌دلیل وارد Agent Service شود.
- fallback بین چند Agent مختلف.
- ارسال مستقیم Agent Service به اینترنت برای کاربران.
- ذخیره OAuth/session credentialها در PostgreSQL.
- حذف OpenRouter یا تغییر رفتار پیش‌فرض فعلی.

---

# 1. Repo audit — وضعیت فعلی که این طرح بر اساس آن نوشته شده

Sol قبل از هر edit باید این فایل‌ها را دوباره روی branch/worktree فعلی بخواند تا مطمئن شود از زمان نوشته‌شدن این سند drift ایجاد نشده است:

### AI configuration / admin
- `backend/app/body_analysis/admin_config/enums.py`
  - `AITaskType` شامل workout, body photo, progress comparison, food photo, food price است.
  - `AIProviderName` فعلاً فقط `OPENROUTER` دارد.
- `backend/app/body_analysis/admin_config/models.py`
  - `AITaskConfig` per-task است.
  - `provider`, `primary_model_id`, `fallback_model_ids`, `temperature`, `timeout_seconds`, `max_cost_per_request`, routing restrictions و health metadata را نگه می‌دارد.
- `backend/app/body_analysis/admin_config/schemas.py`
  - request/response ادمین فعلاً API-centric و credential-centric است.
- `backend/app/body_analysis/admin_config/service.py`
  - credential requirement و OpenRouter construction hard-coded است.
- `backend/app/body_analysis/admin_config/router.py`
  - `/api/v1/admin/ai/*` فعلاً provider/model operations را فقط برای OpenRouter انجام می‌دهد.

### Stable AI provider boundary
- `backend/app/body_analysis/providers/protocol.py`
  - `AIProvider` قرارداد بسیار مناسب فعلی است و باید حفظ شود:
    - `test_connection`
    - `list_models`
    - `get_model_capabilities`
    - `generate_structured_text`
    - `analyze_images`
    - `normalize_error`
- `backend/app/body_analysis/providers/models.py`
  - `StructuredGenerationRequest`
  - `StructuredGenerationResponse`
  - `ImageInput`
  - `ModelCapabilities`
  - `AIProviderError`
  - `ProviderErrorCode`
  - این قراردادها باید تا حد ممکن reuse شوند؛ Agent Service نباید یک domain model موازی و ناسازگار بسازد.

### Body analysis
- `backend/app/body_analysis/runtime.py`
  - مستقیماً `openrouter_provider(...)` می‌سازد.
  - cost preflight بر اساس OpenRouter model catalogue انجام می‌شود.
- `backend/app/body_analysis/service.py`
  - تصاویر private storage را می‌خواند و به `ImageInput(base64_data=...)` تبدیل می‌کند.
  - دو AI call دارد: photo preflight و analysis.
  - model/request/token/cost provenance را ذخیره می‌کند.
- `backend/app/body_photos/storage.py`
  - private body photos خارج از public media نگه داشته می‌شوند.

### Workout
- `backend/app/workouts/dependencies.py`
  - در حالت AI مستقیماً OpenRouter را می‌سازد.
- `backend/app/workouts/ai_coach_provider.py`
  - کلاس اسمش `OpenRouterAiCoachProvider` است ولی dependency واقعی آن یک `StructuredTextProvider` generic است؛ بنابراین rename/generalize کردن آن کم‌ریسک است.

### Food photo
- `backend/app/nutrition/food_photo_service.py`
  - OpenRouter construction، provider name و logging در چند نقطه hard-coded است.
  - عکس را normalize می‌کند، private ذخیره می‌کند، سپس base64 برای provider می‌سازد.

### Existing CLI precedent inside Fitsho
- `backend/app/exercises/owner_video_analysis.py`
  - همین حالا `CodexCliExerciseAnalyzer` دارد.
  - با argument list (نه shell string) Codex را اجرا می‌کند.
  - `--sandbox read-only`, `--output-schema`, `--output-last-message`, `--image` و timeout را استفاده می‌کند.
  - این فایل precedent مهم برای CodexRunner است؛ runner جدید نباید یک implementation ضعیف‌تر یا ناامن‌تر از این pattern بسازد.

### App runtime / config / compose
- `backend/app/config.py`
  - OpenRouter/Zen settings و private storage paths موجودند.
- `backend/app/main.py`
  - `ai_http_client` و clientهای دیگر در lifespan ساخته می‌شوند.
- `compose.yaml`
  - فعلاً `db` و `backend` دارد؛ Agent Service وجود ندارد.
  - private body/food storage به شکل production-grade persistent volume صریح در compose فعلی mount نشده است.
- `.env.example`
  - precedent استفاده از local-login Codex برای owner video را دارد.

### Admin frontend
- `frontend/src/features/admin/AdminAiSettingsPage.tsx`
  - UI فعلاً `OpenRouter` را hard-code کرده.
- `frontend/src/features/admin/types.ts`
  - task config و catalog types فعلاً provider `"openrouter"` دارند.
- `frontend/src/features/admin/api.ts`
  - admin AI calls اینجا متمرکز هستند.
- `frontend/src/features/admin/AdminAiSettingsPage.test.tsx`
  - regression coverage موجود است و باید توسعه یابد.
- `frontend/src/i18n/fa.ts`
- `frontend/src/i18n/en.ts`
- `frontend/src/features/admin/admin.css`

### Existing relevant tests
- `backend/tests/admin/test_ai_task_settings_api.py`
- `backend/tests/body_analysis/test_providers.py`
- `backend/tests/body_analysis/test_execution_and_reviews.py`
- `backend/tests/body_analysis/test_analysis_api.py`
- `backend/tests/workouts/test_ai_coach_provider.py`
- `backend/tests/workouts/test_ai_coach_selector.py`
- `backend/tests/nutrition/test_food_photo_estimation.py`
- `backend/tests/exercises/test_owner_video_analysis.py`
- `backend/tests/test_config.py`
- `frontend/src/features/admin/AdminAiSettingsPage.test.tsx`

---

# 2. Final architecture

```text
                         ┌──────────────────────┐
                         │   OpenRouter API     │
                         └──────────▲───────────┘
                                    │
                      execution_backend = api
                                    │
┌───────────────────────────────────┴────────────────────────────────┐
│                         FITSHO BACKEND                             │
│                                                                   │
│  Task config → Provider Factory → AIProvider                      │
│                              │                                    │
│                              └─ AgentServiceProvider               │
└───────────────────────────────────┬────────────────────────────────┘
                                    │
                      execution_backend = agent_service
                                    │
                       HTTP + internal bearer token
                                    │
                                    ▼
                    ┌─────────────────────────────┐
                    │ agent-service:9001          │
                    │                             │
                    │ FastAPI + Router            │
                    │ Temp Workspace              │
                    │ Concurrency Controller      │
                    │                             │
                    │ ├─ AntigravityRunner → agy │
                    │ ├─ CodexRunner       → codex│
                    │ └─ ClaudeRunner      → claude
                    └─────────────────────────────┘
```

## Core design decisions

1. **یک Agent Service، یک port.**
   - `agy`, `codex`, `claude` CLI هستند؛ server جدا با port جدا نمی‌خواهیم.
   - فقط `agent-service` روی `9001` گوش می‌دهد.

2. **Backend هیچ command مربوط به CLIها را نمی‌شناسد.**
   - Backend فقط HTTP contract را می‌شناسد.
   - تمام `--model`, output parsing, CLI exit codes و auth behavior داخل runnerها می‌ماند.

3. **API و Agent fields همزمان در DB حفظ می‌شوند.**
   - سوییچ Agent → API نباید API key/model قبلی را پاک کند.
   - سوییچ API → Agent نباید agent/model قبلی را پاک کند.

4. **Agent Service credentialها در DB Fitsho ذخیره نمی‌شوند.**
   - یک persistent Docker volume برای HOME کانتینر.
   - Login هر CLI یک‌بار از داخل container.
   - container restart/rebuild نباید login را پاک کند.

5. **عکس‌های کاربر به کل Agent container mount نمی‌شوند.**
   - Backend عکس‌های همان request را از private storage می‌خواند.
   - `AgentServiceProvider` فقط همان تصاویر را با multipart به Agent Service می‌فرستد.
   - Agent Service در `TemporaryDirectory` می‌نویسد و بعد از request پاک می‌کند.
   - این boundary امن‌تر از read access به آرشیو کامل کاربران است.

6. **Existing API behavior default باقی می‌ماند.**
   - migration همه taskهای موجود را `execution_backend=api` می‌کند.
   - اگر Agent Service down باشد، API/OpenRouter همچنان کار می‌کند.

7. **Agent Service به اینترنت publish نمی‌شود.**
   - در Compose فقط `expose: 9001`.
   - Backend با DNS داخلی Docker از `http://agent-service:9001` استفاده می‌کند.

8. **Backend ↔ Agent Service authentication دارد.**
   - Bearer token داخلی.
   - token در env/secrets؛ نه frontend و نه DB.

9. **Agent mode ابتدا فقط سه task را پشتیبانی می‌کند.**
   - body photo
   - workout
   - food photo

10. **هیچ Agent Runner مجاز به دسترسی به repo، DB، Docker socket یا backend secrets نیست.**

---

# 3. Sol / Luna execution contract

## Sol مسئول مستقیم این موارد است
- بررسی drift ریپو قبل از شروع.
- تعریف و freeze کردن interfaces.
- migration و schema decisions.
- security model.
- Provider Factory design.
- HTTP contract بین Backend و Agent Service.
- انتخاب final naming.
- cross-module refactors.
- حل failureهای integration.
- final diff review.
- اجرای final regression suite.
- اصلاح هر خروجی Luna که contract را نقض کرده باشد.

## Luna Low
برای کارهای کاملاً مکانیکی و کم‌ریسک:
- i18n strings.
- type renames که interface از قبل توسط Sol مشخص شده.
- README/docs.
- test fixture updates ساده.
- CSS ساده.
- repetitive enum/UI wiring که logic جدید ندارد.

## Luna Medium
برای unitهای محدود با interface روشن:
- Pydantic schemas.
- isolated HTTP client methods.
- admin frontend conditional rendering.
- migration tests بعد از اینکه Sol schema را مشخص کرده.
- AGY adapter پس از اینکه command contract توسط Sol probe شده.
- focused unit tests.
- Docker helper/healthcheck بعد از freeze شدن architecture.

## Luna High
برای implementationهای پیچیده ولی **داخل boundary ثابت**:
- subprocess lifecycle helper.
- CodexRunner/ClaudeRunner.
- temp workspace + multipart processing.
- concurrency controller.
- AgentServiceProvider HTTP adapter.
- integration tests چندماژولی که architecture را تغییر نمی‌دهند.

## Review rule
بعد از هر task که Luna انجام می‌دهد، Sol باید:
1. `git diff -- <files>` را بخواند.
2. interfaceها را با همین سند مقایسه کند.
3. targeted tests را اجرا کند.
4. اگر Luna scope creep کرده revert/fix کند.
5. فقط بعد از PASS شدن task وارد task بعد شود.

## Parallelism rule
Lunaها فقط زمانی parallel اجرا شوند که **هیچ فایل مشترکی ندارند** و taskها dependency مستقیم ندارند. مثال خوب:
- Luna Low روی `fa.ts/en.ts`
- همزمان Luna Medium روی isolated agent-service unit tests

مثال بد:
- دو Luna همزمان روی `AdminAiSettingsPage.tsx`
- دو Luna همزمان روی `AITaskConfig`

---

# 4. Task 0 — Baseline, worktree, CLI contract probes

**Owner:** Sol  
**Delegation:** فقط probing مکانیکی CLI می‌تواند به Luna Medium داده شود، ولی نتیجه باید توسط Sol تأیید شود.

## Files
- Read: `AGENTS.md`
- Read all files listed in Repo Audit.
- No production code change yet.
- Later record verified CLI versions in `agent-service/README.md`.

## Actions
- [ ] وضعیت git را ثبت کن؛ unrelated dirty files را دست نزن.
- [ ] در worktree/branch جدا برای این feature کار کن.
- [ ] baseline tests مرتبط را قبل از تغییر اجرا کن.
- [ ] version واقعی local هر CLI را ثبت کن:
  - `agy --version`
  - `codex --version`
  - `claude --version`
- [ ] exact non-interactive commands را از `--help` همان نسخه ثبت کن.
- [ ] برای هر CLI این capabilities را جدا probe کن:
  - text headless
  - structured JSON
  - explicit model selection
  - image input
  - timeout/exit behavior
  - auth persistence after container restart
- [ ] اگر یک capability روی یک CLI واقعاً تست نشده، در implementation آن را `false` advertise کن؛ حدس ممنوع.

## Mandatory evidence
- AGY: test موجود این پروژه نشان داده headless + local image + persisted auth در Docker عملی است؛ Sol باید همان تست را در worktree environment بازتولید کند.
- Codex: از pattern موجود `backend/app/exercises/owner_video_analysis.py` استفاده شود و image/schema flags دوباره با pinned version تأیید شوند.
- Claude: هیچ capability بدون smoke test فعال نشود.

## Gate
هیچ Runner implementation قبل از freeze شدن exact command contract شروع نشود.

---

# 5. Task 1 — Extend per-task DB configuration

**Architecture owner:** Sol  
**Suggested implementation:** Luna Medium برای tests/migration boilerplate بعد از اینکه Sol fields را freeze کرد.

## Files
**Modify**
- `backend/app/body_analysis/admin_config/enums.py`
- `backend/app/body_analysis/admin_config/models.py`
- `backend/app/body_analysis/admin_config/schemas.py`
- `backend/app/body_analysis/admin_config/service.py`
- `backend/tests/admin/test_ai_task_settings_api.py`

**Create**
- `backend/alembic/versions/<revision>_add_agent_service_task_routing.py`

## Required types

```python
class AIExecutionBackend(StrEnum):
    API = "api"
    AGENT_SERVICE = "agent_service"


class AIAgentName(StrEnum):
    ANTIGRAVITY = "antigravity"
    CODEX = "codex"
    CLAUDE = "claude"
```

## Add to `AITaskConfig`
- `execution_backend: AIExecutionBackend`
  - non-null
  - default/server_default `"api"`
- `agent_name: AIAgentName | None`
- `agent_model_id: str | None`, max 300

Do **not** remove:
- `provider`
- `primary_model_id`
- `fallback_model_ids`
- API credential relation
- API routing restrictions
- API cost ceiling fields

## Migration behavior
Existing rows:
```text
execution_backend = api
agent_name = NULL
agent_model_id = NULL
```

No existing OpenRouter configuration may change.

## Service validation rules
When `enabled=False`:
- incomplete API or agent fields may be saved.

When `enabled=True` and `execution_backend=api`:
- existing credential requirement remains.
- `primary_model_id` required.
- existing model validation remains.
- `agent_name/agent_model_id` may remain stored but ignored.

When `enabled=True` and `execution_backend=agent_service`:
- do NOT require OpenRouter credential.
- require `agent_name`.
- require `agent_model_id`.
- only allow these task types initially:
  - `WORKOUT_PLAN_GENERATION`
  - `BODY_PHOTO_ANALYSIS`
  - `FOOD_PHOTO_ESTIMATION`
- API fields remain stored but ignored.

Switching backend must not erase inactive-side settings.

## Tests that must exist
- existing API config still defaults to `api`.
- enabling API without credential still fails.
- enabling Agent mode without OpenRouter key succeeds when agent fields exist.
- Agent mode without `agent_name` fails.
- Agent mode without `agent_model_id` fails.
- unsupported task + agent_service fails.
- switch API→Agent→API preserves both sides' configuration.

## Gate
Run:
```bash
cd backend
uv run pytest tests/admin/test_ai_task_settings_api.py -q
```

Then run migration-related/database tests used by the repo.

Sol reviews migration SQL/downgrade manually.

---

# 6. Task 2 — Create Agent Service skeleton and stable HTTP contract

**Architecture owner:** Sol  
**Implementation:** Luna Medium after interfaces below are frozen.

## Create
- `agent-service/pyproject.toml`
- `agent-service/app/__init__.py`
- `agent-service/app/main.py`
- `agent-service/app/config.py`
- `agent-service/app/schemas.py`
- `agent-service/app/security.py`
- `agent-service/app/errors.py`
- `agent-service/app/runners/__init__.py`
- `agent-service/app/runners/base.py`
- `agent-service/tests/conftest.py`
- `agent-service/tests/test_security.py`
- `agent-service/tests/test_health.py`

## Stable service API

### `GET /healthz`
- no model call.
- no quota consumption.
- returns process health only.
- may be used by Docker healthcheck.

### `GET /v1/capabilities`
- requires internal bearer token.
- must not send prompts to models.
- returns runner installation/configuration/capability metadata.

### `POST /v1/test`
- requires token.
- takes `agent`, `model_id`.
- performs an explicit tiny real request.
- used by admin Test button.
- may consume quota; UI must make this clear.

### `POST /v1/generate`
- JSON request.
- structured text task.

### `POST /v1/analyze-images`
- multipart.
- metadata in one JSON form field.
- image files as multipart files.
- never accepts arbitrary host paths from Backend.

## Shared request contract

```python
class AgentName(StrEnum):
    ANTIGRAVITY = "antigravity"
    CODEX = "codex"
    CLAUDE = "claude"


class AgentGenerationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    model_id: str
    system_prompt: str
    input_payload: dict[str, Any]
    response_schema: dict[str, Any]
    schema_name: str
    temperature: float
    max_output_tokens: int
    timeout_seconds: float
```

## Shared response

```python
class AgentGenerationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: dict[str, Any]
    agent: AgentName
    model_id: str
    request_id: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    duration_seconds: float
```

`cost` deliberately absent at Agent Service level in v1; Backend maps subscription-agent cost to `None`.

## Error envelope

```json
{
  "error": {
    "code": "timeout|unauthorized|rate_limited|invalid_request|invalid_output|model_not_found|provider_unavailable",
    "message": "safe message only",
    "request_id": "..."
  }
}
```

Never return:
- raw OAuth token
- full stderr
- full environment
- user image bytes
- full prompt in error
- filesystem paths outside temp workspace

## Internal authentication
Use:
```http
Authorization: Bearer <AGENT_SERVICE_TOKEN>
```

Comparison with `secrets.compare_digest`.

## Gate
```bash
cd agent-service
uv run pytest tests/test_security.py tests/test_health.py -q
```

---

# 7. Task 3 — Secure subprocess engine, temp workspace, concurrency

**Architecture owner:** Sol  
**Implementation:** Luna High  
**Final review:** Sol mandatory

## Create
- `agent-service/app/process.py`
- `agent-service/app/workspace.py`
- `agent-service/app/concurrency.py`
- `agent-service/tests/test_process.py`
- `agent-service/tests/test_workspace.py`
- `agent-service/tests/test_concurrency.py`

## Process rules
Use `asyncio.create_subprocess_exec`, never `create_subprocess_shell`.

Arguments must always be a list:
```python
proc = await asyncio.create_subprocess_exec(
    *command,
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd=workspace,
    start_new_session=True,
)
```

On timeout:
- terminate process group.
- escalate to kill if necessary.
- wait/reap process.
- return normalized timeout error.
- no zombie process.

## Workspace
Each request:
```text
/tmp/fitsho-agent/<request-id>/
```

Use secure temporary directory creation, not user-controlled directory names.

Image filenames generated by service:
```text
image-01.jpg
image-02.jpg
image-03.webp
```

Never use uploaded original filename directly.

On every path:
- success
- CLI failure
- parser failure
- cancellation
- timeout

the temp directory must be removed.

## Image validation
- max count configurable, default 3 for body flow but service may allow up to 5.
- MIME allowlist: JPEG / PNG / WebP.
- per-file max bytes.
- total request max bytes.
- reject zero-byte.
- no SVG.
- no arbitrary file path fields.

## Concurrency
Config examples:
```text
AGENT_GLOBAL_MAX_CONCURRENCY=4
AGENT_ANTIGRAVITY_MAX_CONCURRENCY=2
AGENT_CODEX_MAX_CONCURRENCY=2
AGENT_CLAUDE_MAX_CONCURRENCY=2
AGENT_QUEUE_WAIT_SECONDS=5
```

Use global semaphore + per-runner semaphore.

If capacity cannot be acquired in queue window:
- return `rate_limited` or explicit safe overload code mapped to backend `RATE_LIMITED`.

## Gate
Tests must prove:
- command injection through prompt cannot change executable args.
- timeout kills child.
- temp files deleted after success and failure.
- only configured concurrency runs simultaneously.
- queue overflow fails safely.

---

# 8. Task 4 — AntigravityRunner

**Contract owner:** Sol  
**Implementation:** Luna Medium/High  
**Final verification:** Sol with real CLI

## Create
- `agent-service/app/runners/antigravity.py`
- `agent-service/tests/runners/test_antigravity.py`

## Runner interface
Freeze in `base.py`:

```python
@dataclass(frozen=True)
class RunnerRequest:
    model_id: str
    system_prompt: str
    input_payload: dict[str, Any]
    response_schema: dict[str, Any]
    schema_name: str
    temperature: float
    max_output_tokens: int
    timeout_seconds: float
    image_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class RunnerResult:
    payload: dict[str, Any]
    model_id: str
    input_tokens: int | None
    output_tokens: int | None
    duration_seconds: float


class AgentRunner(Protocol):
    name: AgentName

    async def capabilities(self) -> RunnerCapabilities: ...
    async def run(self, request: RunnerRequest) -> RunnerResult: ...
```

## AGY behavior
- use exact flags confirmed in Task 0.
- explicit `--model`; no silent model fallback.
- headless mode only.
- JSON output.
- schema enforcement where verified by current AGY version.
- run `cwd` = request temp workspace so image files are workspace-local.
- permissions must be constrained for production.
- **Do not ship `--dangerously-skip-permissions` as normal production behavior.**

If AGY needs a permission allowlist file:
- create/configure it only for temp workspace read access.
- do not grant repo/home-wide file access beyond what auth requires.

## Output parsing
AGY outer envelope may contain inner JSON string.
Runner must:
1. parse outer CLI JSON.
2. verify status.
3. parse response/structured payload.
4. validate against requested JSON schema or local Pydantic/schema validator.
5. return only dict payload.

## Tests
Fake executable/runner fixtures must cover:
- successful text.
- successful image.
- malformed outer JSON.
- malformed inner JSON.
- exit != 0.
- 403/unauthorized mapping.
- model not found.
- timeout.
- token usage mapping.

## Real smoke gate
Inside built container:
- text `AUTH_OK`.
- restart container; text `PERSIST_OK`.
- image description.
- structured JSON from image.
All must pass before `supports_image=True`.

---

# 9. Task 5 — CodexRunner

**Contract owner:** Sol  
**Implementation:** Luna High  
**Important precedent:** reuse ideas from `backend/app/exercises/owner_video_analysis.py`.

## Create
- `agent-service/app/runners/codex.py`
- `agent-service/tests/runners/test_codex.py`

## Requirements
Do not re-invent unsafe CLI invocation. Preserve the good existing patterns:
- argument list.
- explicit cwd.
- timeout.
- read-only sandbox where supported.
- output schema file.
- output-last-message file.
- `--image` only if verified in pinned version.
- no shell.
- no repo mutation.

For generic Agent Service, use temp workspace only:
```text
-C <temp-workspace>
--skip-git-repo-check
--ephemeral
--sandbox read-only
```
only where verified by current version.

## Structured output
Write requested JSON schema atomically inside temp workspace:
```text
schema.json
output.json
```

Pass prompt through stdin where supported; do not put giant prompt into shell command line.

## Tests
Same normalized contract as AGY:
- text.
- image.
- schema.
- invalid output.
- auth failure.
- timeout.
- model selection.
- output token usage when available.

## Refactor warning
Do **not** modify `CodexCliExerciseAnalyzer` in the same task unless duplication becomes objectively harmful. First ship generic runner. Any later refactor of owner-video import must be a separate task with its existing tests.

---

# 10. Task 6 — ClaudeRunner

**Contract owner:** Sol  
**Implementation:** Luna High  
**Activation gate:** exact CLI behavior must be proved first.

## Create
- `agent-service/app/runners/claude.py`
- `agent-service/tests/runners/test_claude.py`

## Rules
- use non-interactive/print mode verified in Task 0.
- explicit model.
- prompt via stdin if supported.
- parse machine-readable output only.
- if Claude CLI has no hard JSON-schema enforcement:
  - prompt must request only JSON.
  - Agent Service must parse.
  - validate against requested schema.
  - invalid response → `invalid_output`.
- image capability remains `false` until a container smoke test proves the exact pinned CLI supports it in this mode.

Do not scrape interactive TUI output.

---

# 11. Task 7 — Agent Service routing, capabilities and HTTP endpoints

**Architecture owner:** Sol  
**Implementation:** Luna High

## Modify/Create
- `agent-service/app/main.py`
- `agent-service/app/service.py`
- `agent-service/app/schemas.py`
- `agent-service/app/runners/registry.py`
- `agent-service/tests/test_capabilities.py`
- `agent-service/tests/test_generate_api.py`
- `agent-service/tests/test_image_api.py`

## Registry
One registry:
```python
RUNNERS: dict[AgentName, AgentRunner]
```

No `if/elif` command construction spread through HTTP routes.

## Model listing
Each runner owns model discovery.

Rule:
- if CLI exposes reliable machine-readable list, use it.
- otherwise use an explicit configured allowlist.
- never parse unstable interactive UI text.

Capabilities per model must include at least:
```json
{
  "model_id": "...",
  "supports_text_input": true,
  "supports_image_input": true,
  "supports_structured_output": true
}
```

Runner-level:
```json
{
  "installed": true,
  "version": "...",
  "auth_state": "unknown|authenticated|unauthenticated",
  "models": []
}
```

`auth_state` must not be guessed by reading private credential contents.
A successful `/v1/test` may update in-memory last-known auth state.

## Request flow
```text
HTTP auth
→ validate request
→ pick runner
→ validate requested model/capability
→ acquire concurrency
→ temp workspace
→ save request images
→ runner.run()
→ validate normalized payload
→ cleanup
→ response
```

## Gate
All agent-service tests pass with fake CLIs before any backend integration.

---

# 12. Task 8 — Docker image for all three CLIs + persistent authentication

**Architecture owner:** Sol  
**Docker implementation:** Luna Medium  
**Real auth verification:** Sol

## Create
- `agent-service/Dockerfile`
- `agent-service/docker/entrypoint.sh`
- `agent-service/README.md`
- optional `agent-service/.dockerignore`

## Image requirements
Base should be stable and pinned, e.g. Ubuntu 24.04 or another justified base.

Install only requirements actually needed by pinned CLIs:
- Python runtime / uv
- curl
- ca-certificates
- D-Bus/keyring packages required by AGY
- Node/npm only if required by pinned Codex/Claude distribution
- the three pinned CLIs

Do not bake:
- Google auth
- ChatGPT auth
- Claude auth
- API keys
- proxy credentials

## Runtime user
Create non-root user, e.g. `agent`.

```text
HOME=/home/agent
```

Persistent named volume:
```text
fitsho_agent_home:/home/agent
```

This single HOME volume may contain each CLI's own auth/config directories.

## Keyring/D-Bus
Entrypoint must start the minimum user session services required by AGY headless credentials.
Do not run a full desktop environment.

## Login operations
README must document explicit manual commands, e.g. conceptually:
```bash
docker compose exec agent-service agy
docker compose exec agent-service codex login
docker compose exec agent-service claude
```

Use exact commands verified in Task 0.

## Persistence gate
For each CLI:
1. login.
2. run successful test.
3. `docker compose stop agent-service`.
4. start again.
5. run test without login.
6. must succeed.

No runner marked production-ready before this passes.

---

# 13. Task 9 — Backend AgentServiceProvider + central Provider Factory

**Architecture owner:** Sol  
**Implementation support:** Luna High for HTTP adapter tests.

## Create
- `backend/app/body_analysis/providers/agent_service.py`
- `backend/app/ai/task_provider.py`
- `backend/tests/ai/test_agent_service_provider.py`
- `backend/tests/ai/test_task_provider.py`

## Modify
- `backend/app/body_analysis/providers/__init__.py`
- `backend/app/config.py`
- `.env.example`
- `backend/app/main.py`
- `backend/tests/test_config.py`

## New backend settings

Conceptually:
```python
agent_service_base_url: str = "http://agent-service:9001"
agent_service_token: SecretStr | None
agent_service_connect_timeout_seconds: float = 5.0
agent_service_max_image_bytes: int = ...
```

Production must require a strong Agent Service token if Agent Service mode is used.

## App lifespan
Create a dedicated `httpx.AsyncClient`:
```text
app.state.agent_http_client
```

Do not reuse OpenRouter client because:
- different base URL.
- different authentication.
- different trust/proxy behavior.
- different timeout semantics.

## AgentServiceProvider
Must implement existing `AIProvider`.

Constructor concept:
```python
AgentServiceProvider(
    client,
    base_url,
    token,
    agent_name,
    timeout_seconds,
)
```

### `generate_structured_text`
Map existing `StructuredGenerationRequest` → `/v1/generate`.

### `analyze_images`
Existing `ImageInput` contains base64.
Provider:
1. decode base64 safely.
2. send multipart files.
3. do not write to backend temp disk unless unavoidable.
4. map service response → `StructuredGenerationResponse`.

Result:
```python
StructuredGenerationResponse(
    payload=...,
    model_id=...,
    attempted_models=(...,),
    provider_request_id=request_id,
    input_tokens=...,
    output_tokens=...,
    cost=None,
)
```

### Error mapping
Agent error code → existing `ProviderErrorCode`.

No raw Agent Service response may leak to user.

## Central factory
Create one place that decides:
```text
task.execution_backend == api
    → OpenRouterProvider

task.execution_backend == agent_service
    → AgentServiceProvider
```

The factory must produce enough metadata for downstream provenance:
- logical provider name.
- primary model.
- fallback models.
- provider object.
- whether cost preflight applies.

Suggested typed result:
```python
@dataclass(frozen=True)
class ConfiguredAIProvider:
    provider: AIProvider
    provider_name: str
    primary_model_id: str
    fallback_model_ids: tuple[str, ...]
    routing_preferences: ProviderRoutingPreferences
    supports_cost_accounting: bool
```

For Agent Service:
```text
provider_name = "agent_service:antigravity"
```
(or another Sol-approved stable format ≤ existing DB field lengths).

## Gate
Tests prove factory selects the right provider and existing API behavior is unchanged.

---

# 14. Task 10 — Body Analysis integration

**Architecture owner:** Sol  
**Implementation:** Luna Medium  
**Review:** Sol because this is privacy-sensitive.

## Modify
- `backend/app/body_analysis/runtime.py`
- potentially small provider-neutral error text in `backend/app/body_analysis/service.py`
- `backend/tests/body_analysis/test_execution_and_reviews.py`
- `backend/tests/body_analysis/test_analysis_api.py`
- `backend/tests/body_analysis/test_providers.py`

## Changes
Replace direct OpenRouter construction with central task-provider factory.

### Cost preflight
Current `_validate_budget_preflight` is OpenRouter/catalog specific.

Rule:
- API path: preserve current behavior exactly.
- Agent Service path: skip monetary cost preflight because `cost=None`.
- do not silently treat token count as dollar cost.

### Execution config
For API:
```text
provider_name=openrouter
model=primary OpenRouter model
```

For Agent:
```text
provider_name=agent_service:<agent>
model=agent_model_id
fallback_models=()
```

### Image privacy
`BodyAnalysisService` continues to create `ImageInput` exactly as today.
Only AgentServiceProvider changes transmission.

Do not give Agent Service direct access to body-photo storage in v1.

### Existing two-stage flow
Must remain:
1. photo preflight
2. analysis

Both calls route through the same selected provider/agent for a queued analysis revision.

### Safe messages
Remove OpenRouter-specific wording from generic errors where Agent mode can hit the same branch.

## Tests
- body analysis on API still calls API provider.
- agent selection calls AgentServiceProvider.
- preflight and analysis both use agent.
- low confidence behavior unchanged.
- output normalization unchanged.
- temp/transport failure maps to safe failed analysis.
- provenance stores agent/model.
- API cost ceiling behavior unchanged.
- Agent Service `cost=None` does not falsely fail cost ceiling.

---

# 15. Task 11 — Generalize Workout AI Coach

**Architecture owner:** Sol  
**Implementation:** Luna Medium/High

## Modify
- `backend/app/workouts/ai_coach_provider.py`
- `backend/app/workouts/dependencies.py`
- `backend/tests/workouts/test_ai_coach_provider.py`
- `backend/tests/workouts/test_ai_coach_selector.py`
- relevant workout service tests if dependency shape changes.

## Rename/generalize
`OpenRouterAiCoachProvider` should become provider-neutral, e.g.:
```python
AiCoachProvider
```

It already consumes a `StructuredTextProvider`; keep that abstraction.

Optional transitional alias may be kept briefly if it reduces unrelated churn, but final public naming should not lie about OpenRouter.

## Dependency
Use central factory for `WORKOUT_PLAN_GENERATION`.

API:
- existing model/fallback/preferences.

Agent:
- `AiCoachProvider(AgentServiceProvider(...))`
- `primary_model = agent_model_id`
- no API fallback list in v1.

## Safety
Preserve current critical behavior:
AI only selects among supplied candidate programs.
It must not mutate exercises/prescriptions/safety constraints.

Provider refactor must not move workout programming authority from deterministic engine to model.

## Tests
- API path unchanged.
- Agent path selects candidate and explanation.
- invalid candidate ID still rejected.
- Agent failure maps to existing workout provider errors.
- deterministic generation method never contacts Agent Service.

---

# 16. Task 12 — Food Photo integration

**Architecture owner:** Sol  
**Implementation:** Luna Medium

## Modify
- `backend/app/nutrition/food_photo_service.py`
- `backend/tests/nutrition/test_food_photo_estimation.py`

## Changes
Remove hard-coded:
- `AIProviderName.OPENROUTER` construction.
- `"openrouter"` provider logging/provenance where runtime provider should be used.

Use central task-provider factory for `FOOD_PHOTO_ESTIMATION`.

Keep existing:
- consent requirement.
- upload size validation.
- normalization.
- private storage.
- catalogue mapping.
- retention.
- idempotency.
- safe error behavior.

Provider metadata must record actual logical provider:
```text
openrouter
agent_service:antigravity
agent_service:codex
agent_service:claude
```

## Tests
- consent still required.
- API path regression.
- Agent path success.
- Agent invalid output.
- Agent unavailable cleanup deletes just-stored photo as existing provider failure path does.
- operational events record correct provider.

---

# 17. Task 13 — Admin backend endpoints for Agent Service

**Architecture owner:** Sol  
**Implementation:** Luna Medium

## Modify
- `backend/app/body_analysis/admin_config/schemas.py`
- `backend/app/body_analysis/admin_config/service.py`
- `backend/app/body_analysis/admin_config/router.py`
- `backend/tests/admin/test_ai_task_settings_api.py`

## Add schemas
Task config response/update must expose:
```text
execution_backend
agent_name
agent_model_id
```

Existing credential field remains.

## Add admin endpoints

### `GET /api/v1/admin/ai/agent-service/capabilities`
Backend proxies/normalizes Agent Service capabilities.
Requires admin auth.
No model call.

### `POST /api/v1/admin/ai/agent-service/test`
Body:
```json
{
  "agent": "antigravity",
  "model_id": "..."
}
```
Requires:
- admin
- trusted origin

It invokes Agent Service `/v1/test`.

Do not expose internal bearer token to frontend.

## Model selection validation
UI should only show compatible models, but backend remains authoritative:
- Body photo requires `supports_image_input`.
- Workout requires text + structured output.
- Food photo requires image + structured output.

Because Agent Service may be temporarily offline:
- saving a valid Agent config should not require a live test.
- runtime failure remains safe 503/provider unavailable.
- admin Test is the explicit live verification action.

## API model catalog
Existing OpenRouter `/models` + refresh behavior stays unchanged and is shown only in API mode.

---

# 18. Task 14 — Admin frontend: API vs Agent Service per task

**Architecture owner:** Sol for state shape  
**Implementation:** Luna Medium  
**i18n/CSS:** Luna Low can run separately after component behavior is frozen.

## Modify
- `frontend/src/features/admin/types.ts`
- `frontend/src/features/admin/api.ts`
- `frontend/src/features/admin/AdminAiSettingsPage.tsx`
- `frontend/src/features/admin/AdminAiSettingsPage.test.tsx`
- `frontend/src/features/admin/admin.css`
- `frontend/src/i18n/fa.ts`
- `frontend/src/i18n/en.ts`

## UI behavior

Each supported task:

```text
Execution backend
( ) API
( ) Agent Service
```

### If API
Show current controls:
- OpenRouter
- API key
- Test API
- Refresh models
- primary model
- fallback models
- cost ceiling
- routing restrictions
- capabilities/pricing

### If Agent Service
Hide API-key editing block from active view but do not delete stored key.

Show:
```text
Agent:
[ Antigravity | Codex | Claude ]

Model:
[ compatible models returned by capabilities ]

Agent Service status
Installed / unavailable
Last test result
[ Test Agent ]
```

Hide/disable API-only controls:
- API cost ceiling
- OpenRouter routing restrictions
- API model refresh

Generic controls such as timeout remain.

Temperature/max-output fields:
- only enabled if capability contract says runner supports them.
- otherwise show disabled + short explanation.
- do not pretend unsupported CLI parameters are applied.

## Unsupported tasks
For `PROGRESS_COMPARISON` and `FOOD_PRICE_SEARCH` in v1:
- Agent Service option disabled or absent.
- existing behavior remains clear.

## Tests
`AdminAiSettingsPage.test.tsx` must cover:
- default existing API view.
- switching UI to Agent Service.
- API key not sent/replaced when saving agent mode without replacement.
- agent and model included in save payload.
- task switch does not leak state from previous task.
- capabilities loaded for agent mode.
- incompatible image model not selectable for body/food photo.
- test button calls agent-test endpoint.
- switching back to API restores stored API controls.
- responsive layout remains contained.

Run:
```bash
cd frontend
npm test -- AdminAiSettingsPage.test.tsx
npm run lint
npm run build
```

---

# 19. Task 15 — Compose networking, persistent storage, secrets and proxy

**Architecture owner:** Sol  
**Implementation:** Luna Medium

## Modify
- `compose.yaml`
- `.env.example`
- `backend/app/config.py` if final env names differ
- `agent-service/README.md`

## Add service
Conceptual:

```yaml
agent-service:
  build:
    context: ./agent-service
  expose:
    - "9001"
  environment:
    AGENT_SERVICE_TOKEN: ${AGENT_SERVICE_TOKEN}
    HOME: /home/agent
  volumes:
    - fitsho_agent_home:/home/agent
  healthcheck:
    test: ["CMD", "curl", "-fsS", "http://localhost:9001/healthz"]
  restart: unless-stopped
```

Do **not** publish:
```yaml
ports:
  - "9001:9001"
```
in normal production compose.

Backend:
```text
AGENT_SERVICE_BASE_URL=http://agent-service:9001
AGENT_SERVICE_TOKEN=...
```

## Security hardening
Where compatible with CLI auth:
- non-root user.
- `cap_drop: [ALL]`
- `security_opt: ["no-new-privileges:true"]`
- `pids_limit`.
- memory limit appropriate to server.
- writable persistent HOME only where necessary.
- temp filesystem for `/tmp`.
- no Docker socket.
- no backend source mount.
- no DB socket/credential mount.
- no body-photo archive mount.

## Private Fitsho storage
Sol must audit current deployment semantics before changing paths.

Goal:
Body/food/nutrition private data must survive backend container rebuild.

Use explicit persistent volumes/binds and explicit absolute paths, for example:
```text
/var/lib/fitsho/private/body-photos
/var/lib/fitsho/private/food-photos
/var/lib/fitsho/private/nutrition-labs
```

Do migration/copy carefully; do not orphan existing local data.

This storage persistence change may be a separate commit from Agent Service compose wiring.

## Proxy
Proxy is deployment configuration, never committed as hard-coded Iranian/local address.

Agent container may accept:
```text
HTTP_PROXY
HTTPS_PROXY
NO_PROXY
```

Local Iran deployment can inject the existing host proxy address.
Foreign server can leave proxy unset.

`NO_PROXY` must include Docker-internal services so Backend↔Agent traffic is not sent through VPN.

Do not make `network_mode: host` a production requirement.

---

# 20. Task 16 — End-to-end behavior and failure-mode tests

**Owner:** Sol  
**Delegation:** individual failure tests to Luna Medium/High; final run by Sol.

## Automated E2E cases

### Existing API regression
- API mode body analysis works.
- API workout works.
- API food photo works.
- OpenRouter admin catalog/credential workflow works.

### Agent Service
- task config selects Agent Service.
- Backend calls only Agent Service, not OpenRouter.
- Agent Service selects requested runner.
- requested model is explicit.
- structured output returns to existing business service.

### Image
- Backend sends only current request images.
- Agent temp workspace gets only those images.
- temp images removed after response.
- malformed image rejected before runner.
- Agent container has no archive mount.

### Availability
- Agent Service down:
  - Backend itself starts normally.
  - API tasks continue working.
  - Agent-selected task fails with safe service unavailable error.

### Authentication
- bad internal token → 401.
- frontend never receives internal token.
- missing CLI auth → normalized unauthorized.
- no OAuth/refresh tokens in logs.

### Timeouts
- hanging runner terminated.
- backend receives normalized timeout.
- retry semantics of existing body analysis remain intact.

### Invalid model/output
- unknown agent.
- unknown model.
- model lacks image capability.
- malformed JSON.
- schema-invalid JSON.
All map to safe existing provider errors.

### Concurrency
- burst beyond configured runner capacity.
- bounded number of subprocesses.
- overload returns safe rate-limited/unavailable error.
- server RAM/process count does not grow without bound.

---

# 21. Task 17 — Real Docker smoke matrix

**Owner:** Sol only for final acceptance**

Run against the actual built Agent Service image, not host-installed CLIs.

Record:
- CLI version.
- agent name.
- model.
- auth persistence.
- text.
- structured JSON.
- image.
- average latency.
- token usage if reported.

Matrix:

| Agent | Text | Structured JSON | Image | Auth survives restart | Explicit model |
|---|---|---|---|---|---|
| Antigravity | required | required | required for image tasks | required | required |
| Codex | required | required | required before enabling image tasks | required | required |
| Claude | required | required | required before enabling image tasks | required | required |

If a runner fails image:
- keep runner enabled only for text tasks.
- Admin UI filters it out of body/food photo.
- do not block the whole feature.

---

# 22. Task 18 — Observability and provenance

**Architecture owner:** Sol  
**Implementation:** Luna Medium

## Backend
Preserve/store:
- execution backend.
- logical provider.
- agent.
- model.
- provider request ID.
- input/output tokens.
- duration if there is an existing suitable operational-event field.
- `cost=None` for subscription agent if no trustworthy monetary accounting exists.

## Agent Service logs
Allowed:
```text
request_id
agent
model
endpoint/task kind
duration
status/error_code
input byte counts
image count
token counts if available
```

Forbidden:
```text
full prompt
full input_payload if personal
image bytes
OAuth/auth tokens
Authorization header
raw credential files
unredacted stderr
```

Use structured logging.

---

# 23. Task 19 — Documentation and operational runbook

**Implementation:** Luna Low/Medium  
**Review:** Sol

## Create/update
- `agent-service/README.md`
- optionally `docs/agent-service-operations.md`
- root `README.md` only if project run instructions need it.
- `.env.example`

Runbook must include:
- build service.
- start service.
- initial AGY login.
- initial Codex login.
- initial Claude login.
- verify auth.
- restart persistence check.
- list capabilities.
- admin Test operation.
- local proxy configuration.
- credential volume backup warning.
- how to disable Agent Service quickly.
- how to revert a task to API from admin.

Never document or commit actual tokens.

---

# 24. Final Sol verification checklist

Sol must not claim completion until all applicable checks pass.

## Code review
- [ ] No direct CLI invocation added to Backend.
- [ ] No direct OpenRouter hard-code remains in the three migrated runtime paths where factory should be used.
- [ ] Existing OpenRouter provider itself remains intact.
- [ ] No subscription auth stored in PostgreSQL.
- [ ] No user image archive mount in Agent Service.
- [ ] No `--dangerously-skip-permissions` in production AGY command.
- [ ] No `shell=True`.
- [ ] No Docker socket.
- [ ] Agent Service port not public.
- [ ] internal token redacted.
- [ ] agent mode only enabled for supported tasks.

## Backend tests
At minimum targeted:
```bash
cd backend
uv run pytest \
  tests/admin/test_ai_task_settings_api.py \
  tests/body_analysis/test_providers.py \
  tests/body_analysis/test_execution_and_reviews.py \
  tests/body_analysis/test_analysis_api.py \
  tests/workouts/test_ai_coach_provider.py \
  tests/workouts/test_ai_coach_selector.py \
  tests/nutrition/test_food_photo_estimation.py \
  tests/exercises/test_owner_video_analysis.py \
  tests/test_config.py -q
```

Then full backend suite using the repo's normal test database setup.

## Agent Service
```bash
cd agent-service
uv run pytest -q
```

## Frontend
```bash
cd frontend
npm run lint
npm test
npm run build
```

## Docker
```bash
docker compose config
docker compose build agent-service backend
docker compose up -d
docker compose ps
```

Verify:
- db healthy
- backend healthy/reachable
- agent-service healthy
- agent-service port not exposed publicly
- Backend resolves `agent-service:9001`

## Real acceptance
For each enabled runner:
- actual login.
- actual test.
- restart.
- persisted login.
- actual model selection.
- actual structured result.
- image result where capability is advertised.

---

# 25. Recommended implementation order / checkpoints

Do **not** implement everything in one giant pass.

### Checkpoint A — Data + service contract
Tasks 0–3.
Result:
- DB understands API vs Agent.
- Agent Service skeleton exists.
- security/process/workspace primitives tested.
- no real model integration required yet.

### Checkpoint B — First vertical slice: Antigravity + Body Analysis
Tasks 4, 7, 8, 9, 10.
Result:
```text
Admin DB config
→ Backend AgentServiceProvider
→ agent-service
→ AGY
→ image JSON
→ existing BodyAnalysis normalization
```
This is the most important end-to-end proof.

Sol should stop here and run full targeted regressions before adding more runners.

### Checkpoint C — Codex + Claude
Tasks 5–6 + capability wiring.
Only enable capabilities that real Docker smoke tests pass.

### Checkpoint D — Workout + Food
Tasks 11–12.
Reuse already-proven Provider Factory; do not create new direct integrations.

### Checkpoint E — Admin UI
Tasks 13–14.
At this point backend contract is stable, so frontend work is straightforward and good for Luna.

### Checkpoint F — Deployment/security/final
Tasks 15–19 + full verification.

---

# 26. Suggested Sol orchestration pattern

For every task:

```text
Sol
│
├─ 1. Read task + relevant repo files
├─ 2. Freeze exact interface
├─ 3. Write/approve failing tests or acceptance checks
├─ 4. Dispatch one bounded Luna task
│      ├─ Low    → mechanical
│      ├─ Medium → normal isolated implementation
│      └─ High   → complex isolated implementation
├─ 5. Read Luna diff
├─ 6. Run targeted tests
├─ 7. Fix implementation personally if contract/security is wrong
├─ 8. Commit coherent task
└─ 9. Move to next task
```

### Example delegation — good
```text
Luna Medium:
Implement `agent-service/app/runners/antigravity.py` only.
The runner interface in `base.py` is immutable.
Do not change HTTP routes, Docker, schemas, or Backend.
Add/modify only:
- agent-service/app/runners/antigravity.py
- agent-service/tests/runners/test_antigravity.py
Run the targeted test and report the exact output.
```

### Example delegation — bad
```text
"Build the Agent Service and integrate it into Fitsho."
```

That scope is too large for Luna and makes architectural drift likely.

---

# 27. Non-negotiable invariants

1. **Fitsho Backend must not know CLI syntax.**
2. **Agent Service must not know workout/nutrition business rules.**
3. **AIProvider stays the Backend boundary.**
4. **Existing API path stays default and backwards-compatible.**
5. **Agent auth never enters Fitsho DB.**
6. **User image archive is not broadly mounted to Agent Service.**
7. **Each runner gets only request-scoped temp files.**
8. **Structured outputs are validated before business code receives them.**
9. **No raw model/CLI error leaks to user.**
10. **No unlimited subprocess spawning.**
11. **Unsupported capability is disabled, never guessed.**
12. **Sol is final reviewer and is responsible for correcting Luna output.**

---

# 28. Definition of Done

این feature تمام‌شده محسوب می‌شود وقتی:

- Admin برای `BODY_PHOTO_ANALYSIS`, `WORKOUT_PLAN_GENERATION`, `FOOD_PHOTO_ESTIMATION` بتواند per-task بین `API` و `Agent Service` انتخاب کند.
- در Agent mode بتواند `Antigravity / Codex / Claude` و یک مدل compatible را انتخاب کند.
- Backend فقط `AgentServiceProvider` را بشناسد و هیچ CLI syntax نداشته باشد.
- Agent Service یک container و یک port داخلی داشته باشد.
- هر سه CLI در image نصب باشند.
- credential هر CLI در persistent HOME volume باقی بماند.
- capability هر runner بر اساس تست واقعی advertise شود.
- AGY image flow از container به‌صورت end-to-end پاس شود.
- Codex/Claude فقط capabilityهایی را نشان دهند که smoke test واقعی پاس کرده‌اند.
- OpenRouter API path و تست‌های قبلی بدون regression پاس شوند.
- Agent Service down بودن باعث down شدن Backend نشود.
- image files request-scoped و temporary باشند و cleanup شوند.
- concurrency bounded باشد.
- internal token فعال باشد.
- production compose Agent Service را به اینترنت expose نکند.
- targeted + full backend tests پاس شوند.
- Agent Service tests پاس شوند.
- frontend lint/test/build پاس شوند.
- Sol final diff را review کرده و هر خطای Luna را اصلاح کرده باشد.
