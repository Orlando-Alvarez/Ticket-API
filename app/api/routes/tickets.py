"""Ticket authorization policy.

The project did not define ticket permissions, so these routes use a
least-privilege policy: non-admin users create only for themselves without an
initial assignment; they can read and update ordinary fields only on tickets
they requested or are assigned to. Only admins can change requester or
assignee relationships. Assignee access is based on the assignee_id relation,
not solely on the user's global role.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import get_current_user
from app.crud.tickets import (
    create_ticket,
    get_ticket,
    get_tickets,
    get_tickets_for_user,
    update_ticket,
)
from app.db.session import get_db
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.ticket import TicketCreate, TicketResponse, TicketUpdate


router = APIRouter()


def _get_user_or_none(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def _validate_ticket_users(
    db: Session,
    requester_id: int | None,
    assignee_id: int | None,
) -> None:
    if requester_id is not None and _get_user_or_none(db, requester_id) is None:
        raise AppError("Requester not found.", status.HTTP_404_NOT_FOUND)

    if assignee_id is not None and _get_user_or_none(db, assignee_id) is None:
        raise AppError("Assignee not found.", status.HTTP_404_NOT_FOUND)


def _is_admin(user: User) -> bool:
    return user.role == "admin"


def _can_access_ticket(user: User, ticket: Ticket) -> bool:
    return (
        _is_admin(user)
        or ticket.requester_id == user.id
        or ticket.assignee_id == user.id
    )


def _require_ticket_access(user: User, ticket: Ticket) -> None:
    if not _can_access_ticket(user, ticket):
        raise AppError(
            "You are not authorized to access this ticket.",
            status.HTTP_403_FORBIDDEN,
        )


@router.post(
    "/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create ticket",
)
def create_ticket_endpoint(
    ticket_in: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TicketResponse:
    if not _is_admin(current_user):
        if ticket_in.requester_id != current_user.id:
            raise AppError(
                "You can only create tickets for yourself.",
                status.HTTP_403_FORBIDDEN,
            )
        if ticket_in.assignee_id is not None:
            raise AppError(
                "Only admins can assign tickets during creation.",
                status.HTTP_403_FORBIDDEN,
            )

    _validate_ticket_users(db, ticket_in.requester_id, ticket_in.assignee_id)
    return create_ticket(db, ticket_in)


@router.get(
    "/tickets",
    response_model=list[TicketResponse],
    summary="List tickets",
)
def list_tickets_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TicketResponse]:
    if _is_admin(current_user):
        return get_tickets(db)
    return get_tickets_for_user(db, current_user.id)


@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketResponse,
    summary="Get ticket",
)
def get_ticket_endpoint(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TicketResponse:
    ticket = get_ticket(db, ticket_id)
    if ticket is None:
        raise AppError("Ticket not found.", status.HTTP_404_NOT_FOUND)

    _require_ticket_access(current_user, ticket)
    return ticket


@router.patch(
    "/tickets/{ticket_id}",
    response_model=TicketResponse,
    summary="Update ticket",
)
def update_ticket_endpoint(
    ticket_id: int,
    ticket_in: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TicketResponse:
    ticket = get_ticket(db, ticket_id)
    if ticket is None:
        raise AppError("Ticket not found.", status.HTTP_404_NOT_FOUND)

    _require_ticket_access(current_user, ticket)

    relationship_fields = {"requester_id", "assignee_id"}
    if not _is_admin(current_user) and ticket_in.model_fields_set & relationship_fields:
        raise AppError(
            "Only admins can change ticket ownership or assignment.",
            status.HTTP_403_FORBIDDEN,
        )

    _validate_ticket_users(db, ticket_in.requester_id, ticket_in.assignee_id)
    return update_ticket(db, ticket, ticket_in)
