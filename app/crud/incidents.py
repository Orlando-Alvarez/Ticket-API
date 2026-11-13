from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.schemas.incident import (
    IncidentCreate,
    IncidentSeverity,
    IncidentStatus,
    IncidentUpdate,
)


def create_incident(
    db: Session,
    incident_in: IncidentCreate,
    reported_by_id: int,
) -> Incident:
    incident = Incident(
        **incident_in.model_dump(),
        reported_by_id=reported_by_id,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def get_incident(db: Session, incident_id: int) -> Incident | None:
    statement = select(Incident).where(
        Incident.id == incident_id,
        Incident.deleted_at.is_(None),
    )

    return db.scalar(statement)


def get_incidents(
    db: Session,
    *,
    offset: int,
    limit: int,
    status: IncidentStatus | None = None,
    severity: IncidentSeverity | None = None,
    reporter_scope_id: int | None = None,
) -> tuple[list[Incident], int]:
    filters = [Incident.deleted_at.is_(None)]
    if status is not None:
        filters.append(Incident.status == status)
    if severity is not None:
        filters.append(Incident.severity == severity)
    if reporter_scope_id is not None:
        filters.append(Incident.reported_by_id == reporter_scope_id)

    total_statement = select(func.count()).select_from(Incident).where(*filters)
    total = int(db.scalar(total_statement) or 0)

    statement = (
        select(Incident)
        .where(*filters)
        .order_by(Incident.created_at.desc(), Incident.id.desc())
        .offset(offset)
        .limit(limit)
    )
    incidents = list(db.scalars(statement).all())
    return incidents, total


def update_incident(
    db: Session,
    incident: Incident,
    incident_in: IncidentUpdate,
) -> Incident:
    update_data = incident_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(incident, field, value)

    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def soft_delete_incident(
    db: Session,
    incident_id: int,
    deleted_by_id: int,
) -> bool:
    statement = (
        update(Incident)
        .where(
            Incident.id == incident_id,
            Incident.deleted_at.is_(None),
        )
        .values(
            deleted_at=datetime.now(UTC),
            deleted_by_id=deleted_by_id,
        )
    )
    result = db.execute(statement)
    db.commit()
    return result.rowcount == 1
