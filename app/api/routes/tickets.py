from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.crud.tickets import create_ticket, get_ticket, get_tickets, update_ticket
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User
from app.schemas.ticket import TicketCreate, TicketResponse, TicketUpdate

router = APIRouter()


def _get_user_or_none(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def _validate_ticket_users(db: Session, requester_id: int | None, assignee_id: int | None) -> None:
    if requester_id is not None and _get_user_or_none(db, requester_id) is None:
        raise AppError("Requester not found.", status.HTTP_404_NOT_FOUND)

    if assignee_id is not None and _get_user_or_none(db, assignee_id) is None:
        raise AppError("Assignee not found.", status.HTTP_404_NOT_FOUND)


@router.post(
    "/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create ticket",
)
def create_ticket_endpoint(
    ticket_in: TicketCreate,
    db: Session = Depends(get_db),
) -> TicketResponse:
    _validate_ticket_users(db, ticket_in.requester_id, ticket_in.assignee_id)
    return create_ticket(db, ticket_in)


@router.get(
    "/tickets",
    response_model=list[TicketResponse],
    summary="List tickets",
)
def list_tickets_endpoint(db: Session = Depends(get_db)) -> list[TicketResponse]:
    return get_tickets(db)


@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketResponse,
    summary="Get ticket",
)
def get_ticket_endpoint(
    ticket_id: int,
    db: Session = Depends(get_db),
) -> TicketResponse:
    ticket = get_ticket(db, ticket_id)

    if ticket is None:
        raise AppError("Ticket not found.", status.HTTP_404_NOT_FOUND)

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
) -> TicketResponse:
    ticket = get_ticket(db, ticket_id)

    if ticket is None:
        raise AppError("Ticket not found.", status.HTTP_404_NOT_FOUND)

    _validate_ticket_users(db, ticket_in.requester_id, ticket_in.assignee_id)
    return update_ticket(db, ticket, ticket_in)
