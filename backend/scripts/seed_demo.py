"""Seeds a demo dataset for manual/local exploration.

Run against a migrated database (docker-compose or otherwise):

    docker compose run --rm backend python -m scripts.seed_demo

Creates accounts directly (bypassing OTP, since this is a trusted seeding
context) so the resulting phone numbers can be logged into immediately via the
normal OTP flow -- MockGateway logs the code to stdout/docker logs, or read it
from GET /api/v1/_debug/last-otp?phone=... when SMS_GATEWAY=mock.
"""

import asyncio
from datetime import UTC, date, datetime

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.enums import (
    BloodType,
    Channel,
    DistinguishableGender,
    MissingPersonReportStatus,
    PingStatus,
    RelationshipType,
    RelativeLinkStatus,
    ResponderCredentialStatus,
    UserRole,
)
from app.models.missing_person_report import MissingPersonReport
from app.models.ping import Ping
from app.models.relative_link import RelativeLink, ResponderCredential
from app.models.user import User

DEMO_USERS = [
    {
        "phone_number": "+573001110001",
        "full_name": "Camila Torres",
        "blood_type": BloodType.o_pos,
        "birth_date": date(1994, 3, 12),
        "nationality": "Colombiana",
        "residence_place": "Bogotá, Colombia",
        "distinguishable_gender": DistinguishableGender.female,
    },
    {
        "phone_number": "+573001110002",
        "full_name": "Andres Torres",
        "blood_type": BloodType.a_pos,
        "birth_date": date(1990, 7, 22),
        "nationality": "Colombiana",
        "residence_place": "Medellín, Colombia",
        "distinguishable_gender": DistinguishableGender.male,
    },
    {
        "phone_number": "+573001110003",
        "full_name": "Diego Ramirez",
        "blood_type": BloodType.b_neg,
        "birth_date": date(1985, 11, 3),
        "nationality": "Colombiana",
        "residence_place": "Cali, Colombia",
        "distinguishable_gender": DistinguishableGender.male,
        "role": UserRole.responder,
    },
]


async def get_or_create_user(db, spec: dict) -> User:
    result = await db.execute(select(User).where(User.phone_number == spec["phone_number"]))
    user = result.scalar_one_or_none()
    if user is not None:
        return user
    user = User(
        phone_number=spec["phone_number"],
        full_name=spec["full_name"],
        blood_type=spec["blood_type"],
        birth_date=spec["birth_date"],
        nationality=spec["nationality"],
        residence_place=spec["residence_place"],
        distinguishable_gender=spec["distinguishable_gender"],
        role=spec.get("role", UserRole.user),
    )
    db.add(user)
    await db.flush()
    return user


async def main() -> None:
    async with async_session_factory() as db:
        camila, andres, diego = [await get_or_create_user(db, spec) for spec in DEMO_USERS]

        existing_link = await db.execute(
            select(RelativeLink).where(
                RelativeLink.requester_user_id == camila.id, RelativeLink.target_user_id == andres.id
            )
        )
        if existing_link.scalar_one_or_none() is None:
            db.add(
                RelativeLink(
                    requester_user_id=camila.id,
                    target_user_id=andres.id,
                    relationship_label=RelationshipType.sibling,
                    status=RelativeLinkStatus.accepted,
                    responded_at=datetime.now(UTC),
                )
            )

        existing_credential = await db.execute(
            select(ResponderCredential).where(ResponderCredential.user_id == diego.id)
        )
        if existing_credential.scalar_one_or_none() is None:
            db.add(
                ResponderCredential(
                    user_id=diego.id,
                    organization_name="Cruz Roja Colombiana",
                    credential_type="red_cross",
                    status=ResponderCredentialStatus.verified,
                    verified_at=datetime.now(UTC),
                )
            )

        db.add(
            Ping(
                subject_user_id=camila.id,
                reported_by_user_id=camila.id,
                status=PingStatus.ok,
                latitude=4.6097,
                longitude=-74.0817,
                channel=Channel.web,
            )
        )
        db.add(
            Ping(
                subject_user_id=andres.id,
                reported_by_user_id=andres.id,
                status=PingStatus.distress,
                message="Building collapsed nearby, need help",
                latitude=4.6280,
                longitude=-74.0648,
                channel=Channel.sms,
            )
        )

        existing_report = await db.execute(
            select(MissingPersonReport).where(MissingPersonReport.reporter_user_id == camila.id)
        )
        if existing_report.scalar_one_or_none() is None:
            db.add(
                MissingPersonReport(
                    reporter_user_id=camila.id,
                    subject_full_name="Andres Torres",
                    subject_phone_number="+573001110002",
                    relationship=RelationshipType.sibling,
                    missing_since=date(2026, 8, 1),
                    missing_location_description="Cerca al Parque Berrío, Medellín",
                    last_known_clothing="Camisa azul, jean oscuro",
                    status=MissingPersonReportStatus.matched,
                    matched_user_id=andres.id,
                    matched_at=datetime.now(UTC),
                )
            )

        await db.commit()

    print("Seeded demo accounts:")
    for spec in DEMO_USERS:
        print(f"  {spec['phone_number']}  ({spec['full_name']})")
    print("\nLog in via POST /api/v1/auth/otp/request with any of the numbers above,")
    print("then read the code from the backend logs (MockGateway) or")
    print("GET /api/v1/_debug/last-otp?phone=<number> when SMS_GATEWAY=mock.")


if __name__ == "__main__":
    asyncio.run(main())
