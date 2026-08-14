from pydantic import BaseModel, Field

from app.schemas.common import EmailAddress, PhoneNumber


class OtpRequestIn(BaseModel):
    """Public signup/login OTP request. purpose is always signup_or_login here --
    phone-number-change OTPs go through the separate authenticated
    /auth/phone-number/change/request endpoint so an unauthenticated caller can
    never trigger a phone_change OTP for someone else's account."""

    phone_number: PhoneNumber
    # Chooses the delivery *channel* only -- never an address. When true, the
    # code goes to whatever email is already stored+verified on this
    # phone_number's account (see auth_service.request_login_otp); there is
    # deliberately no field here to specify an arbitrary address (Issue #10:
    # that was an account-takeover hole -- see auth.py's request_otp route).
    use_email: bool = False


class OtpVerifyIn(BaseModel):
    phone_number: PhoneNumber
    code: str = Field(min_length=4, max_length=8)


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_new_account: bool = False


class RefreshIn(BaseModel):
    # Optional because browser clients don't hold the refresh token in JS at all
    # -- it lives only in the HttpOnly cookie, which the server reads directly.
    refresh_token: str | None = None


class PhoneNumberChangeRequestIn(BaseModel):
    new_phone_number: PhoneNumber


class PhoneNumberChangeConfirmIn(BaseModel):
    new_phone_number: PhoneNumber
    code: str = Field(min_length=4, max_length=8)


class EmailChangeRequestIn(BaseModel):
    new_email: EmailAddress


class EmailChangeConfirmIn(BaseModel):
    new_email: EmailAddress
    code: str = Field(min_length=4, max_length=8)
