# Luna Max Prompt — Fitsho Admin-Driven Agent Authentication + Agent Service UI Cleanup

از ریشه پروژه Fitsho و روی feature/worktree فعلی Agent Service کار کن.

## نقش و هدف

تو **Luna Max** هستی و مسئول اجرای کامل این فاز هستی.

هدف این فاز:

1. ادمین بتواند از داخل **Admin → AI Settings → Agent Service** برای هرکدام از Antigravity، Codex و Claude فرآیند Authentication را شروع کند.
2. Agent Service باید CLI واقعی همان Agent را اجرا کند، URL / user code موردنیاز برای login را از خروجی واقعی CLI استخراج کند و فقط اطلاعات امن و لازم را از طریق Backend به Admin UI برگرداند.
3. اگر CLI برای ادامه login نیاز به authorization code / device code / input دیگری داشت، Admin UI بتواند آن input را به Backend و سپس Agent Service برگرداند تا به همان process فعال داده شود.
4. credential نهایی هرگز به Backend، Frontend یا PostgreSQL منتقل نشود و فقط داخل persistent HOME volume فعلی Agent Service باقی بماند.
5. قسمت Agent Service در پنل ادمین مرتب، واضح و production-grade شود.

## قواعد غیرقابل مذاکره

قبل از هر تغییر:
- `AGENTS.md` را بخوان.
- وضعیت git را بررسی کن و به unrelated changes دست نزن.
- architecture فعلی Agent Service را حفظ کن؛ آن را از نو بازطراحی نکن.
- هیچ credential واقعی را commit نکن.
- هیچ raw stdout/stderr حساس را به Backend یا Frontend نده.
- هیچ auth URL، user code، authorization code یا token را در log ذخیره نکن.
- Agent Service internal-only بماند و port 9001 public نشود.
- Browser ادمین مستقیم با Agent Service حرف نزند: Browser → Backend → Agent Service.
- `AGENT_SERVICE_TOKEN` هرگز به frontend نرود.
- از `shell=True`, `create_subprocess_shell`, command string یا eval استفاده نکن.
- هیچ arbitrary executable / command / URL از Backend قبول نکن.
- فقط agent enumهای شناخته‌شده `antigravity`, `codex`, `claude`.
- auth sessionها و subscription credentials در PostgreSQL ذخیره نشوند.
- credentialها در persistent HOME volume فعلی `/home/agent` بمانند.
- image/model capability بدون smoke test واقعی فعال نشود.
- تست قدیمی را برای سبزشدن حذف یا ضعیف نکن.
- TDD: failing test → implementation → passing test.
- بعد از هر Task diff را review و targeted tests را اجرا کن.
- اگر plan با branch واقعی drift دارد، repo واقعی منبع حقیقت است ولی security/architecture contract را نشکن.

## فایل‌های فعلی که قبل از edit باید خوانده شوند

### Agent Service
- `agent-service/app/main.py`
- `agent-service/app/service.py`
- `agent-service/app/config.py`
- `agent-service/app/security.py`
- `agent-service/app/process.py`
- `agent-service/app/workspace.py`
- `agent-service/app/concurrency.py`
- `agent-service/app/observability.py`
- `agent-service/app/schemas.py`
- `agent-service/app/runners/base.py`
- `agent-service/app/runners/registry.py`
- `agent-service/app/runners/antigravity.py`
- `agent-service/app/runners/codex.py`
- `agent-service/app/runners/claude.py`
- `agent-service/Dockerfile`
- `agent-service/docker/entrypoint.sh`
- `agent-service/README.md`
- `agent-service/pyproject.toml`

### Backend
- `backend/app/body_analysis/admin_config/schemas.py`
- `backend/app/body_analysis/admin_config/service.py`
- `backend/app/body_analysis/admin_config/router.py`
- `backend/app/body_analysis/admin_config/enums.py`
- `backend/app/body_analysis/admin_config/models.py`
- `backend/app/body_analysis/providers/agent_service.py`
- `backend/app/ai/task_provider.py`
- `backend/app/config.py`
- `backend/app/main.py`

### Frontend
- `frontend/src/features/admin/AdminAiSettingsPage.tsx`
- `frontend/src/features/admin/AdminAiSettingsPage.test.tsx`
- `frontend/src/features/admin/types.ts`
- `frontend/src/features/admin/api.ts`
- `frontend/src/features/admin/admin.css`
- `frontend/src/i18n/fa.ts`
- `frontend/src/i18n/en.ts`

### Deployment/tests
- `compose.yaml`
- `.env.example`
- `agent-service/tests/*`
- `agent-service/tests/runners/*`
- `backend/tests/admin/test_ai_task_settings_api.py`
- `backend/tests/ai/test_agent_service_provider.py`
- `backend/tests/ai/test_agent_service_admin_contract.py`

---

# PHASE 0 — Mandatory real CLI authentication probe

هیچ auth implementation را قبل از این probe شروع نکن.

1. `docker compose build agent-service`
2. داخل image/container واقعی:
   - `agy --version`
   - `agy --help`
   - `codex --version`
   - `codex --help`
   - `codex login --help`
   - `claude --version`
   - `claude --help`
   - `claude auth --help`
3. اگر subcommandی وجود نداشت، alternative واقعی را از help پیدا کن.
4. برای هر CLI مشخص کن:
   - command واقعی شروع login
   - TTY لازم یا نه
   - URL در stdout یا stderr
   - ANSI/TUI output
   - auth URL hostnameها
   - user/device code دارد یا نه
   - بعد از browser login خودکار کامل می‌شود یا input می‌خواهد
   - success exit code
   - cancel/failure behavior
   - auth status command بدون quota وجود دارد یا نه
5. Antigravity: remote/manual URL flow را با binary واقعی verify کن؛ ممکن است URL + browser code + input به CLI باشد.
6. Codex: فقط `codex login --help` نسخه pin‌شده را مبنا قرار بده؛ هیچ flag را حدس نزن.
7. Claude: exact pinned CLI behavior را مبنا قرار بده؛ هیچ login command را حدس نزن.
8. نتیجه safe را در `agent-service/docs/auth-flow-probe.md` ثبت کن:
   - version
   - exact auth command
   - PTY required
   - safe states
   - allowed verification hostnames
   - user input required
   - completion/failure behavior
   - هیچ session URL/code/email/token واقعی ثبت نشود.

Gate: تا پایان Phase 0 production auth code ننویس. اگر یک CLI flow امن قابل هدایت ندارد، همان Agent را `manual_auth_only` کن و workaround ناامن نساز.

---

# PHASE 1 — Generic auth contract

Create:
- `agent-service/app/auth/__init__.py`
- `agent-service/app/auth/schemas.py`

Status enum:
```python
class AuthSessionStatus(StrEnum):
    STARTING = "starting"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_INPUT = "waiting_for_input"
    VERIFYING = "verifying"
    AUTHENTICATED = "authenticated"
    FAILED = "failed"
    CANCELED = "canceled"
    EXPIRED = "expired"
```

Schemas:
```python
class AuthStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent: AgentName

class AuthInputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1, max_length=4096)

class AuthSessionView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    agent: AgentName
    status: AuthSessionStatus
    verification_url: str | None = None
    user_code: str | None = None
    input_label: str | None = None
    expires_at: datetime
    safe_error_message: str | None = None
```

Rules:
- verification URL فقط HTTPS و فقط hostnameهای allowlist همان adapter.
- user code محدود/printable و بدون control char.
- input_label متن ثابت server-side، نه raw CLI prompt.
- safe_error_message فقط safe ثابت.
- raw stdout/stderr و credential/token در response ممنوع.

Agent Service endpoints:
- `POST /v1/auth/start`
- `GET /v1/auth/{session_id}`
- `POST /v1/auth/{session_id}/input`
- `DELETE /v1/auth/{session_id}`

همه با `require_internal_auth`.

---

# PHASE 2 — Interactive auth process infrastructure

Create:
- `agent-service/app/auth/base.py`
- `agent-service/app/auth/manager.py`
- `agent-service/app/auth/session.py`
- `agent-service/app/auth/process.py`

اگر probe نشان داد TTY لازم است، `pexpect` preferred است:
- dependency در `agent-service/pyproject.toml`
- `pexpect.spawn(executable, args=[...])`
- shell ممنوع.
اگر pipes واقعاً کافی‌اند، stdlib subprocess acceptable است؛ فقط با evidence Phase 0.

Manager:
- session ID = uuid4
- sessions فقط memory
- TTL default 600 sec
- config:
  - `AGENT_AUTH_SESSION_TTL_SECONDS=600`
  - `AGENT_AUTH_MAX_OUTPUT_BYTES=65536`
- فقط یک active auth session per agent
- start دوم همان agent → 409 `auth_in_progress`
- success/failure/cancel/timeout/shutdown → process terminate/reap
- bounded output buffer
- user auth input log نشود و بعد از submit در UI/manager نگه‌داری نشود
- input هرگز command arg نباشد؛ فقط stdin/PTY همان process
- newline/control-char injection reject
- auth subprocess safe-env فقط: PATH, HOME, USER, LANG/LC_ALL, XDG_*, DBUS_SESSION_BUS_ADDRESS, proxy vars, SSL vars, provider-specific safe flags
- backend/DB secrets به auth CLI env نروند
- HOME/DBUS/keyring فعلی container حفظ شود.

---

# PHASE 3 — Per-agent AuthAdapter

Create:
- `agent-service/app/auth/adapters/__init__.py`
- `agent-service/app/auth/adapters/antigravity.py`
- `agent-service/app/auth/adapters/codex.py`
- `agent-service/app/auth/adapters/claude.py`

Contract equivalent:
```python
@dataclass(frozen=True)
class AuthCommand:
    executable: str
    args: tuple[str, ...]
    use_pty: bool

@dataclass(frozen=True)
class ParsedAuthUpdate:
    verification_url: str | None = None
    user_code: str | None = None
    needs_input: bool = False
    input_label: str | None = None
    authenticated: bool = False
    failed: bool = False
    safe_error_message: str | None = None

class AgentAuthAdapter(Protocol):
    agent: AgentName
    def command(self) -> AuthCommand: ...
    def allowed_auth_hosts(self) -> frozenset[str]: ...
    def parse_output(self, text: str) -> ParsedAuthUpdate: ...
    def classify_exit(self, returncode: int, final_text: str) -> AuthSessionStatus: ...
```

Parsing:
- ANSI strip
- URL extraction + `urlsplit` validation
- scheme=https
- hostname must be exact adapter allowlist from Phase 0
- credentials-in-authority reject
- URL query/state/code_challenge never log
- invalid URL never reaches frontend
- codes sanitized/limited

Antigravity/Codex/Claude exact command and regex باید از Phase 0 بیاید.

---

# PHASE 4 — Auth state + version in capabilities

Current capabilities را production-meaningful کن:
- version از `--version` بدون quota و با short timeout
- cache in memory
- successful auth session → authenticated
- known auth failure → unauthenticated
- `/v1/test` success → authenticated
- runner unauthorized → unauthenticated
- after restart:
  - اگر reliable non-quota status command وجود دارد استفاده کن
  - اگر ندارد → unknown
  - credential file existence هرگز authenticated محسوب نشود
- `/v1/capabilities` نباید model quota مصرف کند.

Modify as needed:
- `agent-service/app/runners/registry.py`
- runner files
- `agent-service/app/service.py`

---

# PHASE 5 — Auth routes/lifecycle

Modify:
- `agent-service/app/main.py`
- `agent-service/app/config.py`
- `agent-service/app/service.py` only where needed
- `agent-service/app/runners/registry.py`

App shutdown باید pending auth processes را kill/reap کند.

Reuse existing error envelope. Add safe codes if required:
- `auth_in_progress`
- `auth_session_not_found`
- `auth_session_expired`
- `auth_input_not_expected`

همزمان schema/backend mappings/tests را update کن.

---

# PHASE 6 — Agent Service auth tests

Create:
- `agent-service/tests/auth/test_manager.py`
- `agent-service/tests/auth/test_session.py`
- `agent-service/tests/auth/test_antigravity_auth.py`
- `agent-service/tests/auth/test_codex_auth.py`
- `agent-service/tests/auth/test_claude_auth.py`
- `agent-service/tests/test_auth_api.py`

با fake CLI scripts تست کن:
1. bearer required
2. sanitized start response
3. unknown agent rejected
4. one active session per agent
5. https URL only
6. unapproved host blocked
7. ANSI parse
8. raw prompt/stderr not exposed
9. code sanitized
10. input only when expected
11. long input rejected
12. newline/control injection rejected
13. input only to existing process
14. cancel kills
15. TTL kills/expires
16. safe failure
17. success authenticated
18. shutdown cleanup
19. no shell
20. env has no unrelated secrets
21. bounded output
22. Test success updates auth state
23. unauthorized runner updates auth state
24. capabilities consume no model request

---

# PHASE 7 — Backend admin proxy

Modify:
- `backend/app/body_analysis/admin_config/schemas.py`
- `backend/app/body_analysis/admin_config/service.py`
- `backend/app/body_analysis/admin_config/router.py`

No DB migration برای credential/session.

Backend safe schemas mirror:
- agent
- session_id
- status
- verification_url
- user_code
- input_label
- expires_at
- safe_error_message

Add routes:
- `POST /api/v1/admin/ai/agent-service/auth/start`
- `GET /api/v1/admin/ai/agent-service/auth/{session_id}`
- `POST /api/v1/admin/ai/agent-service/auth/{session_id}/input`
- `DELETE /api/v1/admin/ai/agent-service/auth/{session_id}`

Rules:
- all admin-only
- POST/DELETE trusted origin
- existing `agent_http_client`
- internal bearer injected by Backend
- internal token never returned
- malformed/downstream errors safe
- no frontend-supplied URL forwarded
- agent enum only

Tests:
Create `backend/tests/ai/test_agent_service_auth_admin.py` or focused equivalent.
Cover admin/member/origin/start/poll/input/cancel/token redaction/malformed response/unavailable/expired/not-found.

---

# PHASE 8 — Clean Admin Agent Service UI

Current `AdminAiSettingsPage.tsx` is already large. Auth flow را داخل آن dump نکن.

Create:
- `frontend/src/features/admin/AgentServicePanel.tsx`
- `frontend/src/features/admin/AgentAuthDialog.tsx`

Optional only if useful:
- `frontend/src/features/admin/useAgentAuthSession.ts`

Modify:
- `frontend/src/features/admin/AdminAiSettingsPage.tsx`
- `frontend/src/features/admin/types.ts`
- `frontend/src/features/admin/api.ts`
- `frontend/src/features/admin/admin.css`
- `frontend/src/i18n/fa.ts`
- `frontend/src/i18n/en.ts`

Agent mode UI:
```text
Agent Service                                   Online
Manage subscription agents and authentication

[ Antigravity card ]
Installed ✓   v...
Authentication: Connected / Not connected / Unknown
[Authenticate / Re-authenticate]

[ Codex card ]
...

[ Claude card ]
...

Selected agent: ...
Model: [...]
[Test selected agent/model]
```

Each card:
- selectable
- selected state
- name
- installed badge
- version
- auth status badge
- Authenticate/Re-authenticate
- auth action disabled if binary not installed
- model selection not required to authenticate

Service status:
- capabilities success = Online
- capabilities failure = unavailable
- do not infer from runner auth.

API mode current behavior unchanged.
Unsupported tasks (`progress_comparison`, `food_price_search`) remain Agent-disabled.

---

# PHASE 9 — Auth dialog UX

Authenticate click:
1. POST start
2. dialog loading
3. render session status

WAITING_FOR_USER:
- Persian/English instructions
- `[Open authentication page]`
- `[Copy link]`
- open only on explicit click via `window.open(url, "_blank", "noopener,noreferrer")`

If user_code:
- display readonly
- Copy code

WAITING_FOR_INPUT:
- auth code input
- Continue
- autocomplete off
- no local/session storage
- clear immediately after submit

Polling:
- every ~2 sec while starting/waiting/verifying
- stop on authenticated/failed/canceled/expired
- stop on unmount/task change/dialog close
- prevent stale response race using existing epoch/version pattern

Success:
- show success
- refresh capabilities
- no auto-enable task
- no auto-change model

Failure:
- safe backend message only

Cancel:
- DELETE session then close

---

# PHASE 10 — Frontend types/API

`types.ts` add:
```ts
export type AdminAiAgentAuthStatus =
  | "starting"
  | "waiting_for_user"
  | "waiting_for_input"
  | "verifying"
  | "authenticated"
  | "failed"
  | "canceled"
  | "expired";

export type AdminAiAgentAuthSession = {
  session_id: string;
  agent: AdminAiAgentName;
  status: AdminAiAgentAuthStatus;
  verification_url: string | null;
  user_code: string | null;
  input_label: string | null;
  expires_at: string;
  safe_error_message: string | null;
};
```

`api.ts`:
- `startAdminAiAgentAuth(agent)`
- `getAdminAiAgentAuthSession(sessionId)`
- `submitAdminAiAgentAuthInput(sessionId, value)`
- `cancelAdminAiAgentAuthSession(sessionId)`

Never direct fetch to port 9001.

---

# PHASE 11 — Frontend tests

Create/extend:
- `AdminAiSettingsPage.test.tsx`
- `AgentServicePanel.test.tsx`
- `AgentAuthDialog.test.tsx`

Cover:
1. API mode unchanged
2. Agent panel clean render
3. all 3 cards
4. status/version
5. unavailable binary disables auth
6. auth can start without model
7. start sends only agent
8. dialog URL
9. open link new tab secure
10. copy link
11. user code
12. waiting input
13. clear submitted code
14. polling update
15. polling stops terminal
16. unmount/task switch stops polling
17. stale response blocked
18. success refreshes capabilities
19. no auto-enable
20. safe failure
21. cancel
22. API key hidden in Agent mode
23. switching back API preserves config
24. unsupported tasks blocked

---

# PHASE 12 — i18n/UI copy

Persian + English.

Persian examples:
- سرویس عامل‌های هوش مصنوعی
- احراز هویت
- اتصال حساب
- اتصال مجدد
- متصل
- متصل نیست
- وضعیت نامشخص
- در انتظار تکمیل ورود
- باز کردن صفحه ورود
- کپی لینک
- کد تأیید
- ادامه
- لغو
- احراز هویت با موفقیت انجام شد
- زمان درخواست ورود به پایان رسیده است

Product names English remain as proper nouns.

---

# PHASE 13 — Security/observability

Auth logs only:
- request_id
- endpoint
- agent
- status
- duration
- error_code

Never log:
- verification URL
- query/state/code_challenge
- user code
- authorization code
- stdout/stderr
- account email
- tokens/cookies
- AGENT_SERVICE_TOKEN

Add tests injecting fake secrets and verify absent from response/log/error.

---

# PHASE 14 — Docs

Update:
- `agent-service/README.md`
- `.env.example`

Preferred production login:
`Admin → AI Settings → Agent Service → Agent → Authenticate`

Manual CLI login remains break-glass only.

Document:
- HOME volume persists credentials
- auth session itself in-memory/temporary
- restart during active session cancels session
- completed credential remains in HOME
- after restart auth state can be unknown until reliable probe/Test

---

# PHASE 15 — Real acceptance smoke

Automated tests are not enough.

Antigravity:
1. Authenticate from Admin UI
2. real URL appears
3. browser login
4. return code if required
5. UI authenticated
6. selected model Test
7. restart agent-service
8. Test again without login
9. image capability only after separate real image smoke
10. if image capability proven, one Body Analysis end-to-end

Codex:
same pattern; text/structured first, image stays false until proven.

Claude:
same pattern.

If credentials unavailable:
- implementation/tests را کامل کن
- success جعل نکن
- final report: `MANUAL AUTH ACCEPTANCE REQUIRED`
- یک checkpoint واضح برای human login بده.

---

# PHASE 16 — Regression

Agent Service:
```bash
cd agent-service
uv run pytest -q
uv run ruff check .
uv run mypy .
```

Backend targeted:
```bash
cd backend
uv run pytest   tests/admin/test_ai_task_settings_api.py   tests/ai/test_agent_service_provider.py   tests/ai/test_agent_service_admin_contract.py   tests/ai/test_agent_service_auth_admin.py   -q
```
Then full backend suite + Ruff. Unrelated pre-existing mypy failures را دست نزن؛ touched/new files mypy-clean باشند.

Frontend:
```bash
cd frontend
npm test
npm run lint
npm run build
```

Docker:
```bash
docker compose config
docker compose build agent-service backend
docker compose up -d
docker compose ps
```

Verify:
- backend بدون login agents بالا می‌آید
- agent-service healthy
- port 9001 public نیست
- Backend resolves agent-service
- bad internal token = 401
- active auth cleanup on restart
- HOME volume persists

---

# Final review checklist

Must be true:
- Browser never direct to Agent Service
- token never frontend
- no auth session/credential DB storage
- credentials only HOME/keyring
- no auth URL/code/token log
- no raw stdout/stderr leak
- no shell
- one active auth session per agent
- TTL/cancel/reap/shutdown cleanup
- URL hosts allowlisted from real probes
- input command-injection safe
- capabilities no quota
- auth state not guessed from files
- OpenRouter path unchanged
- Agent Service internal-only
- image flags false unless real smoke passed
- UI cleaner/mobile-friendly
- no regression in per-task API/Agent routing

# Final report

Report:
1. files created/changed
2. exact observed auth mechanism for each CLI
3. version / PTY required / URL / user input / auth smoke / restart persistence
4. exact test results
5. security review
6. only genuinely remaining manual steps

تا آخر task-by-task ادامه بده.
فقط اگر repo contradiction جدی یا human browser login واقعی لازم شد سؤال/checkpoint بده.
هیچ capability یا success بدون evidence واقعی گزارش نکن.
