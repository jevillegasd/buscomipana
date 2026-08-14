# Contributing to BuscoMiPana

Thanks for considering a contribution. BuscoMiPana handles real PII (phone
numbers, national ID numbers, blood type, GPS location, photos) for a
vulnerable-population use case, so a few things here are stricter than a
typical hobby project — please read the [Security-sensitive changes](#security-sensitive-changes)
section before touching auth, visibility, or media code.

## Ground rules

- All product-facing text (UI copy, SMS templates, error messages shown to
  users) must be **Spanish**. Code, comments, commit messages, API contracts,
  and internal docs are **English**. This split is intentional — see
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — don't "fix" it in either
  direction.
- Don't add a feature without also updating the docs that describe it:
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how it works internally,
  [backend/app/content/manual.html](backend/app/content/manual.html) (served
  live at `GET /api/v1/manual`, linked from the login screen) for what a user
  sees. A feature that exists in code but isn't documented, or documented but
  not built, is a bug in the docs either way.
- Any new or changed SMS/email template — anything sent via a
  `NotificationGateway` implementation or `email_service` — needs a matching
  update in [docs/MESSAGE_TEMPLATES.md](docs/MESSAGE_TEMPLATES.md). That file
  is the reference used for SMS-provider and regulatory template-approval
  submissions; an undocumented template is a template that hasn't been
  approved to send.
- Prefer small, focused pull requests over large ones. If a change touches
  both backend and frontend, that's fine in one PR as long as it's one
  coherent change — don't bundle unrelated cleanup in with a feature.

## Getting set up

See the [Quick start](README.md#quick-start-docker) section in the README for
running the full stack locally. For day-to-day backend/frontend-only work
without Docker, see [Local development](README.md#local-development-without-docker-backend).

## Before opening a pull request

**Backend** (from `backend/`):

```bash
ruff check app tests scripts   # lint
pytest                         # 22+ tests, must pass
```

**Frontend** (from `frontend/`):

```bash
npm run build   # tsc -b && vite build -- type-checks and must succeed
```

Note: `package.json` also defines an `npm run lint` script, but ESLint isn't
actually installed or configured in this repo yet — running it will fail.
Wiring up a real ESLint config is a welcome contribution; until then, `tsc`
via `npm run build` is the only enforced frontend check.

Neither suite is enforced by CI yet (there is no CI configuration in this
repo) — that means it's on you to run both before pushing, not optional
because "no bot will catch it."

### Tests

- New backend behavior needs a test in `backend/tests/`. Follow the existing
  pattern: SQLite-backed for anything that doesn't require a Postgres-only
  feature (trigram/levenshtein fuzzy matching, JSONB), which the test suite
  already routes around via `PortableJSON` and by testing the exact-match
  path instead of the fuzzy path on SQLite.
- There is no frontend component test suite yet. If you're the one adding
  it, open an issue first to agree on the tool (Vitest + Testing Library is
  the natural fit given the existing Vite setup) before sinking time into it.

### Commit messages

Write the commit message around **why**, not a restatement of the diff — the
diff already shows what changed. Look at `git log` for the house style before
your first commit.

## Security-sensitive changes

These areas get extra scrutiny in review — not to slow you down, but because
a mistake here leaks real people's location, ID numbers, or photos:

- **`app/services/visibility_service.py`** — the single gate for location,
  profile photo, and national ID visibility. If your change touches who can
  see what, it almost certainly belongs here, reused, not reimplemented
  somewhere else.
- **Auth and session code** (`app/services/auth_service.py`,
  `app/core/security.py`, `app/deps.py`) — OTP handling, token issuance,
  cookie flags.
- **Media upload/storage** (`app/storage/`) — EXIF stripping in particular;
  see the "why" comment in `image_processing.py` before changing how images
  are processed. A photo that skips re-encoding can leak the GPS coordinates
  embedded by the phone that took it.
- **Proxy-ping labeling** (`notification_service.render_ping_message`) — a
  report made *on behalf of* someone must never render as if that person sent
  it themselves.

If you find an actual vulnerability (not just a hardening idea), please don't
open a public issue — email **contact@buscomipana.com** with details first.

## Pull request process

1. Fork or branch from `main`.
2. Make your change, keeping it scoped to one coherent thing.
3. Run the lint/test commands above.
4. Open a PR describing **why** the change is needed, not just what it does —
   link an issue if one exists.
5. Be responsive to review comments; this is a young codebase and review is
   how it stays consistent.

## License

By contributing, you agree your contribution is licensed under the project's
[MIT License](LICENSE).
