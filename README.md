# Otklik

Otklik is intended to become a privacy-first anonymous case-management platform for
trusted appeals. The repository is currently at **Phase 2B: internal staff authentication,
secure sessions, and RBAC foundation**. Applicant submission and lookup APIs, operational
workflows, administration features, analytics, and machine learning are not implemented.

## Architecture

The project is a modular monolith with two deployable applications and two infrastructure
services:

- `apps/web`: Next.js 16 App Router frontend with React, TypeScript, Tailwind CSS,
  shadcn/ui, a native-fetch API client, and TanStack Query.
- `services/api`: Python 3.12 FastAPI application with async SQLAlchemy, Alembic, an async
  Redis-compatible Valkey client, canonical persistence models under `app/db/models`, and
  small cryptographic primitives under `app/core`, and internal staff authentication under
  `app/modules/auth`.
- PostgreSQL 17 with pgvector 0.8.6.
- Valkey 8.1.

Future business HTTP schemas and services remain boundaries under `services/api/app/modules`.
Only staff authentication is populated in this phase. See [Privacy model](docs/privacy-model.md)
and [MVP threat model](docs/threat-model.md) for the security assumptions and limitations.

## Prerequisites

- Docker Desktop with Docker Compose
- Node.js 24 and npm 11 for local frontend development
- Python 3.12 for local backend development

## Environment configuration

Copy the root template and replace every placeholder secret before using a shared or
production environment:

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
| `TRACK_HMAC_SECRET` | HMAC key reserved for future deterministic track-code lookup |
| `RATE_LIMIT_HMAC_SECRET` | HMAC key for transient staff-login rate-limit identifiers |
| `REFRESH_TOKEN_HMAC_SECRET` | Separate HMAC key for server-side refresh-token digests |
| `CONTENT_ENCRYPTION_KEY` | URL-safe base64 encoding of exactly 32 random bytes for AES-256-GCM |
| `ACCESS_TOKEN_TTL_MINUTES` | Staff access-token lifetime; defaults to 15 minutes |
| `REFRESH_SESSION_TTL_DAYS` | Staff refresh-session lifetime; defaults to 7 days |
| `REFRESH_COOKIE_NAME` | Refresh-cookie name; defaults to `otklik_staff_refresh` |
| `LOGIN_RATE_LIMIT_ATTEMPTS` | Attempts allowed per transient login/IP digest window |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | Valkey counter TTL; defaults to 300 seconds |
| `LOG_LEVEL` | Python log level; defaults to `INFO` |
| `CORS_ORIGINS` | Comma-separated origins or a JSON array |

All five secret variables are required when `APP_ENV=production`; signing/HMAC secrets must be
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
docker compose up -d postgres valkey
docker compose run --rm api alembic upgrade head
docker compose up --build -d
docker compose ps
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

The minimal `/staff/login` page redirects authenticated users to role-specific protected
placeholders. Those pages intentionally contain no workflow functionality.

### Demo staff seed

Set all `DEMO_*_PASSWORD` values from `.env.example`, then run from `services/api`:

```powershell
python -m app.scripts.seed_demo_staff
```

The command idempotently creates the configured operator, expert, and admin and creates the
expert profile. It never prints passwords or stores plaintext passwords, never runs at API
startup, and refuses production unless `--allow-production` is passed explicitly. The values
in `.env.example` are demo-only placeholders and must not be used for a real deployment.

After starting the API, verify login while retaining the refresh cookie:

```powershell
$body = @{ login = $env:DEMO_OPERATOR_LOGIN; password = $env:DEMO_OPERATOR_PASSWORD } | ConvertTo-Json
$login = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/login -Body $body -ContentType application/json -SessionVariable staffSession
Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/me -Headers @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/refresh -WebSession $staffSession
```

## Data model and privacy boundaries

Phase 2A added staff/category/routing metadata, appeal lifecycle metadata, participants and
history, encrypted-content records, attachment metadata, and an audit trail. There is no
applicant account or applicant identity table.

- `appeals` stores only operational metadata. Its unique `track_digest` is a binary
  HMAC-SHA256 result; no plaintext track number is stored.
- Appeal text, intake answers, chat messages, internal notes, feedback comments, and
  complaints have encrypted binary fields. AES-256-GCM envelopes include key version 1 and
  use a new nonce for every encryption.
- Optional crisis contact data is isolated in `crisis_contacts` for a future operator-only
  policy. Internal notes are isolated from applicant chat for the same reason.
- Attachments keep an opaque storage key, MIME type, size, and digest—never an original
  filename or public URL.
- Audit `reason` and `metadata_json` must never contain sensitive text, contact data,
  credentials, tokens, raw track numbers, or encryption keys.

Phase 2B adds only `staff_sessions`. Session rows contain digests and lifecycle timestamps,
never raw refresh tokens, IP addresses, User-Agent values, or device fingerprints. No business
endpoint currently reads or writes appeal entities.

## Migrations

Alembic uses the same `DATABASE_URL` setting as the application. Revision `20260909_0001`
enables pgvector; revision `20260909_0002` creates the Phase 2A schema without seed users or
sensitive sample data; revision `20260909_0003` adds revocable staff sessions:

```powershell
cd services/api
alembic upgrade head
alembic current
```

Create future revisions only after importing new SQLAlchemy models from
`app/db/models/__init__.py` so `Base.metadata` can discover them. Persistence helpers belong
in `app/db/repositories`; generic repository/factory layers are intentionally absent.

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
