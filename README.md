# Ticket-API

Ticket-API is a backend API for a portfolio-oriented ticketing and incident management system. It is designed for junior backend, cloud, and platform engineering roles.

This first phase provides a clean FastAPI foundation with versioned routes, a health check endpoint, basic error handling, automated testing with `pytest`, and a GitHub Actions CI workflow.

## Project Goals

This project is being built to demonstrate practical backend and cloud-readiness skills, including:

- Python backend development with FastAPI
- Clean API structure and versioned routing
- Basic service health checks
- Consistent error handling
- Automated testing with `pytest`
- Continuous Integration with GitHub Actions
- Preparation for future PostgreSQL persistence
- Preparation for Docker and cloud deployment

## Requirements

- Python 3.11+
- `pip`

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
python -m pytest
```

Current test coverage includes the health check endpoint:

```http
GET /api/v1/health
```

The test validates that the API:

- Returns HTTP status code `200`
- Returns `status: "ok"`
- Returns `service: "ticket-api"`
- Includes a `version` field

Test file:

```text
tests/test_health.py
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
  schemas/
  main.py

tests/
  test_health.py

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

## Next Phase

The next phase will add persistence with PostgreSQL and initial domain models without breaking the current project structure.

Planned models:

- User
- Ticket
- Incident

Future phases will include authentication, role-based access control, Docker, CI/CD improvements, and cloud deployment.
