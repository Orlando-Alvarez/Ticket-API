# Local Development

[Back to the main README](../README.md)

This guide covers local Docker Compose execution and direct Python
development. It does not describe the AWS deployment workflow.

## Prerequisites

- Git
- Docker Engine or Docker Desktop
- Docker Compose v2
- Python 3.11 or later for direct host development

## Clone and Configure

```bash
git clone https://github.com/Orlando-Alvarez/Ticket-API.git
cd Ticket-API
```

Create a local environment file.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS, Linux, or Ubuntu WSL:

```bash
cp .env.example .env
```

Replace every placeholder locally. Never commit `.env`.

| Variable | Required for | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Host API, Alembic, integration tests | SQLAlchemy PostgreSQL URL |
| `JWT_SECRET_KEY` | API and migration container | Signs and verifies JWTs |
| `POSTGRES_USER` | Docker Compose | PostgreSQL user |
| `POSTGRES_PASSWORD` | Docker Compose | PostgreSQL password |
| `POSTGRES_DB` | Docker Compose | PostgreSQL database |
| `APP_DEBUG` | Optional | FastAPI debug mode; defaults to `false` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Optional | JWT lifetime; defaults to 30 minutes |
| `APP_NAME`, `APP_VERSION`, `API_V1_PREFIX` | Optional | Service metadata and route prefix |

Generate a development-only JWT secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Compose constructs an internal `DATABASE_URL` with hostname `db`. When running
the API or Alembic directly on the host against the Compose database, use
`localhost:5434`. A separately installed PostgreSQL server may use another
port, commonly `5432`.

## Local Docker Compose

Build and start the complete local stack:

```bash
docker compose up -d --build
```

The command starts PostgreSQL, applies migrations through the one-shot
`migrate` service, starts FastAPI, and then starts Nginx after the API
healthcheck succeeds.

### Local URLs

- Swagger UI: <http://127.0.0.1:8080/docs>
- ReDoc: <http://127.0.0.1:8080/redoc>
- Liveness: <http://127.0.0.1:8080/api/v1/health>
- Readiness: <http://127.0.0.1:8080/api/v1/health/ready>

### Status and Logs

```bash
docker compose ps -a
docker compose logs migrate
docker compose logs -f api
docker compose logs -f nginx
docker compose logs -f db
```

`docker compose ps -a` includes the stopped migration container, whose expected
successful state is exit code 0.

### Apply Migrations Explicitly

The complete startup applies migrations automatically. To run the migration
service again:

```bash
docker compose run --rm migrate
```

### Production-Like Local Override

```bash
docker compose \
  -f docker-compose.yml \
  -f compose.prod.yaml \
  up -d --build
```

This removes the PostgreSQL host port, forces FastAPI debug mode off, and
publishes Nginx on host port 80. It still serves plain HTTP and is not the AWS
deployment configuration.

### Stop Without Deleting Data

```bash
docker compose stop
```

Remove containers and Compose networks while preserving the named database
volume:

```bash
docker compose down
```

Do not use `docker compose down -v` unless permanent deletion of local
PostgreSQL data is intentional.

## Direct Python Development

### Create a Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS, Linux, or Ubuntu WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install Dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

### Start PostgreSQL Only

```bash
docker compose up -d db
```

When using this database from the host, configure `DATABASE_URL` with
`localhost:5434`.

### Apply Migrations and Run FastAPI

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Direct execution serves Swagger UI at <http://127.0.0.1:8000/docs>.

Create a migration after changing SQLAlchemy models:

```bash
python -m alembic revision --autogenerate -m "describe the change"
```

Review generated migrations before applying them.

## Authentication Example

Register an active requester:

```bash
curl -X POST "http://127.0.0.1:8080/api/v1/users" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "requester@example.com",
    "full_name": "Example Requester",
    "password": "<account-password>"
  }'
```

Obtain a JWT. OAuth2 uses the email in the `username` field:

```bash
curl -X POST "http://127.0.0.1:8080/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=requester@example.com&password=<account-password>"
```

Call a protected endpoint:

```bash
curl "http://127.0.0.1:8080/api/v1/users/me" \
  -H "Authorization: Bearer <jwt-access-token>"
```

Passwords, access tokens, and password hashes must never be committed or
included in screenshots.

