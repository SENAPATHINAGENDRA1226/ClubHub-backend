from app.schemas.common import ErrorResponse, MessageResponse
from app.schemas.auth import (
    StudentSignupRequest,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    StudentProfileResponse,
    AdminProfileResponse,
    UserResponse,
    OnboardingStudentRequest,
)
from app.schemas.events import (
    EventCreate,
    EventUpdate,
    EventResponse,
    PaginatedEventsResponse,
)
from app.schemas.registrations import (
    RegistrationCreate,
    RegistrationResponse,
    PaginatedRegistrationsResponse,
)
from app.schemas.certificates import (
    CertificateCreate,
    CertificateResponse,
    PaginatedCertificatesResponse,
)

__all__ = [
    "ErrorResponse",
    "MessageResponse",
    "StudentSignupRequest",
    "LoginRequest",
    "TokenResponse",
    "RefreshTokenRequest",
    "StudentProfileResponse",
    "AdminProfileResponse",
    "UserResponse",
    "OnboardingStudentRequest",
    "EventCreate",
    "EventUpdate",
    "EventResponse",
    "PaginatedEventsResponse",
    "RegistrationCreate",
    "RegistrationResponse",
    "PaginatedRegistrationsResponse",
    "CertificateCreate",
    "CertificateResponse",
    "PaginatedCertificatesResponse",
]
