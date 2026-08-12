import jwt
from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.core.config import get_settings
from app.core.database import engine
from app.core.security import decode_access_token
from app.models.enums import UserRole
from app.models.missing_person_report import (
    MissingPersonMatchCandidate,
    MissingPersonReport,
)
from app.models.ping import Ping, Pong
from app.models.relative_link import RelativeLink, ResponderCredential
from app.models.user import User

settings = get_settings()


class AdminAuth(AuthenticationBackend):
    """Bearer-token gate reusing the same JWT issued by /auth/otp/verify --
    SQLAdmin has no notion of our OTP login flow, so this just checks for a
    valid access token belonging to an admin user on every request."""

    async def login(self, request: Request) -> bool:
        form = await request.form()
        token = form.get("token")
        if not token:
            return False
        try:
            payload = decode_access_token(str(token))
        except jwt.PyJWTError:
            return False
        if payload.get("role") != UserRole.admin.value:
            return False
        request.session.update({"token": str(token)})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")
        if not token:
            return False
        try:
            payload = decode_access_token(token)
        except jwt.PyJWTError:
            return False
        return payload.get("role") == UserRole.admin.value


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.phone_number, User.full_name, User.role, User.status, User.created_at]
    column_searchable_list = [User.phone_number, User.full_name]
    can_create = False
    can_delete = False


class ResponderCredentialAdmin(ModelView, model=ResponderCredential):
    name = "Responder Credential"
    column_list = [
        ResponderCredential.id,
        ResponderCredential.user_id,
        ResponderCredential.organization_name,
        ResponderCredential.credential_type,
        ResponderCredential.status,
        ResponderCredential.verified_at,
    ]
    can_create = False


class RelativeLinkAdmin(ModelView, model=RelativeLink):
    column_list = [
        RelativeLink.id,
        RelativeLink.requester_user_id,
        RelativeLink.target_user_id,
        RelativeLink.status,
        RelativeLink.requested_at,
    ]
    can_create = False
    can_edit = False
    can_delete = False


class PingAdmin(ModelView, model=Ping):
    column_list = [
        Ping.id,
        Ping.subject_user_id,
        Ping.reported_by_user_id,
        Ping.is_proxy,
        Ping.status,
        Ping.channel,
        Ping.created_at,
    ]
    can_create = False
    can_edit = False
    can_delete = False


class PongAdmin(ModelView, model=Pong):
    column_list = [Pong.id, Pong.ping_id, Pong.responder_user_id, Pong.audience, Pong.created_at]
    can_create = False
    can_edit = False
    can_delete = False


class MissingPersonReportAdmin(ModelView, model=MissingPersonReport):
    name = "Missing Person Report"
    column_list = [
        MissingPersonReport.id,
        MissingPersonReport.reporter_user_id,
        MissingPersonReport.subject_full_name,
        MissingPersonReport.subject_phone_number,
        MissingPersonReport.status,
        MissingPersonReport.matched_user_id,
    ]
    can_create = False
    can_delete = False


class MissingPersonMatchCandidateAdmin(ModelView, model=MissingPersonMatchCandidate):
    name = "Match Candidate"
    column_list = [
        MissingPersonMatchCandidate.id,
        MissingPersonMatchCandidate.report_id,
        MissingPersonMatchCandidate.candidate_user_id,
        MissingPersonMatchCandidate.combined_score,
        MissingPersonMatchCandidate.confirmed,
    ]
    can_create = False
    can_edit = False
    can_delete = False


def register_admin(app: FastAPI) -> None:
    admin = Admin(app, engine, authentication_backend=AdminAuth(secret_key=settings.admin_session_secret))
    admin.add_view(UserAdmin)
    admin.add_view(ResponderCredentialAdmin)
    admin.add_view(RelativeLinkAdmin)
    admin.add_view(PingAdmin)
    admin.add_view(PongAdmin)
    admin.add_view(MissingPersonReportAdmin)
    admin.add_view(MissingPersonMatchCandidateAdmin)
