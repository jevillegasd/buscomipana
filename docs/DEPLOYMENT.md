# Deployment Guide

This covers taking Buscomipana from local dev (`docker-compose.yml`) to a
real deployment (`docker-compose.prod.yml`), and the Zero Trust /
microsegmentation posture that stack implements.

## Architecture

```
Internet
   |
   |  (no inbound ports open on the host at all)
   v
cloudflared  ──edge network──  Caddy  ──app network──  frontend (static, nginx)
                                  |
                                  └──app network──  backend (FastAPI + SQLAdmin)
                                                        |
                                                     data network
                                                        |
                                          postgres ─────┴───── redis
                                                                  |
                                                            celery-worker
                                                            celery-beat
```

Three Docker networks, each service joined only to what it actually needs:

- **edge**: `cloudflared` <-> `caddy`. Nothing else touches it.
- **app**: `caddy` <-> `backend`, `caddy` <-> `frontend`. Neither `backend`
  nor `frontend` publish a host port — they're reachable only through Caddy.
- **data**: `backend`/`celery-worker`/`celery-beat` <-> `postgres`/`redis`.
  Unreachable from `edge` or `app`. Postgres and Redis publish **no host
  port at all**, so they're unreachable from outside the Docker host, full
  stop — not just "behind a firewall rule someone has to remember to write."

`cloudflared` makes an outbound-only connection to Cloudflare's edge; there
is no inbound port open on the host for any service, for anything. This is
the actual "Zero Trust" mechanism here — not a slogan, a specific property:
nothing on the public internet has a route to any container except through
Cloudflare's own network, which can additionally gate requests by identity
(see the Cloudflare Access step below) rather than just "is this the right
IP."

## One-time setup

### 1. Generate secrets

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Run this **four separate times** for `JWT_SECRET`, `ADMIN_SESSION_SECRET`,
`ANALYTICS_PEPPER`, and `INFOBIP_WEBHOOK_SHARED_SECRET` — four different
values, never reuse one across two of these. `JWT_SECRET` and
`ADMIN_SESSION_SECRET` in particular guard two different trust boundaries
(API bearer tokens vs. the SQLAdmin browser session); a leak of one must not
compromise the other.

### 2. Fill in `.env.production`

```bash
cp .env.production.example .env.production
```

Fill in every blank — the app **refuses to start** (see
`backend/app/core/startup_checks.py`) if `ENV=production` and any secret is
still a placeholder, shorter than 32 characters, `COOKIE_SECURE` isn't
`true`, or the database password still matches the local-dev default. This
is deliberate: better a failed deploy than forgeable JWTs in production.

### 3. Set up the Cloudflare Tunnel

In the Cloudflare dashboard: **Zero Trust > Networks > Tunnels > Create a
tunnel** (choose "Cloudflared"). Name it, then under "Install and run a
connector" copy the token from the `cloudflared tunnel run --token <TOKEN>`
command shown — that's `CLOUDFLARE_TUNNEL_TOKEN` in `.env.production`.

Add a **Public Hostname** on the tunnel pointing your domain
(`PUBLIC_DOMAIN`) at `http://caddy:80` (service name, since it's resolved
inside the `edge` Docker network, not the public internet).

### 4. Gate `/admin` with Cloudflare Access

The SQLAdmin ops panel is already behind an admin-role JWT check
(`backend/app/admin.py`), but a second, independent layer at the network
edge is worth the five minutes: **Zero Trust > Access > Applications > Add
an application** → Self-hosted → path `your-domain.example/admin*` → add a
policy requiring, e.g., a specific email address/domain via one-time PIN.
This means a stolen/forged JWT alone isn't enough to reach the admin login
page at all — a second, independently-compromised factor is needed too,
which is the actual point of defense in depth.

### 5. First boot

```bash
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.prod.yml up -d
```

### 6. Create the real admin account, then tighten `ADMIN_PHONE_NUMBERS`

Any phone number listed in `ADMIN_PHONE_NUMBERS` is promoted to admin
automatically the moment it first signs up — by design (there's no
invite-code system yet), but it means that env var is a live credential
list, not a one-time bootstrap flag. Sign up with the real admin's number,
confirm `role: "admin"` on `GET /api/v1/users/me`, then either remove
`ADMIN_PHONE_NUMBERS` from `.env.production` entirely or narrow it to
numbers you're actively about to onboard — don't leave a standing list of
numbers with silent admin auto-promotion.

### Email OTP fallback (self-hosted, no external SMTP provider)

The login screen's "no me llegó el SMS, enviar por correo" option (see
`backend/app/services/email_service.py`) routes through a self-hosted
Postfix container (`docker/postfix/`, service `postfix` in
`docker-compose.prod.yml`) rather than a third-party SMTP provider. It's an
unauthenticated relay reachable only from `backend` over the internal `mail`
Docker network — no host port published, same treatment as postgres/redis.

Two things worth knowing if this ever needs debugging:

- **Chroot is disabled** for every Postfix service (see the `sed` in
  `docker/postfix/Dockerfile`). Debian's default `master.cf` chroots the
  outbound delivery agent into `/var/spool/postfix/`, which has no
  `/etc/resolv.conf` of its own — every MX lookup failed with "Host not
  found, try again" until this was turned off. No security benefit to the
  chroot inside an already Docker-isolated container anyway.
- **`myhostname` in `docker/postfix/main.cf` is pinned to this VPS's actual
  PTR-record hostname** (`srv1898238.hstgr.cloud`), not `buscomipana.com`.
  Receiving mail servers commonly spam-score a HELO/EHLO name that doesn't
  match reverse DNS for the connecting IP — don't "clean this up" to match
  the app's public domain without re-testing deliverability.
- Logs go to `docker compose -f docker-compose.prod.yml logs postfix`
  (`maillog_file = /dev/stdout` in `main.cf` — without it, Postfix logs via
  syslog, which nothing in this minimal container runs, so they'd otherwise
  go nowhere visible).

If you'd rather use an external provider (SES, SendGrid, etc.) instead of
self-hosting: just point `SMTP_HOST`/`SMTP_PORT`/`SMTP_USERNAME`/
`SMTP_PASSWORD`/`SMTP_USE_TLS` at that provider in `.env.production` and
remove the `postfix` service — `email_service.py` doesn't care which.

## What's already hardened

- Every mutating/expensive endpoint is rate-limited per client IP (or per
  Cloudflare-verified client IP in this deployment — see
  `TRUST_CLOUDFLARE_HEADERS` below), including OTP requests (with an
  explicit resend cooldown), ping creation, missing-person reports,
  relative-link requests, responder search, and photo uploads.
- `GET /pings/{id}/pongs` requires authentication (previously didn't).
- Webhook secret comparison is constant-time (`hmac.compare_digest`).
- Baseline security headers (CSP, X-Frame-Options, X-Content-Type-Options,
  Referrer-Policy, Permissions-Policy, HSTS) on every response, both
  frontend (nginx) and backend (FastAPI middleware).
- `/docs`, `/redoc`, `/openapi.json` are disabled entirely outside local dev
  — no reason to hand out the full API surface/schema publicly.
- Image uploads reject decompression-bomb files cleanly instead of
  crashing, strip all EXIF/metadata (notably GPS tags), and are capped in
  size and pixel dimensions.
- Both Docker images run as a non-root user.
- The frontend image is a real production build (nginx serving static
  assets) — the Vite **dev server was previously what shipped as
  "production,"** which is a meaningfully different risk profile (it's
  explicitly not hardened for untrusted/internet traffic).
- `react-router-dom` upgraded off a version range with two known moderate
  CVEs (open redirect, SSR constructor injection) — neither was reachable
  given how this app uses the router (no dynamic redirect targets, no SSR),
  but there's no reason to carry a known CVE into production regardless.
- Postgres/Redis have no host-published port, in dev *or* prod compose.

### `TRUST_CLOUDFLARE_HEADERS`

Rate limiting keys on `CF-Connecting-IP` instead of the raw socket peer when
this is `true` — otherwise every request would appear to come from Caddy's
container IP, and the per-client rate limits would collapse into one shared
limit for the entire user base. **Only** enable this when the origin is
verifiably unreachable except through Cloudflare (exactly the Tunnel setup
above) — if a bypass path to the origin ever exists, a client could set that
header themselves and spoof past the rate limiter entirely.

## Ongoing responsibilities (not one-time)

- **Dependency scanning**: `pip-audit` (backend) and `npm audit` (frontend)
  came back clean as of this pass — re-run both periodically, not just
  before this one deploy.
- **Secret rotation**: if any secret is ever suspected leaked, rotate it —
  `JWT_SECRET` rotation invalidates all live sessions (acceptable,
  users just log in again), `ADMIN_SESSION_SECRET` invalidates admin panel
  sessions only, `ANALYTICS_PEPPER` rotation should bump
  `ANALYTICS_PEPPER_VERSION` (existing rows keep their old pepper version
  recorded, so historical data doesn't need to be recomputed).
- **`sms_outbox` monitoring**: distress-ping fanout and OTP sends both cost
  real money via Infobip — the outbox table is the audit log; worth an
  occasional glance for volume anomalies (a compromised account spamming
  distress pings, for instance, would show up there before it shows up as a
  bill).
- **Media storage**: `MEDIA_STORAGE_BACKEND=local` works for a first
  deploy but has no redundancy and lives in a single Docker volume — move to
  `s3` (already implemented, see `backend/app/storage/s3_storage.py`) once
  there's real user-uploaded content worth not losing.
- **Backups**: `postgres_data` is a named Docker volume with no backup
  strategy of its own — set up `pg_dump` on a schedule (or your host
  provider's volume-snapshot feature) before this holds real user data.
