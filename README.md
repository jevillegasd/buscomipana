# BuscoMiPana (Find My Sibling)

A phone-first safety check-in and missing-person matching platform for Colombia and Latin America, built to keep working when connectivity is poor.

Create an account with just a phone number (OTP, no password). "Ping" that you're OK or in distress, optionally with location. Link with relatives (mutual handshake) so they can see your status and, once linked, your location. Report someone as missing or standing, even before they have an account — the report resolves automatically the moment that phone number signs up. Everything in the product UI is in Spanish; the codebase, API, and database are in English so the backend stays usable by non-Spanish-speaking integrators.

## Documentation map

| Doc | Audience | Covers |
|---|---|---|
| **[backend/app/content/manual.html](backend/app/content/manual.html)**, served live at `GET /api/v1/manual` (linked from the login screen) | End users / product | Complete user manual of every screen and feature, in Spanish (the product's UI language) — including features that are planned but **not yet implemented**, called out explicitly. |
| **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** | Engineers | Data model, privacy/visibility model, channel abstraction (web/SMS today, IVR/USSD later), media storage, background jobs, and the complete API/environment-variable reference. |
| **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** | Ops / whoever runs prod | Taking the stack from local dev to a real deployment, network/Zero Trust posture, secret rotation, ongoing responsibilities. |
| **[docs/MESSAGE_TEMPLATES.md](docs/MESSAGE_TEMPLATES.md)** | Compliance / provider submissions | Every outbound SMS/email template with exact source text, a rendered example, and its trigger — the reference for SMS-provider or regulatory template-approval submissions. |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | Contributors | Workflow, lint/test commands, security-sensitive areas that get extra review scrutiny. |

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

## Repository structure

```
buscomipana/
├── backend/                     FastAPI application (Python 3.11+)
│   ├── app/
│   │   ├── api/v1/               Route handlers, one file per resource (auth, pings,
│   │   │                         relative_links, missing_person_reports, responders,
│   │   │                         search, admin, webhooks_infobip, debug) + router.py wiring
│   │   ├── core/                 Settings, DB session, JWT/security helpers, rate limiter,
│   │   │                         logging, startup_checks.py (refuses to boot with prod
│   │   │                         misconfiguration), countries.py (allowlisted phone prefixes)
│   │   ├── models/                SQLAlchemy 2.0 ORM models (one file per table/domain) +
│   │   │                         enums.py + types.py (the str_enum() persistence helper)
│   │   ├── schemas/               Pydantic request/response models, mirrored 1:1 with models/
│   │   ├── services/               Business logic — the layer both the web API and the SMS
│   │   │                         webhook call into, so every channel gets identical behavior
│   │   │                         (ping_service, visibility_service, matching_service, etc.)
│   │   ├── gateways/               SMS/notification provider abstraction — mock (dev),
│   │   │                         infobip, twilio, all implementing gateways/base.py
│   │   ├── storage/                 Media storage abstraction — local disk vs. S3-compatible,
│   │   │                         plus image_processing.py (EXIF stripping, resizing)
│   │   ├── workers/                 Celery app + background tasks (SMS retry, OTP cleanup,
│   │   │                         analytics anonymization, fuzzy-match search)
│   │   ├── content/policies/         Markdown source for the in-app privacy policy / terms
│   │   ├── content/manual.html        Single source of truth for the user manual, served live
│   │   │                         at GET /api/v1/manual and linked from the login screen
│   │   ├── admin.py                 SQLAdmin ops panel configuration
│   │   ├── deps.py                   FastAPI dependency-injection helpers (get_current_user, etc.)
│   │   └── main.py                   App factory, middleware, startup
│   ├── alembic/versions/            Database migrations (schema currently pre-release —
│   │                               see ARCHITECTURE.md for the "single migration" note)
│   ├── scripts/seed_demo.py          Populates demo accounts/data for local dev
│   └── tests/                        pytest suite, one file per feature area
│
├── frontend/                     React + TypeScript + Vite PWA
│   └── src/
│       ├── api/                       Fetch client (cookie auth, 401→refresh→retry), wire
│       │                             types mirroring backend schemas, ES label maps
│       ├── components/                 Shared UI: NavBar, modals, phone input, image cropper
│       ├── hooks/                       useAuthenticatedImage (gated photo fetch → blob URL),
│       │                             useOnlineStatus
│       ├── pages/                       One file per screen — Login, Pings (status/check-in),
│       │                             Relatives, MissingPersons, Profile, About
│       └── utils/                       Small helpers (maps links, relative-time formatting)
│
├── docker/postfix/                Self-hosted outbound-mail container (email OTP fallback)
├── docs/
│   ├── ARCHITECTURE.md             Engineering reference (this is the source of truth for design)
│   ├── DEPLOYMENT.md               Production deployment + security posture
│   └── identity/                     Brand/visual identity guide (palette, tone)
├── docker-compose.yml              Local dev stack
├── docker-compose.prod.yml         Production stack (Cloudflare Tunnel, Caddy, Postfix, etc.)
├── Caddyfile                       Reverse proxy config used by both compose files
├── CONTRIBUTING.md                 Contributor workflow and security-sensitive-area guide
└── LICENSE                         MIT
```

**Where logic lives, in one sentence:** every ping-producing path (the web
`POST /pings` endpoint and the Infobip inbound-SMS webhook) funnels through
the same `services/ping_service.create_ping()`, so channel-specific code
(`api/v1/`, `gateways/`) never duplicates business rules — see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#channel-abstraction-web--sms--future-ivrussd)
for the full picture.

## Contributing

Contributions are welcome. Before opening a pull request, read
**[CONTRIBUTING.md](CONTRIBUTING.md)** — it covers the branch/PR workflow,
the lint and test commands both suites must pass, and which parts of the
codebase (auth, visibility gating, media processing) get extra review
scrutiny because they handle real people's PII, location, and photos.

Found a security vulnerability? Please don't open a public issue — email
**contact@buscomipana.com** instead.

## License

[MIT](LICENSE).
