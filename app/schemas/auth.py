import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.enums import UserRole


class StudentSignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)

    @model_validator(mode="after")
    def check_passwords_match(self) -> "StudentSignupRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID
    email: str
    role: UserRole
    is_first_login: bool
    onboarding_completed: bool
    committee_ids: Optional[List[uuid.UUID]] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class StudentProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    branch: str
    section: str
    phone_number: str
    academic_year: str
    cgpa: Optional[float] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    instagram_url: Optional[str] = None
    profile_photo_url: Optional[str] = None
    onboarding_completed: bool

    class Config:
        from_attributes = True


class AdminProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    designation: str
    profile_photo_url: Optional[str] = None

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole
    is_first_login: bool
    onboarding_completed: bool
    profile: Optional[Dict[str, Any]] = None
    committee_ids: Optional[List[uuid.UUID]] = None

    class Config:
        from_attributes = True


class OnboardingStudentRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    branch: str = Field(..., min_length=1)
    section: str = Field(..., min_length=1)
    phone_number: str = Field(..., min_length=7)
    academic_year: str = Field(..., min_length=1)
    cgpa: Optional[float] = Field(None, ge=0.0, le=10.0)
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    instagram_url: Optional[str] = None
    profile_photo_url: Optional[str] = None

    @model_validator(mode="after")
    def clean_and_format(self) -> "OnboardingStudentRequest":
        if self.phone_number:
            digits = "".join(filter(str.isdigit, self.phone_number))
            if len(digits) == 10:
                self.phone_number = f"+91{digits}"
            elif len(digits) == 12 and digits.startswith("91"):
                self.phone_number = f"+{digits}"
            elif digits:
                self.phone_number = f"+{digits}" if not self.phone_number.startswith("+") else self.phone_number
        return self
