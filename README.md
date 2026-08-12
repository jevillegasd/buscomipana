# Buscomipana

A phone-first safety check-in and missing-person matching platform for Colombia and Latin America, built to keep working when connectivity is poor.

Create an account with just a phone number (OTP, no password). "Ping" that you're OK or in distress, optionally with location. Link with relatives (mutual handshake) so they can see your status and, once linked, your location. Report someone as missing or standing, even before they have an account — the report resolves automatically the moment that phone number signs up. Everything in the product UI is in Spanish; the codebase, API, and database are in English so the backend stays usable by non-Spanish-speaking integrators.

See **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for the full design: data model, privacy/visibility model, channel abstraction (web/SMS today, IVR/USSD later), media storage, background jobs, and the complete API/environment-variable reference.

> The project was previously named `find_my_sibling` — the local checkout folder still uses that name (renaming it was skipped to avoid disrupting an active OneDrive sync), but every package name, Docker container/DB name, API title, and piece of UI copy has been rebranded to Buscomipana.

## Stack

- **Backend**: FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL, Alembic migrations, Celery + Redis for background jobs, SQLAdmin for ops.
- **Frontend**: React + TypeScript + Vite, installable PWA, Tailwind CSS.
- **SMS**: Infobip (swappable gateway abstraction; mock gateway for local dev).
- **Media**: Pillow-processed (EXIF-stripped) photo uploads, pluggable storage (local disk for dev, S3-compatible for production).

## Quick start (Docker)

```bash
cp .env.example .env          # edit secrets/passwords as needed
docker compose up -d
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python -m scripts.seed_demo   # optional demo data
```

- Frontend: http://localhost:5173
- Backend API docs (Swagger): http://localhost:8000/docs
- Admin panel: http://localhost:8000/admin (log in with an admin account's access token)

No SMS provider is required locally: `SMS_GATEWAY=mock` (the default) logs OTP codes to `docker compose logs backend` and exposes them at `GET /api/v1/_debug/last-otp?phone=<number>` (local env only).

## Local development without Docker (backend)

```bash
cd backend
uv pip install -e ".[dev]"        # or: pip install -e ".[dev]"
pytest                            # 22 tests, run against SQLite for anything that doesn't need Postgres-only features
ruff check app tests scripts
```

Full Postgres-only behavior (fuzzy matching, generated columns) is covered by manual verification against the Docker stack — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#testing).

## Local development without Docker (frontend)

```bash
cd frontend
npm install
npm run dev      # expects the backend at http://localhost:8000 (see VITE_API_BASE_URL)
npm run build    # type-checks + production build
```
