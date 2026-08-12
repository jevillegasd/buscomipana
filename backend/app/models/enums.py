import enum


class UserRole(str, enum.Enum):
    user = "user"
    responder = "responder"
    admin = "admin"


class UserStatus(str, enum.Enum):
    active = "active"
    deactivated = "deactivated"


class BloodType(str, enum.Enum):
    a_pos = "A+"
    a_neg = "A-"
    b_pos = "B+"
    b_neg = "B-"
    ab_pos = "AB+"
    ab_neg = "AB-"
    o_pos = "O+"
    o_neg = "O-"


class DistinguishableGender(str, enum.Enum):
    """Presentation-based, not a legal/registry fact -- this is what a
    rescuer sees and can use to identify someone in the field, so the
    options describe how a person presents rather than sex at birth."""

    male = "male"
    female = "female"
    other = "other"
    prefer_not_to_say = "prefer_not_to_say"


class MediaAssetPurpose(str, enum.Enum):
    profile_photo = "profile_photo"
    missing_person_photo = "missing_person_photo"


class MediaStorageBackend(str, enum.Enum):
    local = "local"
    s3 = "s3"


class OtpPurpose(str, enum.Enum):
    signup_or_login = "signup_or_login"
    phone_change = "phone_change"


class Channel(str, enum.Enum):
    web = "web"
    sms = "sms"
    ivr_call = "ivr_call"
    ussd = "ussd"


class RelationshipType(str, enum.Enum):
    """Closed vocabulary instead of free text on purpose: relative_links and
    missing_person_reports both store this, and a fixed literal set is what
    lets future features (family-graph traversal, responder triage, filtering)
    key off it directly instead of parsing arbitrary strings. The frontend
    localizes these to Spanish for display; the wire values stay English."""

    parent = "parent"
    child = "child"
    sibling = "sibling"
    spouse = "spouse"
    grandparent = "grandparent"
    grandchild = "grandchild"
    aunt_or_uncle = "aunt_or_uncle"
    niece_or_nephew = "niece_or_nephew"
    cousin = "cousin"
    guardian = "guardian"
    friend = "friend"
    other = "other"


class RelativeLinkStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    revoked = "revoked"


class ResponderCredentialStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    revoked = "revoked"


class PingStatus(str, enum.Enum):
    ok = "ok"
    distress = "distress"
    unknown = "unknown"


class PongAudience(str, enum.Enum):
    directed = "directed"
    broadcast = "broadcast"


class MissingPersonReportStatus(str, enum.Enum):
    open = "open"
    matched = "matched"
    closed = "closed"


class SmsIntent(str, enum.Enum):
    ping_ok = "ping_ok"
    ping_sos = "ping_sos"
    pong = "pong"
    unrecognized = "unrecognized"


class SmsOutboxPurpose(str, enum.Enum):
    otp = "otp"
    ping_notification = "ping_notification"
    pong_notification = "pong_notification"
    missing_person_match = "missing_person_match"


class SmsOutboxStatus(str, enum.Enum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"
