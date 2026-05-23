# Ticket-API

Ticket-API is a backend API for a portfolio-oriented ticketing and incident management system. It is designed for junior backend, cloud, and platform engineering roles.

This project provides a clean FastAPI foundation with versioned routes, a health check endpoint, basic error handling, automated testing with `pytest`, SQLAlchemy models, Alembic migrations, PostgreSQL-ready configuration, Docker-based local development, and a GitHub Actions CI workflow.

## Project Goals

This project is being built to demonstrate practical backend and cloud-readiness skills, including:

- Python backend development with FastAPI
- Clean API structure and versioned routing
- Basic service health checks
- Consistent error handling
- Automated testing with `pytest`
- Continuous Integration with GitHub Actions
- PostgreSQL persistence readiness with SQLAlchemy
- Database migrations with Alembic
- Docker-based local development
- Preparation for future cloud deployment

## Requirements

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

For testing, install the testing dependencies:

```bash
pip install pytest httpx
```

## Run the API

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

The application does not create tables automatically. Use Alembic to apply database migrations.

## Database Migrations

Start the PostgreSQL container:

```bash
docker compose up -d db
```

Apply migrations:

```bash
.venv\Scripts\alembic.exe upgrade head
```

Create a new migration after changing SQLAlchemy models:

```bash
.venv\Scripts\alembic.exe revision --autogenerate -m "describe change"
```

Alembic reads `DATABASE_URL` from the application settings. For Docker Compose, use the internal database host `db`. For local commands from Windows, use `localhost`.

## Available Endpoint

### `GET /api/v1/health`

Expected response:

```json
{
  "status": "ok",
  "service": "ticket-api",
  "version": "0.1.0"
}
```

This endpoint is used to verify that the API is running correctly.

## Testing

The project includes automated tests using `pytest`.

Run the tests locally:

```bash
.venv\Scripts\python.exe -m pytest
```

Current test coverage includes:

```http
GET /api/v1/health
```

The tests validate that the API:

- Returns HTTP status code `200`
- Returns `status: "ok"`
- Returns `service: "ticket-api"`
- Includes a `version` field
- Defines SQLAlchemy model metadata
- Uses the expected PostgreSQL psycopg database URL configuration

Test files:

```text
tests/test_health.py
tests/test_models.py
tests/test_database_config.py
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
  core/
  db/
  models/
  schemas/
  main.py

alembic/
  versions/

tests/
  test_health.py
  test_models.py
  test_database_config.py

Dockerfile
alembic.ini
docker-compose.yml

.github/
  workflows/
    ci.yml
```

## Error Handling Included

The API currently includes basic error handling for:

- `404` responses in a consistent JSON format
- `422` validation errors
- `500` internal server errors with a generic message that avoids exposing internal details

## Current Status

Completed:

- FastAPI project skeleton
- Versioned API routing
- Health check endpoint
- Basic error handling
- Initial README
- Automated health endpoint test with `pytest`
- GitHub Actions CI workflow
- SQLAlchemy domain models
- Database configuration
- SQLAlchemy engine and session setup
- Alembic migration setup
- Initial database migration for users, tickets, and incidents
- Dockerfile and Docker Compose local development setup

## Next Phase

The next phase will add API behavior on top of the database layer without breaking the current project structure.

Future phases will include CRUD endpoints, authentication, role-based access control, CI/CD improvements, and cloud deployment.
