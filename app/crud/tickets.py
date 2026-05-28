from sqlalchemy import select
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
    return db.get(Ticket, ticket_id)


def get_tickets(db: Session) -> list[Ticket]:
    return list(db.scalars(select(Ticket)).all())


def update_ticket(db: Session, ticket: Ticket, ticket_in: TicketUpdate) -> Ticket:
    update_data = ticket_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(ticket, field, value)

    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket
