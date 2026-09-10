# Otklik

Otklik is a privacy-first anonymous case-management platform for trusted appeals. The
repository is currently at the **hackathon MVP through administration (C7) and metadata-only
analytics (C8)**. Anonymous
creation and status access, staff authentication, operator triage, persistent crisis rules,
expert/applicant dialogue, collaboration, and encrypted image handling are implemented. The
configuration workspace, audit viewer, metadata analytics, and privacy-safe CSV export are
implemented. Machine learning and final visual redesign are not.

## Quick start

Requirements: Docker Desktop, or Docker Engine with Docker Compose. A fresh evaluator machine
does not need Python, Node.js, PostgreSQL, or Valkey installed locally.

```text
git clone <repository-url>
cd otklik
docker compose up --build
```

Open the applicant site at `http://localhost:3000` and staff login at
`http://localhost:3000/staff/login`.

| Demo role | Login | Password |
| --- | --- | --- |
| Administrator | `demo_admin` | `AdminDemo_2026!` |
| Operator | `demo_operator` | `OperatorDemo_2026!` |
| General expert | `demo_expert` | `ExpertDemo_2026!` |
| Psychologist | `demo_psychologist` | `ExpertDemo_2026!` |
| Lawyer | `demo_lawyer` | `ExpertDemo_2026!` |
| Social teacher | `demo_social` | `ExpertDemo_2026!` |
| Conflict specialist | `demo_conflict` | `ExpertDemo_2026!` |

These credentials and Compose secrets are deterministic, **development-only** evaluator
defaults. No real data is included. Production mode explicitly rejects the built-in demo
cryptographic secrets; provide and rotate every database password, signing/HMAC secret,
content-encryption key, and demo credential before any real deployment.

The one-shot `bootstrap` service waits for healthy infrastructure, upgrades Alembic, and runs
the idempotent reference, demo-staff/routing, and synthetic metadata scenario seeds. API and
web startup depend on successful bootstrap completion. Seeds do not run inside normal API
startup. The scenario contains only clearly synthetic operational metadata—no appeal body,
message, note, contact, filename, track code, or other real/sensitive data.

## Architecture

The project is a modular monolith with two deployable applications and two infrastructure
services:

- `apps/web`: Next.js 16 App Router frontend with React, TypeScript, Tailwind CSS,
  shadcn/ui, a native-fetch API client, and TanStack Query.
- `services/api`: Python 3.12 FastAPI application with async SQLAlchemy, Alembic, an async
  Redis-compatible Valkey client, canonical persistence models under `app/db/models`, and
  small cryptographic primitives under `app/core`, staff authentication under
  `app/modules/auth`, the anonymous flow under `app/modules/appeals`, and operator/routing
  boundaries under `app/modules/operator` and `app/modules/routing`, with the participant-
  scoped expert workflow under `app/modules/expert`.
- PostgreSQL 17 with pgvector 0.8.6.
- Valkey 8.1.

Future business HTTP schemas and services remain boundaries under `services/api/app/modules`.
Feature services stay deliberately small and persistence remains under `app/db`. See [Privacy model](docs/privacy-model.md)
and [MVP threat model](docs/threat-model.md) for the security assumptions and limitations.

## Prerequisites

- Docker Desktop with Docker Compose
- Node.js 24 and npm 11 for local frontend development
- Python 3.12 for local backend development

## Environment configuration

The one-command development Compose path uses explicit demo-only defaults and does not require
an `.env` file. For native local development, copy the root template and replace every
placeholder secret before using a shared or production environment:

```powershell
Copy-Item .env.example .env
```

The API reads the following environment variables:

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | `development`, `testing`, or `production` |
| `DATABASE_URL` | Async SQLAlchemy PostgreSQL URL |
| `VALKEY_URL` | Redis-compatible Valkey URL |
| `JWT_SECRET` | HMAC secret used to sign short-lived staff access JWTs |
| `TRACK_HMAC_SECRET` | HMAC key for deterministic track-number lookup |
| `RATE_LIMIT_HMAC_SECRET` | HMAC key for transient staff/public rate-limit identifiers |
| `REFRESH_TOKEN_HMAC_SECRET` | Separate HMAC key for server-side refresh-token digests |
| `APPLICANT_ACCESS_JWT_SECRET` | Separate signing secret for temporary appeal-scoped access cookies |
| `CONTENT_ENCRYPTION_KEY` | URL-safe base64 encoding of exactly 32 random bytes for AES-256-GCM |
| `ACCESS_TOKEN_TTL_MINUTES` | Staff access-token lifetime; defaults to 15 minutes |
| `REFRESH_SESSION_TTL_DAYS` | Staff refresh-session lifetime; defaults to 7 days |
| `REFRESH_COOKIE_NAME` | Refresh-cookie name; defaults to `otklik_staff_refresh` |
| `LOGIN_RATE_LIMIT_ATTEMPTS` | Attempts allowed per transient login/IP digest window |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | Valkey counter TTL; defaults to 300 seconds |
| `APPLICANT_ACCESS_TTL_MINUTES` | Appeal capability lifetime; defaults to 30 minutes |
| `APPLICANT_ACCESS_COOKIE_NAME` | Appeal capability cookie name |
| `TRACK_ACCESS_RATE_LIMIT_ATTEMPTS` | Track checks per transient network window; defaults to 5 |
| `TRACK_ACCESS_RATE_LIMIT_WINDOW_SECONDS` | Track-check counter TTL; defaults to 60 seconds |
| `APPEAL_SUBMISSION_RATE_LIMIT_ATTEMPTS` | Submissions per transient network window; defaults to 10 |
| `APPEAL_SUBMISSION_RATE_LIMIT_WINDOW_SECONDS` | Submission counter TTL; defaults to one hour |
| `ATTACHMENT_STORAGE_PATH` | Private encrypted-blob directory |
| `ATTACHMENT_MAX_BYTES` | Input bytes per attachment; defaults to 10 MiB |
| `CRISIS_SUPPORT_*` | Organizer-approved public crisis panel copy/contact configuration |
| `OPERATOR_OVERDUE_HOURS` | Derived queue overdue threshold; defaults to 24 hours |
| `APPLICANT_MAX_RETURNS` | Maximum applicant returns after recommendations; defaults to 2 |
| `EXPERT_COMPOSER_LOCK_TTL_SECONDS` | Valkey expert composer-lock TTL; defaults to 30 seconds |
| `DEMO_*_LOGIN`, `DEMO_*_PASSWORD` | Development-only staff and specialist seed credentials |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` | Optional server-side SMTP transport (including Yandex SMTP) |
| `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`, `SMTP_USE_TLS` | Staff invitation sender and STARTTLS behavior |
| `STAFF_INVITE_TTL_HOURS` | One-time invite/reset expiry; defaults to 24 hours |
| `STAFF_FRONTEND_BASE_URL` | Server-side base URL used in setup links |
| `LOG_LEVEL` | Python log level; defaults to `INFO` |
| `CORS_ORIGINS` | Comma-separated origins or a JSON array |

All six secret variables are required when `APP_ENV=production`; signing/HMAC secrets must be
at least 32 bytes, and the content key is validated at startup in that environment. They remain optional in development and testing
until the related service is constructed. Wildcard CORS is always rejected because credentialed
requests are enabled. Generate a
content key outside source control with
`python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"`.

The browser-visible `NEXT_PUBLIC_API_BASE_URL` contains only the public API origin. Next.js
inlines it during `npm run build`, so rebuild the web image after changing it. For local
frontend work, copy `apps/web/.env.example` to `apps/web/.env.local`.

No request bodies, authorization headers, cookies, passwords, tokens, client IP addresses,
response bodies, or secret settings are logged. Uvicorn access logging is disabled by the
documented and container startup commands.

## Docker startup

The Compose stack uses service DNS names internally: the API connects to `postgres:5432`
and `valkey:6379`. Database and Valkey host mappings remain bound to localhost only.

```powershell
docker compose up --build
```

For detached operation and inspection:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs bootstrap api web
```

The local endpoints are:

- Frontend: `http://localhost:3000`
- API liveness: `http://localhost:8000/health`
- API readiness: `http://localhost:8000/api/v1/health/ready`
- Public API metadata: `http://localhost:8000/api/v1/meta`

## Backend startup

From `services/api`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --no-access-log
```

The existing root `.env` is discovered when the backend is launched from `services/api`.
In production, inject configuration through the process environment instead of copying a
secret-bearing file into an image.

## Frontend startup

From `apps/web`:

```powershell
Copy-Item .env.example .env.local
$env:NEXT_TELEMETRY_DISABLED="1"
npm ci
npm run dev
```

The root layout stays a Server Component. A small client provider owns the TanStack Query
cache. A separate client auth provider keeps the access token in memory only and renews it
through the scoped HttpOnly refresh cookie. Nothing is written to `localStorage` or
`sessionStorage`.

## Anonymous applicant flow

The public UI at `/` supports student, parent, and teacher submissions without an applicant
account. `GET /api/v1/public/reference` provides active seeded categories and four optional,
application-defined intake questions. Seed the Russian starter categories idempotently from
`services/api`:

```powershell
python -m app.scripts.seed_reference_data
```

`POST /api/v1/public/appeals` accepts JSON metadata and sensitive text, stores the text and
answers in separate AES-GCM ciphertext records, and returns a one-time visible number in the
format `ОТК-XXXX-XXXX`. Only its deterministic HMAC-SHA256 digest is stored. The response also
sets a short-lived, appeal-scoped, signed HttpOnly cookie. A later
`POST /api/v1/public/appeals/access` verifies a supplied number and establishes a new temporary
capability; the number is never put in a URL or browser storage. `GET .../current` returns only
applicant-safe status data, while `POST .../leave` clears the capability cookie.

Deterministic, auditable crisis phrase detection checks description and optional answers in
memory. It sets `crisis_flag` but never changes priority to urgent. The support panel is
non-blocking. Any phone or URL in `CRISIS_SUPPORT_*` must be approved by organizers before
production. On a crisis appeal, the optional contact endpoint encrypts contact data into the
isolated `crisis_contacts` table; declining it never affects submission.

Images are uploaded only after creation. JPEG, PNG, and WEBP inputs are magic-byte checked,
decoded with Pillow, bounded by pixel count, orientation-corrected, reconstructed from pixels,
and re-encoded without EXIF/geolocation metadata. Up to five 10 MiB inputs are accepted.
Encrypted blobs live in private storage under opaque extensionless keys. PostgreSQL stores no
original filename or public URL, and its SHA-256 digest covers the encrypted blob.

## Operator workflow and routing

Only an authenticated user whose role is exactly `operator` can use `/api/v1/operator`.
Administrators do not inherit triage-content access. The paginated queue defaults to new and
returned appeals, supports operational filters, and orders crisis attention first, urgent
priority second, and oldest waiting time third. Waiting and overdue values are derived rather
than persisted.

Operator detail decrypts only original content and intake answers inside the authorized
service path. Its explicit DTO contains no track material, crisis contact, applicant-specialist
chat, or internal notes. Category and priority changes use allowlisted audit metadata.
Assignment validates expert role, active state, eligible specialist-group membership, current
load, capacity, and status transition, then atomically updates participants and histories.
Rejection explanations are applicant-visible content and are AES-GCM encrypted separately
instead of being placed in audit or status-history free text.

Routing follows `category -> eligible groups -> active experts -> active workload -> capacity`.
The lowest load/capacity ratio is recommended with deterministic tie-breaking. Missing
eligibility and full-capacity states are explicit, and recommendation never assigns.

Crisis phrases are database rows, never administrator-supplied regex. Submission loads the
active small ruleset once and applies Unicode/case/`ё` normalization, punctuation and hyphen
separation, whitespace collapse, and token-boundary literal matching. Compact matching is an
explicit per-rule setting. Run `python -m app.scripts.seed_reference_data` after migration to
create missing defaults idempotently; matching existing rows are not overwritten or
reactivated. Administrators manage rules and can test transient text through the Phase 6A
configuration API; tester input is neither stored nor audited.

Crisis contact and attachment bytes use separate operator-only `no-store` endpoints. Contact
reads are audited without the value. Attachments are integrity-checked and decrypted without
revealing storage paths, storage keys, or original filenames.

## Staff authentication

Staff authentication exists only for operator, expert, and administrator accounts. Anonymous
applicants have no login and no account. The versioned API exposes:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

Access JWTs are short-lived and contain only staff ID, role, session ID, timestamps, issuer,
and audience. Opaque refresh tokens are rotated on use, stored only in an HttpOnly cookie, and
represented in PostgreSQL only by a keyed HMAC-SHA256 digest. The cookie is `Secure` in
production and scoped to `/api/v1/auth`. Deactivation and password changes revoke every active
session for the staff member. Central dependencies keep authentication (401) separate from
role authorization (403). Role alone never grants access to sensitive appeal content; future
appeal-level policies must also evaluate assignment, participation, and workflow state.

The minimal `/staff/login` page redirects authenticated users by role. The operator and expert
routes host their Phase 4/5 workspaces; `/staff/admin` is the exact-role configuration workspace.

## Expert dialogue and resolution

Expert queue/detail reads require both the exact `expert` role and an active primary or
coexecutor participant row for the specific appeal. Administrators and unrelated experts do
not inherit content access. Applicant-facing messages, internal notes, transfer reasons,
return explanations, feedback comments, and complaints are separate AES-GCM ciphertexts with
record-specific AAD. Applicant responses label every staff sender only as `Специалист`.

Specialist message, clarification, and final-recommendation writes require ownership of a
short-lived Valkey composer lock. The UI acquires it on composing, renews it every 15 seconds,
and releases it after sending; Valkey expiry recovers abandoned locks. Only non-sensitive
appeal/staff UUIDs are stored in the lock value/key. Polling is used instead of WebSockets.

The primary expert can add an eligible active coexecutor while remaining primary, or submit an
encrypted transfer request. An exact-role operator approves or rejects the transfer; approval
validates category eligibility and capacity and atomically updates the primary participant,
assignment, and history. Final recommendations are encrypted public messages and move the
appeal to `answer_ready`. The applicant can complete it or return it (at most twice) with an
encrypted explanation. Returned appeals re-enter the operator queue. Feedback is independent
of resolution; optional comments and complaints are encrypted, and complaints are available
only through the operator endpoint, never the expert workspace.

“Не могу взять обращение” creates a distinct targetless pending reassignment request. The
current expert remains responsible until an operator selects an eligible replacement and
approves it. Rejection leaves the assignment unchanged. Neither the request nor its encrypted
reason is included in applicant responses.

### Demo staff seed

Set all `DEMO_*_PASSWORD` values from `.env.example`, then run from `services/api`:

```powershell
python -m app.scripts.seed_demo_staff
```

Run the reference seed first. The command idempotently creates the configured operator,
administrator, general demo expert, psychologist, lawyer, social teacher, and conflict
specialist. Every expert receives a profile and one DEMO-only routing membership, with
overlapping category/group rules suitable for assignment, coexecutor, and transfer tests.
Specialist passwords can be configured individually; when omitted they use
`DEMO_EXPERT_PASSWORD` as a development-only fallback.
Only missing rows are added; existing group metadata and relationships are never overwritten.
It never prints passwords or stores plaintext passwords, never runs at API
startup, and refuses production unless `--allow-production` is passed explicitly. The values
in `.env.example` are deterministic demo-only credentials and must not be used for a real deployment.

After starting the API, verify login while retaining the refresh cookie:

```powershell
$body = @{ login = $env:DEMO_OPERATOR_LOGIN; password = $env:DEMO_OPERATOR_PASSWORD } | ConvertTo-Json
$login = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/login -Body $body -ContentType application/json -SessionVariable staffSession
Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/me -Headers @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/refresh -WebSession $staffSession
```

## Administrator configuration (Phase 6A)

The protected `/staff/admin` workspace is the product configuration panel. Its Russian
sections cover analytics overview, staff, metadata-only stuck appeals, audit, applicant types,
categories, intake questions, specialist groups,
expert memberships/capacity, category-to-group routing, crisis markers, crisis-support
resources, and a read-only view of safe environment-backed product settings. Product roles
remain fixed to `operator`, `expert`, and `admin`. Administrator APIs expose only staff and
configuration metadata; they do not return appeal text, chat, notes, attachments, crisis
contacts, return explanations, feedback/complaint plaintext, track material, ciphertext, or
secrets.

New staff accounts start without a password. Creating, reinviting, or resetting a staff
account creates a 48-byte-random URL-safe one-time token, stores only its SHA-256 digest, and
sends a setup link whose default lifetime is 24 hours. The `/staff/setup-password` page
consumes the link once and stores only an Argon2 password hash. Password reset, role change,
and deactivation revoke staff sessions as appropriate. SMTP is optional at startup; if it is
not configured, the account and invitation remain saved and the admin receives a controlled
“mail not sent” result. Configure the standard SMTP adapter with:

```dotenv
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=Отклик
SMTP_USE_TLS=true
STAFF_INVITE_TTL_HOURS=24
STAFF_FRONTEND_BASE_URL=http://localhost:3000
```

Run `python -m app.scripts.seed_reference_data` after migration. It idempotently creates only
missing starter applicant types, categories, four intake questions/mappings, and crisis rules;
it does not overwrite or reactivate administrator-managed rows. Applicant type tone controls
existing “ты/вы” copy. The public reference endpoint returns active applicant types,
categories, category-mapped active questions, and active crisis-support resources in configured
order. Server-side question validation enforces the current active field definition and
allowed choice options before the answer JSON is encrypted.

Routing configuration continues to use the Phase 2A `category_group_rules`, expert profiles,
and group memberships, so operator recommendations reflect admin changes immediately. Crisis
rules remain literal normalized phrases with an explicit compact-match switch—no regex, fuzzy
matching, or executable configuration. Crisis-support resources are separate public system
configuration and never contain the applicant's isolated crisis contact.

Safe settings are deliberately read-only and environment-backed in this time-boxed phase.
Database credentials, SMTP password, encryption key, JWT secrets, and HMAC secrets are never
available through the admin API. Meaningful mutations write allowlisted audit events containing
only configuration identifiers and safe field names; passwords, tokens, SMTP credentials, and
tester/applicant input are excluded.

## Data model and privacy boundaries

Phase 2A added staff/category/routing metadata, appeal lifecycle metadata, participants and
history, encrypted-content records, attachment metadata, and an audit trail. There is no
applicant account or applicant identity table.

- `appeals` stores only operational metadata. Its unique `track_digest` is a binary
  HMAC-SHA256 result; no plaintext track number is stored.
- Appeal text, intake answers, chat messages, internal notes, feedback comments, and
  complaints have encrypted binary fields. AES-256-GCM envelopes include key version 1 and
  use a new nonce for every encryption.
- Optional crisis contact data is isolated in `crisis_contacts` and can be decrypted only by
  the dedicated operator endpoint. Internal notes are isolated from applicant chat for the
  same reason.
- Attachments keep an opaque storage key, sanitized MIME type, encrypted blob size, and digest—never an original
  filename or public URL.
- Audit `reason` and `metadata_json` must never contain sensitive text, contact data,
  credentials, tokens, raw track numbers, or encryption keys.

Phase 2B adds only `staff_sessions`. Session rows contain digests and lifecycle timestamps,
never raw refresh tokens, IP addresses, User-Agent values, or device fingerprints. Phase 4
adds `crisis_rules` and encrypted `appeal_rejections` while reusing the Phase 2A routing,
participant, history, attachment, and audit tables.
Phase 5 adds encrypted transfer reasons and `appeal_return_explanations`; it reuses the
existing encrypted messages, notes, feedback, complaints, and participant tables.

## Migrations

Alembic uses the same `DATABASE_URL` setting as the application. Revision `20260909_0001`
enables pgvector; revision `20260909_0002` creates the Phase 2A schema without seed users or
sensitive sample data; revision `20260909_0003` adds revocable staff sessions; revision
`20260909_0004` adds persistent crisis rules and encrypted rejection explanations; revision
`20260909_0005` adds encrypted transfer reasons and applicant return explanations; revision
`20260910_0006` adds staff invitation digests, dynamic applicant types/questions/mappings,
staff email/profile metadata, and crisis-support configuration:

```powershell
cd services/api
alembic upgrade head
alembic current
```

Create future revisions only after importing new SQLAlchemy models from
`app/db/models/__init__.py` so `Base.metadata` can discover them. Persistence helpers belong
in `app/db/repositories`; generic repository/factory layers are intentionally absent.

## Evaluator acceptance checklist (C1–C8)

1. **C1 — anonymous intake:** open `/`, create an appeal without registration, choose a
   database-driven applicant type/category, answer configured questions, and save the one-time
   track number.
2. **C2 — anonymous return:** open “Проверить обращение”, enter the track number, and confirm
   that the capability cookie opens a URL that contains no track code.
3. **C3 — operator:** sign in as `demo_operator`, open the crisis/new queue, triage a case,
   inspect sanitized attachments if present, and assign the recommended eligible expert.
4. **C4 — expert:** sign in as the assigned expert, take the case into work, acquire the
   composer lock, send an encrypted message, add a separate internal note, and prepare final
   recommendations.
5. **C5 — return/complete:** reopen the appeal by track, reply to clarification, choose “Это не
   помогло” with an explanation and observe it return to the operator queue; on an
   `answer_ready` case choose “Это помогло” and optionally submit feedback.
6. **C6 — crisis:** submit text matching an active crisis rule; verify `crisis_flag` without
   automatic urgent priority, the non-blocking support panel, and isolated optional contact.
7. **C7 — administration:** sign in as `demo_admin`; create/edit a category, group, expert and
   capacity, connect category → group → expert, verify the operator recommendation changes,
   then use “Обращения” to intervene in a stuck case with a reason and verify the entry in
   “Аудит”. The admin must never see appeal content.
8. **C8 — analytics/export:** on admin “Обзор”, switch 7/30-day range, inspect KPI cards,
   charts and workload, download CSV, and confirm it contains metadata/timings only.

### Demo workflow notes

The synthetic seeded appeals make C7/C8 visible immediately. To demonstrate the full live
workflow with a new applicant submission, keep the displayed track number only in your test
notes, assign through the operator UI, work it through the expert UI, then return to the public
status page. Applicant credentials are never stored in browser storage, and specialist real
names are never shown publicly.

## Tests and linting

Backend, from `services/api`:

```powershell
ruff check .
pytest
```

PostgreSQL integration tests use synchronous Psycopg from the development dependency group,
apply pending migrations to the configured database, and roll back their constraint-test rows.
The application runtime remains async SQLAlchemy with asyncpg. Use a dedicated database URL in
CI.

Frontend, from `apps/web`:

```powershell
$env:NEXT_TELEMETRY_DISABLED="1"
npm run lint
npm run build
```

Compose validation and image builds, from the repository root:

```powershell
docker compose config --quiet
docker compose build
```
