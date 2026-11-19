"""Server-side policies. Always pass the current database user and resource record.

Never construct these records from model output or untrusted upload metadata.
"""
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from fastapi import Depends, HTTPException, status

from core.security import get_current_user


class Department(str, Enum):
    ENGINEERING = "engineering"
    FINANCE = "finance"
    IT_SUPPORT = "it_support"
    SECURITY = "security"


class Role(str, Enum):
    EMPLOYEE = "employee"
    DOCUMENT_PUBLISHER = "document_publisher"
    DOCUMENT_APPROVER = "document_approver"
    SUPPORT_ANALYST = "support_analyst"
    PLATFORM_ADMINISTRATOR = "platform_administrator"
    SECURITY_REVIEWER = "security_reviewer"


class Audience(str, Enum):
    COMPANY = "company"
    DEPARTMENT = "department"
    RESTRICTED = "restricted"
    SUPPORT = "support"


@dataclass(frozen=True)
class DocumentAccess:
    owner_department: str
    audience: Audience
    status: str = "draft"
    allowed_groups: tuple[str, ...] = ()
    submitted_by: UUID | None = None


def is_account_admin(user) -> bool:
    return user.is_active and user.user_type == Role.PLATFORM_ADMINISTRATOR


async def require_account_admin(user=Depends(get_current_user)):
    if not is_account_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Account administrator permission required")
    return user


def _has_group(user, groups) -> bool:
    # permission_group is retained only for storage compatibility, not authority.
    return bool(set(user.groups or []).intersection(groups))


def can_read_document(user, document: DocumentAccess) -> bool:
    if not user.is_active or document.status != "published":
        return False
    if document.audience == Audience.COMPANY:
        return True
    if document.audience == Audience.DEPARTMENT:
        return user.department == document.owner_department
    if document.audience == Audience.RESTRICTED:
        return _has_group(user, document.allowed_groups)
    if document.audience == Audience.SUPPORT:
        return (user.user_type == Role.SUPPORT_ANALYST
                and document.owner_department in (user.support_departments or []))
    return False


def can_submit_document(user, document: DocumentAccess) -> bool:
    if not (user.is_active and user.user_type == Role.DOCUMENT_PUBLISHER
            and user.department == document.owner_department
            and document.status == "draft"):
        return False
    return _can_select_audience(user, document)


def _can_select_audience(user, document: DocumentAccess) -> bool:
    if document.audience == Audience.DEPARTMENT:
        return True
    if document.audience in (Audience.COMPANY, Audience.SUPPORT):
        return user.department == Department.IT_SUPPORT
    if document.audience == Audience.RESTRICTED:
        # A publisher/approver must hold every group they select as the audience.
        return bool(document.allowed_groups) and set(document.allowed_groups).issubset(user.groups or [])
    return False


def can_approve_document(user, document: DocumentAccess) -> bool:
    return (user.is_active and user.user_type == Role.DOCUMENT_APPROVER
            and user.department == document.owner_department
            and document.status == "review"
            and document.submitted_by is not None
            and document.submitted_by != user.id
            and _can_select_audience(user, document))


def can_read_ticket(user, *, requester_id: UUID, department: str) -> bool:
    return user.is_active and (
        user.id == requester_id
        or (user.user_type == Role.SUPPORT_ANALYST
            and department in (user.support_departments or []))
    )


def assistant_can(user, operation: str) -> bool:
    """Coarse tool allowlist; target resources still require their own checks.

    Ticket updates are deliberately excluded until field validation and
    approval bound to the exact operation are implemented.
    """
    return user.is_active and operation in {"search_documents", "read_ticket", "create_ticket"}
