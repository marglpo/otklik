# Otklik

Otklik is intended to become a privacy-first anonymous case-management platform for
trusted appeals. The repository is currently at **Phase 2A: privacy domain, PostgreSQL data
model, and cryptographic foundation**. Applicant submission and lookup APIs, staff
authentication, operational workflows, administration, analytics, and machine learning are
not implemented.

## Architecture

The project is a modular monolith with two deployable applications and two infrastructure
services:

- `apps/web`: Next.js 16 App Router frontend with React, TypeScript, Tailwind CSS,
  shadcn/ui, a native-fetch API client, and TanStack Query.
- `services/api`: Python 3.12 FastAPI application with async SQLAlchemy, Alembic, an async
  Redis-compatible Valkey client, canonical persistence models under `app/db/models`, and
  small cryptographic primitives under `app/core`.
- PostgreSQL 17 with pgvector 0.8.6.
- Valkey 8.1.

Future HTTP schemas and services remain empty boundaries under `services/api/app/modules`.
They are deliberately not populated in this phase. See [Privacy model](docs/privacy-model.md)
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
| `JWT_SECRET` | Reserved secret for future token work; no JWT logic exists yet |
| `TRACK_HMAC_SECRET` | HMAC key reserved for future deterministic track-code lookup |
| `RATE_LIMIT_HMAC_SECRET` | Reserved secret for future privacy-preserving rate limits |
| `CONTENT_ENCRYPTION_KEY` | URL-safe base64 encoding of exactly 32 random bytes for AES-256-GCM |
| `LOG_LEVEL` | Python log level; defaults to `INFO` |
| `CORS_ORIGINS` | Comma-separated origins or a JSON array |

All four secret variables are required when `APP_ENV=production`, and the content key is
validated at startup in that environment. They remain optional in development and testing
until a crypto service is constructed. Wildcard CORS is rejected in production. Generate a
content key outside source control with
`python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"`.

The browser-visible `NEXT_PUBLIC_API_BASE_URL` contains only the public API origin. Next.js
inlines it during `npm run build`, so rebuild the web image after changing it. For local
frontend work, copy `apps/web/.env.example` to `apps/web/.env.local`.

No request bodies, authorization headers, client IP addresses, response bodies, or secret
settings are logged. Uvicorn access logging is disabled by the documented and container
startup commands.

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
cache, and the home page includes only a foundation-phase readiness diagnostic.

## Data model and privacy boundaries

Phase 2A adds staff/category/routing metadata, appeal lifecycle metadata, participants and
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

These are storage and utility foundations only; no business endpoint currently reads or
writes these entities.

## Migrations

Alembic uses the same `DATABASE_URL` setting as the application. Revision `20260909_0001`
enables pgvector; revision `20260909_0002` creates the Phase 2A schema without seed users or
sensitive sample data:

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

PostgreSQL integration tests require the running Compose `postgres` service and a database at
the current Alembic head. Constraint probes run in transactions that abort without retaining
their test rows. Use an isolated Compose project in CI.

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
