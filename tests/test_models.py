from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.incident import Incident
from app.models.user import User


def test_database_models_are_registered():
    expected_tables = {"users", "tickets", "incidents"}

    assert expected_tables.issubset(Base.metadata.tables.keys())

def test_incident_defaults_and_reporter(db_session: Session) -> None:
    reporter = User(email="reporter@example.com", full_name="Reporter", hashed_password="test-hash")
    incident = Incident(title="Service unavailable", reporter=reporter)
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    assert incident.reported_by_id == reporter.id
    assert incident in reporter.reported_incidents
    assert incident.status == "open"
    assert incident.severity == "medium"
    assert incident.description is None
    assert incident.created_at is not None


def test_incident_table_has_constraints_defaults_and_listing_index() -> None:
    table = Base.metadata.tables["incidents"]
    constraint_names = {constraint.name for constraint in table.constraints}
    index_names = {index.name for index in table.indexes}

    assert "ck_incidents_severity" in constraint_names
    assert "ck_incidents_status" in constraint_names
    assert "ix_incidents_reported_by_created_id" in index_names
    assert table.c.severity.server_default is not None
    assert table.c.status.server_default is not None
