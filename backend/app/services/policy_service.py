from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.countries import resolve_country
from app.models.policy_acceptance import PolicyAcceptance
from app.models.user import User

_CONTENT_DIR = Path(__file__).resolve().parent.parent / "content" / "policies"


@dataclass(frozen=True)
class PolicyDocument:
    version: str
    title: str
    filename: str


# Adding a new country's own legal text: drop a markdown file in
# app/content/policies/ and add an entry here. Countries not listed (or not
# yet resolvable, e.g. AE today) fall back to DEFAULT_POLICY -- generic,
# non-jurisdiction-specific language -- rather than silently reusing another
# country's legal text.
POLICY_REGISTRY: dict[str, PolicyDocument] = {
    "CO": PolicyDocument(
        version="2026-08-12",
        title="Política de Tratamiento de Datos Personales — Colombia",
        filename="co.md",
    ),
}

DEFAULT_POLICY = PolicyDocument(
    version="2026-08-12",
    title="Política de Privacidad",
    filename="default.md",
)

# Unlike the privacy policy, terms of service aren't country-specific and
# there's no acceptance-tracking gate for them (PolicyAcceptance exists
# specifically for Habeas Data consent) -- just one versioned document.
TERMS_OF_SERVICE = PolicyDocument(
    version="2026-08-13",
    title="Términos y Condiciones de Uso",
    filename="terms.md",
)


@lru_cache
def _read_content(filename: str) -> str:
    return (_CONTENT_DIR / filename).read_text(encoding="utf-8")


def get_policy_for_country(country: str) -> PolicyDocument:
    return POLICY_REGISTRY.get(country.upper(), DEFAULT_POLICY)


def get_policy_content(document: PolicyDocument) -> str:
    return _read_content(document.filename)


async def get_latest_acceptance(db: AsyncSession, *, user_id) -> PolicyAcceptance | None:
    result = await db.execute(
        select(PolicyAcceptance)
        .where(PolicyAcceptance.user_id == user_id)
        .order_by(PolicyAcceptance.accepted_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def needs_acceptance(db: AsyncSession, *, user: User) -> bool:
    country = resolve_country(user.phone_number)
    if country is None:
        # Shouldn't happen for accounts created after the country gate went
        # in, but pre-existing/debug accounts with an unrecognized number
        # have no policy to show -- fail open rather than blocking them.
        return False
    current = get_policy_for_country(country)
    latest = await get_latest_acceptance(db, user_id=user.id)
    if latest is None:
        return True
    return latest.policy_country != country or latest.policy_version != current.version


async def record_acceptance(
    db: AsyncSession,
    *,
    user: User,
    ip_address: str | None,
    user_agent: str | None,
) -> PolicyAcceptance:
    country = resolve_country(user.phone_number)
    if country is None:
        raise ValueError(f"cannot record policy acceptance for unresolvable phone number country: {user.id}")
    document = get_policy_for_country(country)
    acceptance = PolicyAcceptance(
        user_id=user.id,
        policy_country=country,
        policy_version=document.version,
        accepted_at=datetime.now(UTC),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(acceptance)
    await db.flush()
    return acceptance
