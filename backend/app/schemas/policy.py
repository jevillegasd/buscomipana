from datetime import datetime

from pydantic import BaseModel


class PolicyOut(BaseModel):
    country: str
    version: str
    title: str
    content: str


class PolicyAcceptanceOut(BaseModel):
    country: str
    version: str
    accepted_at: datetime


class TermsOut(BaseModel):
    version: str
    title: str
    content: str
