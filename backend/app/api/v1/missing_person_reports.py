import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.limiter import limiter
from app.deps import get_current_user
from app.models.user import User
from app.schemas.missing_person_report import (
    MissingPersonMatchCandidateOut,
    MissingPersonReportCreateIn,
    MissingPersonReportOut,
)
from app.services import (
    matching_service,
    media_asset_service,
    missing_person_report_service,
)

router = APIRouter(prefix="/missing-person-reports", tags=["missing-person-reports"])


async def _build_report_out(db: AsyncSession, report) -> MissingPersonReportOut:
    asset = await media_asset_service.get_missing_person_photo_asset(db, report_id=report.id)
    out = MissingPersonReportOut.model_validate(report)
    return out.model_copy(update={"has_photo": asset is not None})


@router.post("", response_model=MissingPersonReportOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_report(
    request: Request,
    body: MissingPersonReportCreateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await missing_person_report_service.create_report(
        db,
        reporter=user,
        subject_full_name=body.subject_full_name,
        subject_phone_number=body.subject_phone_number,
        relationship=body.relationship,
        notes=body.notes,
        last_known_latitude=body.last_known_latitude,
        last_known_longitude=body.last_known_longitude,
        missing_since=body.missing_since,
        missing_location_description=body.missing_location_description,
        last_known_clothing=body.last_known_clothing,
        body_marks=body.body_marks,
    )
    # Exact match already resolved synchronously above. Fuzzy/near-miss candidate
    # search runs inline for MVP simplicity (small user base); a high-volume
    # deployment would instead enqueue workers.tasks.search_missing_person_candidates.
    await matching_service.populate_candidates(db, report=report)
    await db.commit()
    await db.refresh(report)
    return await _build_report_out(db, report)


@router.get("", response_model=list[MissingPersonReportOut])
async def list_my_reports(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    reports = await missing_person_report_service.list_reports_for_reporter(db, reporter_id=user.id)
    return [await _build_report_out(db, r) for r in reports]


@router.get("/{report_id}", response_model=MissingPersonReportOut)
async def get_report(
    report_id: uuid.UUID, _: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    try:
        report = await missing_person_report_service.get_report(db, report_id=report_id)
    except missing_person_report_service.ReportNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return await _build_report_out(db, report)


@router.get("/{report_id}/candidates", response_model=list[MissingPersonMatchCandidateOut])
async def list_candidates(
    report_id: uuid.UUID, _: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await missing_person_report_service.list_candidates(db, report_id=report_id)


@router.post(
    "/{report_id}/candidates/{candidate_user_id}/confirm", response_model=MissingPersonMatchCandidateOut
)
async def confirm_candidate(
    report_id: uuid.UUID,
    candidate_user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        candidate = await missing_person_report_service.confirm_candidate(
            db, reporter=user, report_id=report_id, candidate_user_id=candidate_user_id
        )
    except missing_person_report_service.ReportNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    except missing_person_report_service.NotReportOwner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the reporter can confirm a candidate")
    except missing_person_report_service.CandidateNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    await db.commit()
    return candidate


@router.put("/{report_id}/photo", response_model=MissingPersonReportOut)
@limiter.limit("10/minute")
async def upload_report_photo(
    request: Request,
    report_id: uuid.UUID,
    file: UploadFile = File(...),
    consent_public_use: bool = Form(...),
    consent_ai_processing: bool = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Both consent flags are required (not just recorded) -- the whole point
    of a missing-person photo is that it's shown publicly to anyone searching
    for the subject and is the intended input for the future AI face-matching
    feature, so the upload is rejected outright without explicit consent to
    both, rather than silently uploading and hiding the photo later."""
    try:
        report = await missing_person_report_service.get_report(db, report_id=report_id)
    except missing_person_report_service.ReportNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    if report.reporter_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the reporter can attach a photo")

    raw_bytes = await file.read()
    try:
        await media_asset_service.upload_missing_person_photo(
            db,
            reporter_id=user.id,
            report_id=report_id,
            raw_bytes=raw_bytes,
            content_type=file.content_type or "",
            consent_public_use=consent_public_use,
            consent_ai_processing=consent_ai_processing,
        )
    except media_asset_service.ConsentRequired:
        await db.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Both public-use and AI-processing consent are required to attach a photo",
        )
    except media_asset_service.FileTooLarge:
        await db.rollback()
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Photo is too large")
    except media_asset_service.UnsupportedImageType:
        await db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "File is not a supported image (JPEG/PNG/WEBP)")
    await db.commit()
    await db.refresh(report)
    return await _build_report_out(db, report)


@router.get("/{report_id}/photo")
async def get_report_photo(
    report_id: uuid.UUID, _: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    # Intentionally not gated by relative-link/responder status, unlike the
    # profile photo -- matches missing_person_reports' existing visibility
    # (any authenticated user can already GET /{report_id}), and is exactly
    # what the "public use" consent on upload authorizes.
    result = await media_asset_service.get_missing_person_photo_bytes(db, report_id=report_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No photo attached to this report")
    photo_bytes, content_type = result
    return Response(content=photo_bytes, media_type=content_type)
