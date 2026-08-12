# Buscomipana — Architecture & Reference

Comprehensive reference for the whole system: concept, data model, privacy model, channel abstraction, media storage, background jobs, API surface, environment variables, local development, testing, and known gaps.

For the original planning context and phased build order, see the plan history in `.claude/plans/` (not required reading to work in this codebase — this document is the current source of truth).

## Contents

- [Concept](#concept)
- [Tech stack](#tech-stack)
- [System overview](#system-overview)
- [Data model](#data-model)
- [Privacy & visibility model](#privacy--visibility-model)
- [Identity & auth](#identity--auth)
- [Channel abstraction (web / SMS / future IVR/USSD)](#channel-abstraction-web--sms--future-ivrussd)
- [Media storage & photo consent](#media-storage--photo-consent)
- [Near-miss / fuzzy matching](#near-miss--fuzzy-matching)
- [Background jobs](#background-jobs)
- [API surface](#api-surface)
- [Frontend](#frontend)
- [Environment variables](#environment-variables)
- [Local development](#local-development)
- [Testing](#testing)
- [Known limitations & deferred work](#known-limitations--deferred-work)

## Concept

A safety check-in and missing-person matching platform, phone-number-first so it works for people without smartphones or reliable data:

- **Passwordless accounts**: phone number + OTP (SMS today; voice/IVR is a reserved future channel).
- **Ping/pong**: a user reports their own status (`ok` / `distress` / `unknown`), optionally with location. A third party can report *on someone else's behalf* (a "proxy" ping) — always labeled as such, never silently attributed to the subject. Relatives/responders can "pong" back a response.
- **Relative handshake**: two accounts mutually link (request → accept), which is what unlocks seeing each other's precise location (status is more broadly visible — see [Privacy & visibility model](#privacy--visibility-model)).
- **Missing-person reporting**: report someone by name + phone number, even if they don't have an account yet ("unclaimed"). The report resolves automatically — either immediately (exact phone match) or later, the moment that phone number signs up (`resolve_open_reports_for_new_user`).
- **Verified responders**: an admin-verified credential (e.g. Red Cross) grants the same location/photo access as an accepted relative link, without requiring one.
- **Anonymized analytics**: every ping is mirrored into an irreversibly-hashed analytics table for pattern analysis, without exposing identity.
- **Everything in the frontend is Spanish**; the backend (code, API contracts, error strings, DB) is English, so the API stays usable by non-Spanish-speaking clients/integrators. Only the presentation layer is localized.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI + SQLAlchemy 2.0 (async) + asyncpg | Async-native for bursty SMS-webhook/fanout load; see `docs` gap re: Django tradeoff in original plan |
| Database | PostgreSQL 16 + `pg_trgm`, `fuzzystrmatch`, `cube`/`earthdistance`, `pgcrypto` | Fuzzy name/phone matching, coarse geo distance, UUID generation |
| Migrations | Alembic | Single hand-written initial migration (`0001_initial_schema`) — still pre-release, edited in place rather than stacking incremental migrations |
| Background jobs | Celery + Redis | Retry/backoff semantics for SMS delivery, periodic sweeps |
| Admin | SQLAdmin | Read-mostly ops views, JWT-based auth reusing the app's own tokens |
| SMS | Infobip (pluggable) | Two-way SMS + voice/IVR support in LatAm, relevant to a future IVR channel |
| Image processing | Pillow | EXIF stripping, format normalization, size capping |
| Object storage | Local disk (dev) / S3-compatible (prod, unverified — no AWS credentials in this environment) | Pluggable `MediaStorage` abstraction |
| Frontend | React + TypeScript + Vite, Tailwind CSS, TanStack Query, React Router | Installable PWA |

## System overview

```
Browser (PWA, Spanish UI)                     Infobip (SMS/voice)
        │  HttpOnly cookies                          │ webhook
        ▼                                             ▼
   FastAPI app  ──────────────────────────  /webhooks/infobip/*
        │                                             │
        │  reuses same ping_service.create_ping() regardless of origin
        ▼
   PostgreSQL  ◄───────────────  Celery worker + beat (Redis broker)
        │                              (SMS retry, OTP cleanup, analytics
        ▼                               anonymization, candidate search)
  media storage (local disk / S3)
```

Mobile/API clients authenticate via `Authorization: Bearer`; the browser authenticates via HttpOnly cookies set on the same endpoints — both paths are accepted by every protected route (`app/deps.py:get_current_user`).

## Data model

14 tables, defined in `backend/app/models/` and created by the single Alembic migration `backend/alembic/versions/0001_initial_schema.py`.

| Table | Purpose | Key relationships |
|---|---|---|
| `users` | Account + minimal profile PII | — |
| `otp_verifications` | OTP codes (hashed) for signup/login and phone-number change | `users.id` (nullable — signup case) |
| `auth_sessions` | Refresh-token sessions (hashed), revocable individually or all-at-once | `users.id` |
| `phone_number_changes` | Audit trail for phone-number corrections | `users.id`, `otp_verifications.id` |
| `relative_links` | The handshake: requester/target, status, relationship type | `users.id` ×2 |
| `responder_credentials` | Verified-responder status (org, credential type) | `users.id` |
| `pings` | Status reports; `is_proxy` is a DB-generated column (`reported_by_user_id IS DISTINCT FROM subject_user_id`) | `users.id` ×2 |
| `pongs` | Responses to a ping | `pings.id`, `users.id` |
| `missing_person_reports` | Missing/standing-relative reports, resolvable before the subject has an account | `users.id` (reporter, nullable matched_user) |
| `missing_person_match_candidates` | Ranked fuzzy-match candidates for a report | `missing_person_reports.id`, `users.id` |
| `inbound_sms_messages` | Idempotency log + parsed intent for inbound SMS (providers retry deliveries) | `pings.id` (nullable) |
| `sms_outbox` | Every outbound SMS attempt (OTP, notifications), for the Celery retry sweep | `pings.id`, `otp_verifications.id` (nullable) |
| `ping_analytics_events` | Irreversibly-hashed ping history for pattern analysis | none (by design — see below) |
| `media_assets` | Profile photos and missing-person-report photos | `users.id` (owner), `missing_person_reports.id` (nullable, unique — one photo per report) |

**No circular FK**: `media_assets` references both `users` and `missing_person_reports`, but neither of those tables points back into `media_assets`. "The current profile photo for user X" is found by querying the most recent `media_assets` row for `(owner_user_id=X, purpose=profile_photo)` — the same "latest row for this subject" pattern used for ping locations in fuzzy matching (`matching_service._latest_ping_location`).

**`ping_analytics_events` has no FK to `pings` or `users` at all**, on purpose — see [Privacy & visibility model](#privacy--visibility-model).

### Enums (`app/models/enums.py`)

All stored as `VARCHAR` + `CHECK` constraint (not native Postgres enum types), via a shared `str_enum()` helper (`app/models/types.py`) that forces SQLAlchemy to persist the enum's `.value` rather than its Python member name — the two differ for `BloodType` (`o_pos` vs `"O+"`), which is exactly the bug this helper exists to prevent.

| Enum | Values |
|---|---|
| `UserRole` | `user`, `responder`, `admin` |
| `UserStatus` | `active`, `deactivated` |
| `BloodType` | `A+ A- B+ B- AB+ AB- O+ O-` |
| `SexAtBirth` | `male`, `female`, `intersex`, `prefer_not_to_say` |
| `OtpPurpose` | `signup_or_login`, `phone_change` |
| `Channel` | `web`, `sms`, `ivr_call`, `ussd` (last two reserved, not implemented) |
| `RelationshipType` | `parent child sibling spouse grandparent grandchild aunt_or_uncle niece_or_nephew cousin guardian friend other` — closed vocabulary on purpose, so relationship data never needs free-text parsing |
| `RelativeLinkStatus` | `pending`, `accepted`, `declined`, `revoked` |
| `ResponderCredentialStatus` | `pending`, `verified`, `revoked` |
| `PingStatus` | `ok`, `distress`, `unknown` |
| `PongAudience` | `directed`, `broadcast` |
| `MissingPersonReportStatus` | `open`, `matched`, `closed` |
| `SmsIntent` | `ping_ok`, `ping_sos`, `pong`, `unrecognized` |
| `SmsOutboxPurpose` | `otp`, `ping_notification`, `pong_notification`, `missing_person_match` |
| `SmsOutboxStatus` | `queued`, `sent`, `delivered`, `failed` |
| `MediaAssetPurpose` | `profile_photo`, `missing_person_photo` |
| `MediaStorageBackend` | `local`, `s3` |

### Profile fields (`users`, all optional except phone number)

`full_name`, `blood_type`, `birth_date`, `national_id_number`, `birth_place`, `nationality`, `sex_at_birth`. `birth_date` replaced an earlier `birth_year` field (strictly more precise, no redundant data).

### Missing-person report fields (all optional besides name/phone)

`relationship`, `notes`, `last_known_latitude`/`longitude`, `missing_since`, `missing_location_description`, `last_known_clothing`, `body_marks`, plus a photo via `media_assets`.

## Privacy & visibility model

The single gate — `visibility_service.can_view_location(db, viewer_id, subject_id)` — is TRUE if the viewer *is* the subject, an **accepted** `relative_links` row connects them (either direction), or the viewer holds a **verified** `responder_credentials` row. It is reused for three things:

1. **Ping location** (`ping_service.serialize_ping`): `latitude`/`longitude`/`location_accuracy_m` are nulled out for anyone who fails the gate. **Ping `status`, `message`, `channel`, and `is_proxy` are visible to any authenticated user who knows the `subject_user_id`** — this is a deliberate design choice (alive/distress status is meant to be broadly discoverable; only precise location is a hard secret), confirmed and kept as-is. A user_id becoming known — e.g. via a matched missing-person report's `matched_user_id` — is enough to poll `GET /pings?subject_user_id=`, with no handshake required.
2. **Profile photo** (`media_asset_service.get_profile_photo_bytes_for_viewer`): same gate, same reasoning — a photo is at least as identifying as coordinates.
3. **`national_id_number`** on `GET /users/{id}` (`UserPublicOut`): populated only when the gate passes; `None` otherwise. Every other public profile field (name, blood type, birth date, etc.) is visible to any authenticated user who knows the ID, matching how `blood_type`/`birth_year` already worked before this field existed.

**Proxy-ping labeling is enforced at the render layer, not left to callers to remember**: `notification_service.render_ping_message()` takes the full `Ping` ORM row (never a stripped payload) and branches on the DB-generated `is_proxy` column, producing `"⚠ Reported BY {reporter} ON BEHALF OF {subject}: ..."` instead of `"{subject}: ..."`. Covered by `tests/test_pings.py`.

**Missing-person-report photos are the one place visibility is intentionally *not* gated** — any authenticated user can view one, matching the report's own existing open visibility (`GET /missing-person-reports/{id}` has no ownership check). This is exactly what the public-use consent captured at upload time authorizes; see [Media storage & photo consent](#media-storage--photo-consent).

### Anonymized analytics

`ping_analytics_events` stores `subject_hash = HMAC-SHA256(user_id, pepper)` and `ping_ref_hash = HMAC-SHA256(ping_id, pepper)` — never `user_id` or `ping_id` directly, and no FK to either table. The pepper (`ANALYTICS_PEPPER`) lives outside the database entirely, so a dump of this table alone cannot be reversed to identity even with full DB access. `ping_ref_hash` exists specifically as a **collision-free join key** for `record_pong_latency()` to find the right row to update — an earlier design that matched on `(subject_hash, ping_created_at)` had a real bug where two pings for the same subject in the same second (a genuine SQLite issue in tests, and a plausible race in Postgres under load) would raise `MultipleResultsFound` or update the wrong row; fixed by keying on the ping itself instead of a timestamp.

### Image privacy (EXIF stripping)

Every uploaded photo is re-decoded and rebuilt pixel-by-pixel via Pillow (`app/storage/image_processing.py`) before storage — deliberately not just re-saved, since that alone doesn't guarantee metadata removal in every Pillow code path. This strips embedded EXIF, which commonly includes **GPS coordinates from the phone that took the photo** — a real leak vector that would otherwise bypass every location control described above. Verified with a real embedded GPS EXIF tag in `tests/test_image_processing.py` (via `piexif`), confirming GPS data is present before processing and absent after.

## Identity & auth

- **No passwords.** `POST /auth/otp/request` (rate-limited, 5/min) sends a 6-digit code (hashed with argon2 at rest) via the SMS gateway; `POST /auth/otp/verify` consumes it and creates the account on first use — the same endpoint pair handles signup and login.
- **`users.id` (UUID) is the permanent identity; `phone_number` is a mutable column** (partial-unique index `WHERE deleted_at IS NULL`), so correcting a mis-typed number is an `UPDATE`, not an identity change — no FK ever breaks. Corrections go through the same OTP flow (`purpose=phone_change`), audited in `phone_number_changes`.
- **Sessions**: short-lived JWT access token + rotating opaque refresh token (hash stored in `auth_sessions`). `logout-all` revokes every session in one `UPDATE` — important if a phone is lost.
- **Dual auth transport**: `Authorization: Bearer` (mobile/API/tests) and HttpOnly cookies (`bmp_access_token`, `bmp_refresh_token`, set by `_set_auth_cookies` in `app/api/v1/auth.py`) are both accepted by `get_current_user`. The browser client never touches the actual tokens — `frontend/src/api/client.ts` relies entirely on the cookie plus a plain `localStorage` boolean UI hint (`bmp_logged_in`) that carries no security weight.
- **Admin bootstrap**: no invite system exists yet — a phone number listed in `ADMIN_PHONE_NUMBERS` is promoted to `role=admin` the moment it first signs up (`auth_service.verify_login_otp`).
- **Every new signup gets an initial `status=ok` self-ping** (channel `web`), which (a) seeds ping history immediately and (b) is what `resolve_open_reports_for_new_user` piggybacks on to auto-resolve any missing-person report that was filed against this phone number before the account existed, notifying the reporter(s) by SMS.

## Channel abstraction (web / SMS / future IVR/USSD)

Every ping-producing path — the web REST endpoint and the Infobip inbound-SMS webhook — funnels through the **same** `ping_service.create_ping()`. Nothing downstream (notification fanout, analytics anonymization) needs to know which channel a ping came from.

- `NotificationGateway` (`app/gateways/base.py`): `send_otp`, `send_sms`, `place_ivr_call` (raises `NotImplementedError` — reserved). Implementations: `MockGateway` (local dev — logs to stdout, exposes `_debug/last-otp`) and `InfobipGateway` (real SMS, unverified against a live account in this environment).
- **Inbound normalization**: `POST /webhooks/infobip/sms/inbound` parses Infobip's payload into an `InboundChannelEvent`, which `channel_ingest_service.ingest()` turns into a `PING OK` / `PING SOS` / `PONG <phone> <message>` intent and calls `ping_service.create_ping()` — the exact function the web endpoint calls. Idempotent on `provider_message_id` (SMS providers retry deliveries); logged to `inbound_sms_messages` either way. Adding IVR later means one more adapter (`place_ivr_call`) and one more webhook handler — zero changes to `ping_service`.
- `POST /webhooks/infobip/voice/inbound` is a stub returning `501`, reserved for that future IVR phase.

## Media storage & photo consent

`MediaStorage` (`app/storage/base.py`) mirrors the gateway pattern: `save`/`read`/`delete` by opaque key, swappable via `MEDIA_STORAGE_BACKEND=local|s3`.

- **`LocalDiskStorage`**: writes under a root directory (docker-compose mounts it as the named volume `media_data`, kept separate from the bind-mounted source tree). Never exposed via a static-files mount — always read back through an authenticated endpoint so access control is identical regardless of backend.
- **`S3Storage`**: boto3-based (sync client wrapped in `asyncio.to_thread`), targets a private bucket (no public-read policy assumed) with optional `MEDIA_S3_ENDPOINT_URL` for S3-compatible services (MinIO, DigitalOcean Spaces). **Unverified against real S3** — no AWS credentials available in this environment; implemented directly against boto3's documented API.
- Every upload is validated (`image/jpeg|png|webp`, size-capped by `MEDIA_MAX_UPLOAD_BYTES`), EXIF-stripped, resized to a max 2000px edge, and normalized to JPEG before storage.

**Consent** (`media_assets.consent_public_use`, `consent_ai_processing`, `consent_recorded_at`):

- **Profile photo**: no consent flags required — visibility is gated (self/relative/responder), not public.
- **Missing-person-report photo**: `PUT /missing-person-reports/{id}/photo` **rejects the upload outright** (`422`) unless both `consent_public_use=true` and `consent_ai_processing=true` are submitted. This isn't just recorded after the fact — the whole point of this photo is that it's shown to any authenticated user searching for the subject and is the intended input for a **future** AI face-matching feature (not implemented), so both uses must be explicitly agreed to before the upload is accepted at all. The frontend surfaces both as separate, plain-language Spanish checkboxes (`MissingPersonsPage.tsx`) that must both be checked before the upload button enables.

## Near-miss / fuzzy matching

`matching_service.py` — Postgres-only (`pg_trgm` + `fuzzystrmatch`); a no-op on any other backend, including the SQLite used by unit tests (which cover the exact-match path instead).

- **Phone**: `levenshtein(phone_number, target) <= 2`, scored `1 - distance/length`.
- **Name**: `pg_trgm` `similarity()`, backed by a GIN trigram index.
- **Location** (optional): `earthdistance` proximity between a report's last-known coordinates and a candidate's most recent ping location, within 50km.
- **Combined score** = `0.5×phone + 0.35×name + 0.15×location`, computed in Python (tunable without a migration) and upserted into `missing_person_match_candidates` via `ON CONFLICT DO UPDATE`.
- Exact phone match resolves a report **immediately and synchronously** at creation time (before fuzzy search even runs); fuzzy candidates populate right after, inline for MVP scale (a high-volume deployment would enqueue `workers.tasks.search_missing_person_candidates` instead).
- `GET /search/people?phone=&name=` reuses the same scoring, gated to verified responders/admins (`require_responder`) — a direct PII lookup over a vulnerable population, not opened to all users.

## Background jobs

Celery + Redis (`app/workers/celery_app.py`, `app/workers/tasks.py`). `task_eager_propagates=True`; **eager mode is intentionally never enabled** — the FastAPI request path awaits the async services directly instead of calling these tasks synchronously, specifically to avoid nesting `asyncio.run()` inside an already-running event loop. These tasks are what a real Celery worker process consumes from Redis in production.

| Task | Trigger | Purpose |
|---|---|---|
| `send_queued_sms` | (available, not currently enqueued from the request path — see below) | Sends one `sms_outbox` entry via the gateway |
| `retry_failed_sms` | Beat, every 5 min | Re-enqueues `sms_outbox` rows with `status=failed` and `attempt_count < 5` |
| `cleanup_expired_otps` | Beat, hourly | Deletes `otp_verifications` older than 24h |
| `anonymize_ping` | Available | Wraps `analytics_service.anonymize_ping` for a worker-driven deployment |
| `record_pong_latency` | Available | Wraps `analytics_service.record_pong_latency` |
| `search_missing_person_candidates` | Available | Wraps `matching_service.populate_candidates` for high-volume deployments |

**Durability note**: the request path (`auth_service`, `notification_service`) already awaits the gateway directly and records the outcome via `sms_outbox_service.record_send_result` regardless of success/failure — so `retry_failed_sms` always has real failed rows to act on. This gives durable retry without routing the primary send path through Celery's eager mode.

## API surface

Base path `/api/v1`. Full request/response schemas are live at `/docs` (Swagger UI) — this is a map of what exists, not a parameter reference.

**Auth** — `POST /auth/otp/request`, `POST /auth/otp/verify`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/logout-all`, `POST /auth/phone-number/change/request`, `POST /auth/phone-number/change/confirm`

**Profile** — `GET/PATCH /users/me`, `GET /users/{id}`, `GET /users/me/pings`, `PUT/DELETE /users/me/profile-photo`, `GET /users/{id}/profile-photo`

**Relative handshake** — `POST/GET /relative-links`, `POST /relative-links/{id}/accept`, `POST /relative-links/{id}/decline`, `DELETE /relative-links/{id}`

**Ping/Pong** — `POST/GET /pings`, `GET /pings/{id}`, `POST/GET /pings/{id}/pongs`

**Missing-person reports** — `POST/GET /missing-person-reports`, `GET /missing-person-reports/{id}`, `GET /missing-person-reports/{id}/candidates`, `POST /missing-person-reports/{id}/candidates/{candidate_user_id}/confirm`, `PUT/GET /missing-person-reports/{id}/photo`

**Search** — `GET /search/people` (responder/admin only)

**Responders/admin** — `POST /responders/apply`, `GET /admin/responders/pending`, `POST /admin/responders/{id}/verify`, `POST /admin/responders/{id}/revoke`

**Infobip webhooks** — `POST /webhooks/infobip/sms/inbound`, `POST /webhooks/infobip/sms/delivery-report`, `POST /webhooks/infobip/voice/inbound` (stub, 501)

**Debug** — `GET /_debug/last-otp` (local env only)

## Frontend

React + TS + Vite PWA, `frontend/src/`:

```
api/client.ts         fetch wrapper: cookie auth, 401→refresh→retry, multipart upload, blob fetch
api/types.ts           wire types (mirror backend Pydantic schemas)
api/relationships.ts   RelationshipType → Spanish label map + option list
api/enums_es.ts        SexAtBirth → Spanish label map + option list
hooks/useAuthenticatedImage.ts   fetches a gated photo endpoint as a blob → object URL (never a raw <img src>,
                                  since that would bypass the same visibility check every other field goes through)
components/NavBar.tsx
pages/LoginPage.tsx        OTP phone/code flow
pages/ProfilePage.tsx      profile fields + photo upload/delete
pages/PingsPage.tsx        self check-in (OK/distress) + geolocation capture + history
pages/RelativesPage.tsx    handshake request/accept/decline/revoke + relative status + avatar
pages/MissingPersonsPage.tsx  report form + fuzzy-candidate confirmation + photo upload with consent checkboxes
```

**Language split**: all UI copy (labels, buttons, placeholders, status text, the PWA manifest name/description, `index.html` `lang="es"`) is Spanish. Wire values (enum literals like `sibling`, `distress`, `profile_photo`) stay the English strings the backend defines — only display labels are translated, via the small `*_es.ts` mapping files, so the API contract never depends on UI language.

## Environment variables

Defined in `backend/app/core/config.py` (`Settings`), documented with defaults in `.env.example`.

| Variable | Purpose |
|---|---|
| `ENV` | `local` enables `/​_debug/last-otp` and relaxes cookie `Secure` default |
| `APP_NAME` | Display brand name — FastAPI title and OTP/notification SMS text (`gateways/base.py:render_otp_message`) |
| `DATABASE_URL`, `POSTGRES_*` | Postgres connection |
| `REDIS_URL` | Celery broker |
| `JWT_SECRET`, `JWT_ACCESS_TOKEN_TTL_MINUTES`, `JWT_REFRESH_TOKEN_TTL_DAYS` | Session tokens |
| `ANALYTICS_PEPPER`, `ANALYTICS_PEPPER_VERSION` | Out-of-DB secret for `ping_analytics_events` hashing; rotate periodically (bump the version) |
| `SMS_GATEWAY` | `mock` \| `infobip` |
| `INFOBIP_BASE_URL`, `INFOBIP_API_KEY`, `INFOBIP_SENDER_ID`, `INFOBIP_WEBHOOK_SHARED_SECRET` | Infobip SMS gateway + inbound webhook auth |
| `ADMIN_PHONE_NUMBERS` | Comma-separated phone numbers auto-promoted to `admin` on first signup |
| `FRONTEND_ORIGIN`, `ACCESS_TOKEN_COOKIE_NAME`\*, `REFRESH_TOKEN_COOKIE_NAME`\*, `COOKIE_SECURE` | Browser cookie auth + CORS (must be an explicit origin, not `*`, once `allow_credentials=True`) |
| `MEDIA_STORAGE_BACKEND` | `local` \| `s3` |
| `MEDIA_LOCAL_PATH` | Root directory for local disk storage |
| `MEDIA_MAX_UPLOAD_BYTES` | Upload size cap (default 8MB) |
| `MEDIA_S3_BUCKET`, `MEDIA_S3_REGION`, `MEDIA_S3_ACCESS_KEY_ID`, `MEDIA_S3_SECRET_ACCESS_KEY`, `MEDIA_S3_ENDPOINT_URL` | S3 backend config |

\* Have code defaults, not currently listed in `.env.example`.

## Local development

```bash
docker compose up -d
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python -m scripts.seed_demo   # 3 demo accounts, 1 responder, 1 matched report
```

Read a mock OTP two ways:
```bash
docker compose logs -f backend                                  # "MOCK SMS to +57...: Your Buscomipana code is 123456"
curl "http://localhost:8000/api/v1/_debug/last-otp?phone=%2B573001110001"
```

Resetting the dev database (e.g. after a schema change to the not-yet-released migration):
```bash
docker compose down -v && docker compose up -d
docker compose run --rm backend alembic upgrade head
```

Rebuilding after a backend dependency change (`pyproject.toml`):
```bash
docker compose build backend celery-worker celery-beat
```

## Testing

`backend/tests/` — 22 tests, run with `pytest` from `backend/`. Uses in-memory SQLite for everything that doesn't require Postgres-only features (JSONB → generic JSON via `PortableJSON`, trigram/levenshtein fuzzy matching, which no-ops on non-Postgres backends and is covered via the exact-match path instead). Photo tests use an isolated `LocalDiskStorage` under `tmp_path` (autouse fixture) so test runs never write into the repo.

| File | Covers |
|---|---|
| `test_auth.py` | OTP signup/login round-trip, token refresh/rotation/revocation |
| `test_pings.py` | Location visibility gating, proxy-ping labeling |
| `test_responders.py` | Full responder credential lifecycle incl. immediate access revocation |
| `test_missing_person_reports.py` | Exact-phone-match resolution, fuzzy-search no-op on SQLite |
| `test_missing_person_retroactive_match.py` | Report filed before subject has an account, resolved on signup |
| `test_missing_person_photo.py` | Consent enforcement, public visibility, reporter-only upload |
| `test_profile_fields_and_photos.py` | New profile fields round-trip, national-ID gating, profile-photo visibility/deletion |
| `test_image_processing.py` | Real GPS EXIF stripping (via `piexif`), dimension capping, invalid-file rejection |
| `test_infobip_webhook.py` | Inbound SMS → same `create_ping()` path, idempotency, webhook auth |
| `test_analytics.py` | Anonymization irreversibility, pong-latency join correctness |
| `test_workers.py` | Celery task logic (direct async-function tests, not full `.delay()` dispatch — no Redis in this environment) |

Frontend: `npm run build` (`tsc -b && vite build`) type-checks and production-builds; no component test suite yet.

## Known limitations & deferred work

- **IVR / fixed-line call pings, USSD**: reserved in the `Channel` enum and gateway interface, not implemented.
- **WhatsApp**: not requested, but fits the same gateway abstraction — a natural phase-2 candidate given Infobip's WhatsApp Business API support and regional usage patterns.
- **S3 storage backend**: implemented against boto3's documented API, unverified against a real bucket (no AWS credentials in this environment).
- **AI photo matching**: consent is captured and enforced today; the matching feature itself is not built.
- **Native mobile apps**: the API is client-agnostic (OpenAPI-generated client, no web-only assumptions) but no native client exists.
- **Full analytics warehouse/dashboarding**: `ping_analytics_events` is populated; no OLAP store or dashboard on top of it.
- **Advanced fuzzy-matching tuning**: fixed scoring weights; no phonetic matching tuned for Spanish names or learned ranking.
- **Responder-org verification**: manual admin action via SQLAdmin; no document upload or registry integration.
- **PostGIS**: coarse `earthdistance` proximity used instead; fine geospatial (geofencing, heatmaps) deferred.
- **Offline ping queuing**: no service-worker background sync yet for submitting a ping with no connectivity.
- **Compliance**: Colombia's Ley 1581 de 2012 (Habeas Data) governs handling of the PII this app collects (phone number, blood type, national ID, photos) — a compliance review is advisable before wider rollout; not done here.
