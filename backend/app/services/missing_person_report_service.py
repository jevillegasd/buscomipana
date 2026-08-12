import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.gateways.base import fit_single_sms
from app.gateways.factory import get_gateway
from app.models.enums import (
    MissingPersonReportStatus,
    RelationshipType,
    SmsOutboxPurpose,
)
from app.models.missing_person_report import (
    MissingPersonMatchCandidate,
    MissingPersonReport,
)
from app.models.user import User
from app.services import sms_outbox_service

settings = get_settings()


class MissingPersonReportError(Exception):
    pass


class ReportNotFound(MissingPersonReportError):
    pass


class CandidateNotFound(MissingPersonReportError):
    pass


class NotReportOwner(MissingPersonReportError):
    pass


async def create_report(
    db: AsyncSession,
    *,
    reporter: User,
    subject_full_name: str,
    subject_phone_number: str,
    relationship: RelationshipType | None,
    notes: str | None,
    last_known_latitude: float | None,
    last_known_longitude: float | None,
    missing_since: date | None = None,
    missing_location_description: str | None = None,
    last_known_clothing: str | None = None,
    body_marks: str | None = None,
) -> MissingPersonReport:
    """Ships the cheap, instant win first: an exact phone-number match against
    users.phone_number resolves the report immediately. Fuzzy/near-miss
    candidates (mis-typed digits, similar names) are populated afterwards by
    matching_service via a background job (see build step 10)."""
    report = MissingPersonReport(
        reporter_user_id=reporter.id,
        subject_full_name=subject_full_name,
        subject_phone_number=subject_phone_number,
        relationship=relationship,
        notes=notes,
        last_known_latitude=last_known_latitude,
        last_known_longitude=last_known_longitude,
        missing_since=missing_since,
        missing_location_description=missing_location_description,
        last_known_clothing=last_known_clothing,
        body_marks=body_marks,
        status=MissingPersonReportStatus.open,
    )

    exact_match = await db.execute(
        select(User).where(User.phone_number == subject_phone_number, User.deleted_at.is_(None))
    )
    matched_user = exact_match.scalar_one_or_none()
    if matched_user is not None:
        report.status = MissingPersonReportStatus.matched
        report.matched_user_id = matched_user.id
        report.matched_at = datetime.now(UTC)

    db.add(report)
    await db.flush()
    return report


async def get_report(db: AsyncSession, *, report_id: uuid.UUID) -> MissingPersonReport:
    result = await db.execute(select(MissingPersonReport).where(MissingPersonReport.id == report_id))
    report = result.scalar_one_or_none()
    if report is None:
        raise ReportNotFound(str(report_id))
    return report


async def list_reports_for_reporter(db: AsyncSession, *, reporter_id: uuid.UUID) -> list[MissingPersonReport]:
    result = await db.execute(
        select(MissingPersonReport)
        .where(MissingPersonReport.reporter_user_id == reporter_id)
        .order_by(MissingPersonReport.created_at.desc())
    )
    return list(result.scalars().all())


async def list_candidates(db: AsyncSession, *, report_id: uuid.UUID) -> list[MissingPersonMatchCandidate]:
    result = await db.execute(
        select(MissingPersonMatchCandidate)
        .where(MissingPersonMatchCandidate.report_id == report_id)
        .order_by(MissingPersonMatchCandidate.combined_score.desc())
    )
    return list(result.scalars().all())


async def confirm_candidate(
    db: AsyncSession, *, reporter: User, report_id: uuid.UUID, candidate_user_id: uuid.UUID
) -> MissingPersonMatchCandidate:
    report = await get_report(db, report_id=report_id)
    if report.reporter_user_id != reporter.id:
        raise NotReportOwner()

    result = await db.execute(
        select(MissingPersonMatchCandidate).where(
            MissingPersonMatchCandidate.report_id == report_id,
            MissingPersonMatchCandidate.candidate_user_id == candidate_user_id,
        )
    )
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise CandidateNotFound()

    candidate.confirmed = True
    report.status = MissingPersonReportStatus.matched
    report.matched_user_id = candidate_user_id
    report.matched_at = datetime.now(UTC)
    await db.flush()
    return candidate


async def resolve_open_reports_for_new_user(db: AsyncSession, *, new_user: User) -> list[MissingPersonReport]:
    """The mirror image of the exact-match check in create_report(): a report
    can be filed for a phone number *before* that person ever creates an
    account (the whole point of "unclaimed" missing-person reports). Called
    from auth_service on every new signup so those reports resolve the moment
    the subject finally registers, instead of sitting open forever."""
    result = await db.execute(
        select(MissingPersonReport).where(
            MissingPersonReport.subject_phone_number == new_user.phone_number,
            MissingPersonReport.status == MissingPersonReportStatus.open,
        )
    )
    reports = list(result.scalars().all())
    if not reports:
        return reports

    now = datetime.now(UTC)
    for report in reports:
        report.status = MissingPersonReportStatus.matched
        report.matched_user_id = new_user.id
        report.matched_at = now
    await db.flush()

    await _notify_reporters_of_match(db, reports=reports, matched_user=new_user)
    return reports


async def _notify_reporters_of_match(
    db: AsyncSession, *, reports: list[MissingPersonReport], matched_user: User
) -> None:
    reporter_ids = {r.reporter_user_id for r in reports}
    result = await db.execute(select(User).where(User.id.in_(reporter_ids)))
    reporters = result.scalars().all()

    subject_name = matched_user.full_name or matched_user.phone_number
    # No location here -- reporting someone missing does not establish a
    # relative-link handshake, so location stays gated by that separate,
    # mutual-consent flow (see visibility_service.can_view_location).
    message = fit_single_sms(
        f"{subject_name} ({matched_user.phone_number}) se registró en {settings.app_name} y reportó "
        "estar bien. Lo habías reportado como desaparecido o en pie."
    )
    gateway = get_gateway()
    for reporter in reporters:
        send_result = await gateway.send_sms(
            reporter.phone_number, message, idempotency_key=f"missing-match:{matched_user.id}:{reporter.id}"
        )
        await sms_outbox_service.record_send_result(
            db,
            to_phone_number=reporter.phone_number,
            purpose=SmsOutboxPurpose.missing_person_match,
            body=message,
            result=send_result,
        )
