# Ticket-API

Ticket-API is a backend API for a portfolio-oriented ticketing and incident management system. It is designed to demonstrate practical backend, database, testing, containerization, and cloud-readiness skills for junior backend, cloud, and platform engineering roles.

The project is built with **FastAPI**, **SQLAlchemy**, **PostgreSQL**, **Alembic**, **Docker Compose**, **pytest**, and **GitHub Actions CI**.

## Overview

Ticket-API provides a clean backend foundation for managing users, tickets, and incidents.

Current functionality includes:

- Versioned FastAPI routes under `/api/v1`
- Health check endpoint
- Basic error handling
- SQLAlchemy domain models
- PostgreSQL-ready database configuration
- Alembic database migrations
- Docker-based local development with PostgreSQL
- Basic User CRUD endpoints
- Basic Ticket CRUD endpoints
- Automated tests with `pytest`
- GitHub Actions CI workflow

## Project Goals

This project is being built to demonstrate practical backend and cloud-readiness skills, including:

- Python backend development with FastAPI
- Clean API structure and versioned routing
- Request and response validation with Pydantic
- SQLAlchemy ORM models and relationships
- PostgreSQL persistence readiness
- Alembic database schema migrations
- Docker and Docker Compose local development
- Automated testing with `pytest`
- Continuous Integration with GitHub Actions
- Clear documentation and professional Git workflow
- Preparation for future cloud deployment

## Tech Stack

- **Python**: main programming language
- **FastAPI**: backend API framework
- **Uvicorn**: ASGI server for running FastAPI
- **Pydantic / pydantic-settings**: data validation and application configuration
- **SQLAlchemy**: ORM for database models and sessions
- **PostgreSQL**: relational database
- **psycopg**: PostgreSQL driver
- **Alembic**: database migrations
- **Docker**: containerized application runtime
- **Docker Compose**: local API + database orchestration
- **pytest**: automated testing
- **httpx / TestClient**: API endpoint testing
- **GitHub Actions**: CI workflow

## Requirements

For local development:

- Python 3.11+
- `pip`

For Docker-based local development:

- Docker
- Docker Compose

## Local Installation

Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install the project locally:

```bash
pip install -e .
```

Install testing dependencies if needed:

```bash
pip install pytest httpx
```

## Run the API Locally

```bash
uvicorn app.main:app --reload
```

The API will be available at:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`
- `http://127.0.0.1:8000/api/v1/health`

## Run With Docker

Build and start the FastAPI and PostgreSQL containers:

```bash
docker compose up --build
```

The API will be available at:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`
- `http://127.0.0.1:8000/api/v1/health`

The PostgreSQL container is exposed locally on port `5432`.

Stop the containers:

```bash
docker compose down
```

Stop the containers and remove the local PostgreSQL volume:

```bash
docker compose down -v
```

Docker Compose passes this database URL to the API container:

```text
postgresql+psycopg://ticket_user:ticket_password@db:5432/ticket_api
```

The application does **not** create tables automatically. Use Alembic to apply database migrations.

## Database Migrations

Start the PostgreSQL container:

```bash
docker compose up -d db
```

Apply migrations:

```bash
.venv\Scripts\alembic.exe upgrade head
```

Alternative:

```bash
python -m alembic upgrade head
```

Create a new migration after changing SQLAlchemy models:

```bash
.venv\Scripts\alembic.exe revision --autogenerate -m "describe change"
```

Alembic reads `DATABASE_URL` from the application settings.

Use this host depending on where the command runs:

- From Windows/local terminal: `localhost`
- From inside Docker Compose: `db`

To inspect tables:

```bash
docker compose exec db psql -U ticket_user -d ticket_api -c "\dt"
```

Expected tables after migrations:

```text
users
tickets
incidents
alembic_version
```

## Available Endpoints

### Health

#### `GET /api/v1/health`

Expected response:

```json
{
  "status": "ok",
  "service": "ticket-api",
  "version": "0.1.0"
}
```

This endpoint verifies that the API is running correctly.

---

### Users

#### `POST /api/v1/users`

Creates a user.

Example request:

```json
{
  "email": "requester@example.com",
  "full_name": "Test Requester",
  "hashed_password": "fake-hash",
  "role": "requester",
  "is_active": true
}
```

Example response:

```json
{
  "id": 1,
  "email": "requester@example.com",
  "full_name": "Test Requester",
  "role": "requester",
  "is_active": true,
  "created_at": "2026-05-28T20:00:00"
}
```

`hashed_password` is accepted only because authentication and real password hashing are not implemented yet. It is **not** returned in API responses.

#### `GET /api/v1/users`

Returns all users.

#### `GET /api/v1/users/{user_id}`

Returns a user by ID.

If the user does not exist, the API returns:

```json
{
  "error": {
    "message": "User not found."
  }
}
```

#### `PATCH /api/v1/users/{user_id}`

Partially updates a user.

Example request:

```json
{
  "role": "agent"
}
```

If an email already belongs to another user, the API returns HTTP `409 Conflict`:

```json
{
  "error": {
    "message": "Email already exists."
  }
}
```

---

### Tickets

#### `POST /api/v1/tickets`

Creates a ticket.

A valid `requester_id` is required. `assignee_id` is optional, but if provided it must reference an existing user.

Example request:

```json
{
  "title": "Cannot access dashboard",
  "description": "The dashboard returns an error after login.",
  "priority": "high",
  "requester_id": 1,
  "assignee_id": 2
}
```

Example response:

```json
{
  "id": 1,
  "title": "Cannot access dashboard",
  "description": "The dashboard returns an error after login.",
  "status": "open",
  "priority": "high",
  "requester_id": 1,
  "assignee_id": 2,
  "created_at": "2026-05-28T20:00:00",
  "updated_at": null
}
```

If the requester does not exist:

```json
{
  "error": {
    "message": "Requester not found."
  }
}
```

If the assignee does not exist:

```json
{
  "error": {
    "message": "Assignee not found."
  }
}
```

#### `GET /api/v1/tickets`

Returns all tickets.

#### `GET /api/v1/tickets/{ticket_id}`

Returns a ticket by ID.

If the ticket does not exist:

```json
{
  "error": {
    "message": "Ticket not found."
  }
}
```

#### `PATCH /api/v1/tickets/{ticket_id}`

Partially updates a ticket.

Example request:

```json
{
  "status": "in_progress",
  "assignee_id": 2
}
```

## Manual Testing Flow With Swagger

After starting the API and applying migrations:

1. Open Swagger:
   - `http://127.0.0.1:8000/docs`
2. Create a requester:
   - `POST /api/v1/users`
3. Create an agent:
   - `POST /api/v1/users`
4. Create a ticket using the requester ID:
   - `POST /api/v1/tickets`
5. Assign or update the ticket using the agent ID:
   - `PATCH /api/v1/tickets/{ticket_id}`
6. List tickets:
   - `GET /api/v1/tickets`

## Testing

The project includes automated tests using `pytest`.

Run the tests locally:

```bash
.venv\Scripts\python.exe -m pytest
```

Alternative:

```bash
python -m pytest
```

Current test coverage includes:

- Health endpoint behavior
- SQLAlchemy model metadata registration
- PostgreSQL database URL configuration
- Basic Ticket CRUD behavior
- Ticket error handling for missing tickets, requester, and assignee
- Basic User CRUD behavior
- User error handling for missing users and duplicate emails
- Ensuring `hashed_password` is not exposed in user responses

Current test files:

```text
tests/test_health.py
tests/test_models.py
tests/test_database_config.py
tests/test_tickets.py
tests/test_users.py
```

Current expected result:

```text
18 passed
```

## Continuous Integration

The project includes a GitHub Actions CI workflow located at:

```text
.github/workflows/ci.yml
```

The workflow runs automatically on:

- Pushes to `main`
- Pushes to branches matching `feat/**`
- Pull requests targeting `main`

The CI pipeline performs the following steps:

1. Checks out the repository.
2. Sets up Python.
3. Upgrades `pip`.
4. Installs the project and test dependencies.
5. Runs the test suite with `pytest`.

This helps verify that the project continues to work after each change.

## Current Project Structure

```text
app/
  api/
    routes/
      health.py
      tickets.py
      users.py
    router.py
  core/
    config.py
    errors.py
  crud/
    tickets.py
    users.py
  db/
    base.py
    session.py
  models/
    incident.py
    ticket.py
    user.py
  schemas/
    health.py
    ticket.py
    user.py
  main.py

alembic/
  env.py
  script.py.mako
  versions/
    20260523_0001_create_initial_tables.py

tests/
  test_database_config.py
  test_health.py
  test_models.py
  test_tickets.py
  test_users.py

.github/
  workflows/
    ci.yml

Dockerfile
docker-compose.yml
alembic.ini
pyproject.toml
README.md
```

## Error Handling Included

The API includes consistent JSON error handling for:

- `404 Not Found`
- `409 Conflict`
- `422 Validation Error`
- `500 Internal Server Error`

Example:

```json
{
  "error": {
    "message": "Ticket not found."
  }
}
```

## Current Status

Completed:

- FastAPI project skeleton
- Versioned API routing
- Health check endpoint
- Basic error handling
- Automated testing with `pytest`
- GitHub Actions CI workflow
- SQLAlchemy domain models
- PostgreSQL database configuration
- SQLAlchemy engine and session setup
- Dockerfile and Docker Compose local development setup
- Alembic migration setup
- Initial database migration for users, tickets, and incidents
- Basic Ticket CRUD endpoints
- Basic User CRUD endpoints

## Current Limitations

The project intentionally does **not** include these features yet:

- Authentication
- Login endpoint
- JWT access tokens
- Password hashing
- Role-based authorization
- DELETE endpoints
- Pagination
- Filtering
- Incident CRUD endpoints
- Cloud deployment configuration

## Next Phase

Recommended next phase:

- Add basic Incident CRUD endpoints.

Future phases may include:

- Password hashing and authentication
- JWT-based login
- Role-based authorization
- Pagination and filtering
- DELETE behavior
- CI/CD improvements
- Cloud deployment
