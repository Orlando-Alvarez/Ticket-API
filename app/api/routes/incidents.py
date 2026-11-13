from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import get_current_user
from app.crud.incidents import (
    create_incident,
    get_incident,
    get_incidents,
    update_incident,
)
from app.db.session import get_db
from app.models.incident import Incident
from app.models.user import User
from app.schemas.incident import (
    IncidentCreate,
    IncidentListResponse,
    IncidentResponse,
    IncidentSeverity,
    IncidentStatus,
    IncidentUpdate,
)

router = APIRouter()


def _is_admin(user: User) -> bool:
    return user.role == "admin"


def _require_incident_access(user: User, incident: Incident) -> None:
    if not _is_admin(user) and incident.reported_by_id != user.id:
        raise AppError(
            "Incident not found.",
            status.HTTP_404_NOT_FOUND,
        )


@router.post(
    "/incidents",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create incident",
)
def create_incident_endpoint(
    incident_in: IncidentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IncidentResponse:
    return create_incident(db, incident_in, current_user.id)


@router.get(
    "/incidents",
    response_model=IncidentListResponse,
    summary="List incidents",
)
def list_incidents_endpoint(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    incident_status: Annotated[IncidentStatus | None, Query(alias="status")] = None,
    severity: IncidentSeverity | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IncidentListResponse:
    reporter_scope_id = None if _is_admin(current_user) else current_user.id
    incidents, total = get_incidents(
        db,
        offset=offset,
        limit=limit,
        status=incident_status,
        severity=severity,
        reporter_scope_id=reporter_scope_id,
    )
    return IncidentListResponse(
        items=incidents,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/incidents/{incident_id}",
    response_model=IncidentResponse,
    summary="Get incident",
)
def get_incident_endpoint(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IncidentResponse:
    incident = get_incident(db, incident_id)
    if incident is None:
        raise AppError("Incident not found.", status.HTTP_404_NOT_FOUND)

    _require_incident_access(current_user, incident)
    return incident


@router.patch(
    "/incidents/{incident_id}",
    response_model=IncidentResponse,
    summary="Update incident",
)
def update_incident_endpoint(
    incident_id: int,
    incident_in: IncidentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IncidentResponse:
    incident = get_incident(db, incident_id)
    if incident is None:
        raise AppError("Incident not found.", status.HTTP_404_NOT_FOUND)

    _require_incident_access(current_user, incident)

    if not _is_admin(current_user) and "status" in incident_in.model_fields_set:
        raise AppError(
            "Only admins can change incident status.",
            status.HTTP_403_FORBIDDEN,
        )

    return update_incident(db, incident, incident_in)
