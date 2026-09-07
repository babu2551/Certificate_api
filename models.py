from pydantic import BaseModel, EmailStr, Field


class RegistrationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    course: str = Field(..., min_length=1, max_length=100)
    event: str = Field(..., min_length=1, max_length=150)
    rank: str = Field(default="Participant", min_length=1, max_length=30)


class VerificationRequest(BaseModel):
    email: EmailStr
    event: str = Field(..., min_length=1, max_length=150)


class RegistrationResponse(BaseModel):
    message: str
    registration_id: str


class VerificationResponse(BaseModel):
    eligible: bool
    name: str | None = None
    course: str | None = None
    rank: str | None = None
    message: str
