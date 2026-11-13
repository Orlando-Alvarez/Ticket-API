from datetime import UTC, datetime

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.models.ticket import Ticket
from app.schemas.ticket import TicketCreate, TicketUpdate


def create_ticket(db: Session, ticket_in: TicketCreate) -> Ticket:
    ticket = Ticket(**ticket_in.model_dump())
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def get_ticket(db: Session, ticket_id: int) -> Ticket | None:
    statement = select(Ticket).where(
        Ticket.id == ticket_id,
        Ticket.deleted_at.is_(None),
    )
    return db.scalar(statement)


def get_tickets(db: Session) -> list[Ticket]:
    statement = select(Ticket).where(Ticket.deleted_at.is_(None))
    return list(db.scalars(statement).all())


def get_tickets_for_user(db: Session, user_id: int) -> list[Ticket]:
    statement = select(Ticket).where(
        Ticket.deleted_at.is_(None),
        or_(
            Ticket.requester_id == user_id,
            Ticket.assignee_id == user_id,
        )
    )
    return list(db.scalars(statement).all())


def update_ticket(db: Session, ticket: Ticket, ticket_in: TicketUpdate) -> Ticket:
    update_data = ticket_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(ticket, field, value)

    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def soft_delete_ticket(db: Session, ticket_id: int, deleted_by_id: int) -> bool:
    statement = (
        update(Ticket)
        .where(
            Ticket.id == ticket_id,
            Ticket.deleted_at.is_(None),
        )
        .values(
            deleted_at=datetime.now(UTC),
            deleted_by_id=deleted_by_id,
        )
    )
    result = db.execute(statement)
    db.commit()
    return result.rowcount == 1
