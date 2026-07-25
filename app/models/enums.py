from enum import Enum


class UserRole(str, Enum):
    STUDENT = "student"
    ADMIN = "admin"
    COMMITTEE = "committee"


class CommitteeCategory(str, Enum):
    FACULTY = "faculty"
    STUDENT = "student"


class CommitteeSubCategory(str, Enum):
    CSM = "CSM"
    CSD = "CSD"
    CODING = "coding"
    SPORTS = "sports"
    NON_TECHNICAL = "non_technical"


class EventCategory(str, Enum):
    UPCOMING = "upcoming"
    CURRENT = "current"
    PAST = "past"


class RegistrationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class CertificateType(str, Enum):
    PARTICIPATION = "participation"
    WINNER = "winner"
    RUNNER_UP = "runner_up"


class AchievementPosition(str, Enum):
    WINNER = "winner"
    RUNNER_UP = "runner_up"
    SPECIAL_MENTION = "special_mention"


class OpportunityType(str, Enum):
    INTERNSHIP = "internship"
    JOB = "job"
    HACKATHON = "hackathon"
    SCHOLARSHIP = "scholarship"


class MediaItemType(str, Enum):
    NEWSLETTER = "newsletter"
    MAGAZINE = "magazine"


class GrievanceStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class GrievanceCategory(str, Enum):
    EVENT = "event"
    COMMITTEE = "committee"
    FACILITY = "facility"
    OTHER = "other"
