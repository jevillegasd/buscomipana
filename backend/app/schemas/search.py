import uuid

from pydantic import BaseModel


class PersonSearchResultOut(BaseModel):
    user_id: uuid.UUID
    phone_similarity_score: float
    name_similarity_score: float
    combined_score: float
