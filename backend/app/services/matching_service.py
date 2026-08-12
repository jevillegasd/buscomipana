import math
import uuid

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.missing_person_report import (
    MissingPersonMatchCandidate,
    MissingPersonReport,
)

# Weighted per the approved architecture: phone similarity dominates (typos/digit
# transpositions are the most common real-world data-entry error), name is a
# secondary signal, location a light tie-breaker. Kept in Python (not a stored
# proc) so these are tunable without a migration.
PHONE_WEIGHT = 0.5
NAME_WEIGHT = 0.35
LOCATION_WEIGHT = 0.15

PHONE_LEVENSHTEIN_MAX = 2
NAME_SIMILARITY_MIN = 0.3
LOCATION_MAX_KM = 50.0


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def _phone_candidates(db: AsyncSession, phone_number: str) -> dict[uuid.UUID, float]:
    result = await db.execute(
        text(
            """
            SELECT id, levenshtein(phone_number, :phone) AS distance
            FROM users
            WHERE deleted_at IS NULL
              AND levenshtein(phone_number, :phone) <= :max_distance
            """
        ),
        {"phone": phone_number, "max_distance": PHONE_LEVENSHTEIN_MAX},
    )
    scores = {}
    for row in result.all():
        user_id, distance = row[0], row[1]
        longest = max(len(phone_number), 1)
        scores[user_id] = max(0.0, 1 - (distance / longest))
    return scores


async def _name_candidates(db: AsyncSession, full_name: str) -> dict[uuid.UUID, float]:
    result = await db.execute(
        text(
            """
            SELECT id, similarity(full_name, :name) AS sim
            FROM users
            WHERE deleted_at IS NULL AND full_name IS NOT NULL
              AND similarity(full_name, :name) >= :min_sim
            """
        ),
        {"name": full_name, "min_sim": NAME_SIMILARITY_MIN},
    )
    return {row[0]: float(row[1]) for row in result.all()}


async def _latest_ping_location(db: AsyncSession, user_id: uuid.UUID) -> tuple[float, float] | None:
    result = await db.execute(
        text(
            """
            SELECT latitude, longitude FROM pings
            WHERE subject_user_id = :user_id AND latitude IS NOT NULL AND longitude IS NOT NULL
            ORDER BY created_at DESC LIMIT 1
            """
        ),
        {"user_id": user_id},
    )
    row = result.first()
    if row is None:
        return None
    return float(row[0]), float(row[1])


async def search_people(db: AsyncSession, *, phone: str | None, name: str | None) -> list[dict]:
    """Standalone near-miss lookup for the /search/people endpoint -- same
    scoring building blocks as populate_candidates, but returned directly
    rather than persisted, since there's no missing-person report to attach
    them to. No-op on non-Postgres backends, same as populate_candidates."""
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return []
    if not phone and not name:
        return []

    phone_scores = await _phone_candidates(db, phone) if phone else {}
    name_scores = await _name_candidates(db, name) if name else {}
    candidate_ids = set(phone_scores) | set(name_scores)

    results = []
    for candidate_id in candidate_ids:
        phone_score = phone_scores.get(candidate_id, 0.0)
        name_score = name_scores.get(candidate_id, 0.0)
        combined = PHONE_WEIGHT * phone_score + NAME_WEIGHT * name_score
        results.append(
            {"user_id": candidate_id, "phone_similarity_score": phone_score, "name_similarity_score": name_score, "combined_score": combined}
        )
    results.sort(key=lambda r: r["combined_score"], reverse=True)
    return results


async def populate_candidates(db: AsyncSession, *, report: MissingPersonReport) -> list[MissingPersonMatchCandidate]:
    """Fuzzy/near-miss matching relies on Postgres's pg_trgm and fuzzystrmatch
    extensions (see alembic/versions/0001_initial_schema.py) and is a no-op on
    any other backend -- including the SQLite used by this repo's unit tests,
    which cover the exact-phone-match path instead (see
    missing_person_report_service.create_report)."""
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return []

    phone_scores = await _phone_candidates(db, report.subject_phone_number)
    name_scores = await _name_candidates(db, report.subject_full_name)
    candidate_ids = set(phone_scores) | set(name_scores)
    candidate_ids.discard(report.matched_user_id)

    for candidate_id in candidate_ids:
        phone_score = phone_scores.get(candidate_id, 0.0)
        name_score = name_scores.get(candidate_id, 0.0)
        location_score = None
        if report.last_known_latitude is not None and report.last_known_longitude is not None:
            location = await _latest_ping_location(db, candidate_id)
            if location is not None:
                distance_km = _haversine_km(
                    float(report.last_known_latitude), float(report.last_known_longitude), *location
                )
                location_score = max(0.0, 1 - (distance_km / LOCATION_MAX_KM)) if distance_km <= LOCATION_MAX_KM else 0.0

        combined = PHONE_WEIGHT * phone_score + NAME_WEIGHT * name_score + LOCATION_WEIGHT * (location_score or 0.0)

        stmt = (
            pg_insert(MissingPersonMatchCandidate)
            .values(
                report_id=report.id,
                candidate_user_id=candidate_id,
                phone_similarity_score=round(phone_score, 3),
                name_similarity_score=round(name_score, 3),
                location_score=round(location_score, 3) if location_score is not None else None,
                combined_score=round(combined, 3),
            )
            .on_conflict_do_update(
                constraint="uq_report_candidate",
                set_={
                    "phone_similarity_score": round(phone_score, 3),
                    "name_similarity_score": round(name_score, 3),
                    "location_score": round(location_score, 3) if location_score is not None else None,
                    "combined_score": round(combined, 3),
                },
            )
        )
        await db.execute(stmt)

    await db.flush()
    from app.services.missing_person_report_service import list_candidates

    return await list_candidates(db, report_id=report.id)
