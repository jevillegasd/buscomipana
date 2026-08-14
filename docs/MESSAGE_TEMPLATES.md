# Message Templates

Registry of every outbound SMS and email template the system can send, with exact source text,
a rendered example, and the condition that triggers it. Kept here as the durable reference for
provider/regulatory template-approval submissions (e.g. Infobip, or a telecom regulator) — update
this file whenever a template changes, is added, or is removed.

Message text is quoted verbatim in **Spanish** — that's the language the product actually sends
in (see [README.md](../README.md) for why the codebase is English but all user-facing copy is
Spanish). Placeholders are named exactly as the corresponding Python variables in source.

**Traffic nature:** 100% of the templates below are **transactional** — one-time access codes, or
notifications triggered by a direct user action (a status report, or a missing-person report
resolving). None is marketing or promotional content. The active brand name in production is
`BuscoMiPana` (`APP_NAME` in `.env.production`).

| | |
|---|---|
| Active templates | 6 |
| SMS | 4 |
| Email | 1 |
| Provider-side (registered, not sent by this code) | 1 |
| Marketing | 0 |

## T-01 — Access code (OTP) by SMS

**Category:** SMS · Transactional
**Trigger:** Sent when requesting login or signup by phone number (`POST /auth/otp/request`).
Same flow for new and existing accounts — there is no separate "signup" step.
**Source:** `backend/app/gateways/base.py:render_otp_message`

Template:

```
Tu código de {app_name} es {code}
```

Example, as delivered (34 / 160 chars):

```
Tu codigo de BuscoMiPana es 482913
```

The text is transliterated into the GSM-7 alphabet before sending (unrepresentable Spanish
accents are substituted: `código → codigo`) to guarantee a single SMS segment.

## T-02 — Access code (OTP) by email

**Category:** Email · Transactional
**Trigger:** Fallback for SMS, only available once the account has verified its number by SMS at
least once and has a backup email on file. The recipient is always the email already saved on the
account, never one supplied at request time.
**Source:** `backend/app/services/email_service.py`

Subject template:

```
Tu código de {app_name}
```

Subject example:

```
Tu código de BuscoMiPana
```

Body template:

```
Tu código de verificación de {app_name} es: {code}

Este código vence en {otp_ttl_minutes} minutos. Si no lo solicitaste, ignora este mensaje.
```

Body example (`otp_ttl_minutes` configured in production: 10):

```
Tu código de verificación de BuscoMiPana es: 482913

Este código vence en 10 minutos. Si no lo solicitaste, ignora este mensaje.
```

Not subject to the single-SMS-segment limit.

## T-03 — Distress alert to relatives (direct report)

**Category:** SMS · Transactional
**Trigger:** Sent to every relative with an **accepted** link when the person reports their own
status as "Necesito ayuda" (I need help). "I'm OK" reports never generate an SMS — only distress
triggers this send.
**Source:** `backend/app/services/notification_service.py:render_ping_message`, invoked by
`notify_ping`

Template:

```
{subject_name}: NECESITA AYUDA[ - {message}]
```

Example, as delivered (98 / 160 chars):

```
Maria Fernanda Rojas: NECESITA AYUDA - Atrapada en el bus, sin señal para llamar, cerca del puente
```

The status label is never truncated; only the optional free-text message is trimmed to whatever
segment space remains. Without a free-text message, the body is just `Maria Fernanda Rojas:
NECESITA AYUDA` (36 chars).

## T-04 — Distress alert to relatives (reported by a pana / proxy)

**Category:** SMS · Transactional
**Trigger:** Same trigger as T-03, but when another person (a linked relative) reported the
distress status **on behalf of** the affected person — never silently attributed to the subject.
**Source:** `backend/app/services/notification_service.py:render_ping_message` (same function as
T-03)

Template:

```
Reportado por {reporter_name} en nombre de {subject_name}: NECESITA AYUDA[ - {message}]
```

Example, as delivered (145 / 160 chars):

```
Reportado por Carlos Andrés Rojas en nombre de Maria Fernanda Rojas: NECESITA AYUDA - Atrapada en el bus, sin señal para llamar, cerca del puente
```

If the reporter's name isn't known, `{reporter_name}` falls back to `un pana` ("a buddy").

## T-05 — Match notification (missing-person report)

**Category:** SMS · Transactional
**Trigger:** Sent to whoever reported someone as missing, the moment that person signs up to
BuscoMiPana with the reported phone number — automatic resolution, no manual action. Excludes
location: that requires an accepted relative link, a separate flow.
**Source:** `backend/app/services/missing_person_report_service.py:_notify_reporters_of_match`,
invoked by `resolve_open_reports_for_new_user`

Template:

```
{subject_name} ({phone_number}) se registró en {app_name} y reportó estar bien. Lo habías reportado como desaparecido o en pie.
```

Example, as delivered (133 / 160 chars):

```
Maria Fernanda Rojas (+573001234567) se registro en BuscoMiPana y reporto estar bien. Lo habias reportado como desaparecido o en pie.
```

## T-06 — PIN template registered with Infobip's 2FA product

**Category:** Provisioned on the provider · Transactional
**Trigger:** Not a message this system composes and sends directly: it's the template registered
**once** in Infobip's 2FA application (`POST /2fa/2/applications/{id}/messages`) so Infobip
generates, delivers, and verifies the PIN on its own — this backend never sees the actual code for
this provider. Used instead of T-01 specifically because several Colombian carriers reject OTP
traffic sent over the generic SMS route (`error 592 REJECTED_NETWORK`), requiring it to originate
from the provider's dedicated 2FA infrastructure.
**Source:** `backend/app/gateways/infobip_gateway.py:_ensure_2fa_application`

Template registered with Infobip:

```
Tu codigo de BuscoMiPana es {{pin}}
```

`{{pin}}` is Infobip's own placeholder syntax, not a variable from this code. No accent on
"codigo," exactly as registered.

## Verified absent

Not listed above because they don't exist:

- **Responses to a report ("pong"):** responding to a status alert generates no SMS or email —
  it's only saved to the database.
- **Requesting or accepting a relative link:** the entire "panas" (buddy) flow is silent — no
  outbound message at all.
- **Any marketing, promotional, or unsolicited content:** no such template exists anywhere in the
  code.
