# Ticket-API

Ticket-API is a portfolio-oriented backend for ticket and incident management.
It demonstrates modular FastAPI development, PostgreSQL persistence, database
migrations, OAuth2/JWT authentication, role-based authorization, resource-level
access control, automated testing, and a professional Git workflow.

The current authentication and security release focuses on protecting user and
ticket operations. Docker infrastructure improvements are intentionally being
developed in a separate pull request; see [Docker status](#docker-status).

## Key Capabilities

- Versioned FastAPI routes under `/api/v1`
- Modular routes, schemas, CRUD functions, models, configuration, and security
- PostgreSQL with SQLAlchemy 2
- Alembic database migrations
- User registration with Argon2 password hashing
- OAuth2 password flow with JWT bearer tokens
- Role-based access control for `requester` and `admin`
- User profile and administration endpoints
- Ticket access based on `requester_id` and `assignee_id`
- Protection against unauthorized ownership and assignment changes
- Pydantic request validation and consistent JSON errors
- Automated tests with Pytest and FastAPI's `TestClient`
- Basic GitHub Actions test workflow

## Authorization Model

New accounts are always created as active `requester` users. Supplying
`role` or `is_active` during public registration does not grant additional
privileges.

The application currently recognizes these effective roles:

- **requester**: the default account role
- **admin**: can list and update users and manage every ticket

An assignee is not a separate RBAC role. Ticket access as an assignee is based
on the ticket's `assignee_id` relationship.

### User permissions

| Operation | Requester | Admin |
| --- | --- | --- |
| Register a user | Public | Public |
| Read `/users/me` | Own profile | Own profile |
| Read `/users/{user_id}` | Own profile only | Any user |
| List users | Denied | Allowed |
| Update users or roles | Denied | Allowed |

### Ticket permissions

| Operation | Non-admin user | Admin |
| --- | --- | --- |
| Create a ticket | For self, without initial assignment | For any valid requester, with optional assignment |
| List tickets | Requested or assigned tickets only | All tickets |
| Read a ticket | Requested or assigned tickets only | Any ticket |
| Update normal fields | Requested or assigned tickets only | Any ticket |
| Change `requester_id` or `assignee_id` | Denied | Allowed |

Inactive users cannot log in or access protected endpoints.

## Tech Stack

- **Python 3.11+**
- **FastAPI** and **Uvicorn**
- **Pydantic** and **pydantic-settings**
- **SQLAlchemy 2**
- **PostgreSQL** and **psycopg 3**
- **Alembic**
- **PyJWT**
- **pwdlib with Argon2**
- **Pytest**
- **httpx2** for compatibility with the current FastAPI/Starlette test client
- **Docker and Docker Compose** for the basic local database/application setup
- **GitHub Actions** for automated test execution

## Project Structure

```text
app/
  api/
    routes/
      auth.py
      health.py
      tickets.py
      users.py
    router.py
  core/
    config.py
    errors.py
    security.py
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
    auth.py
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
  conftest.py
  test_auth.py
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
```

## Local Development

### Requirements

- Python 3.11 or newer
- `pip`
- A PostgreSQL instance
- Git

Docker can be used to start only the existing PostgreSQL service while the API
runs locally. The full authenticated Docker workflow is pending a separate
infrastructure pull request.

### 1. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

For application development and testing:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

For runtime dependencies only:

```bash
python -m pip install -e .
```

### 3. Configure environment variables

Copy the example file:

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS or Linux:

```bash
cp .env.example .env
```

Configure the local `.env` file without committing it:

```dotenv
APP_NAME=ticket-api
APP_VERSION=0.1.0
DEBUG=false
API_V1_PREFIX=/api/v1
DATABASE_URL=postgresql+psycopg://<db-user>:<db-password>@localhost:5432/<db-name>
JWT_SECRET_KEY=<long-random-secret>
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

`JWT_SECRET_KEY` is required and must not contain a real production key in
source control. Generate a development value locally, for example:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 4. Start PostgreSQL

Use an existing PostgreSQL instance, or start the database service already
available in the repository:

```bash
docker compose up -d db
```

When the API runs from the host machine, `DATABASE_URL` must use
`localhost`. A containerized API uses the Compose service hostname `db`.

### 5. Apply migrations

```bash
python -m alembic upgrade head
```

The initial migration creates:

- `users`
- `tickets`
- `incidents`
- `alembic_version`

Create a migration after changing SQLAlchemy models:

```bash
python -m alembic revision --autogenerate -m "describe the change"
```

### 6. Run the API

```bash
python -m uvicorn app.main:app --reload
```

Local URLs:

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- Health check: <http://127.0.0.1:8000/api/v1/health>

## Authentication

### Register a requester

`POST /api/v1/users` is public.

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/users" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "requester@example.com",
    "full_name": "Example Requester",
    "password": "<account-password>"
  }'
```

Example response:

```json
{
  "email": "requester@example.com",
  "full_name": "Example Requester",
  "role": "requester",
  "is_active": true,
  "id": 1,
  "created_at": "2026-01-01T12:00:00Z"
}
```

Plain-text passwords and password hashes are never returned by the API.

### Obtain a JWT access token

`POST /api/v1/auth/token` uses
`application/x-www-form-urlencoded`. The OAuth2 `username` field contains
the user's email address.

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=requester@example.com&password=<account-password>"
```

Example response:

```json
{
  "access_token": "<jwt-access-token>",
  "token_type": "bearer"
}
```

Use the token on protected endpoints:

```bash
curl "http://127.0.0.1:8000/api/v1/users/me" \
  -H "Authorization: Bearer <jwt-access-token>"
```

Invalid, expired, or missing credentials return `401 Unauthorized` with:

```text
WWW-Authenticate: Bearer
```

### Authenticate through Swagger UI

1. Start the API and open <http://127.0.0.1:8000/docs>.
2. Register a user with `POST /api/v1/users`.
3. Select **Authorize**.
4. Enter the registered email in **username** and the account password in
   **password**.
5. Leave client credentials empty and authorize.
6. Swagger automatically sends the bearer token to protected operations.

Admin-only operations still require an account whose stored role is `admin`.
There is no public admin bootstrap endpoint. The first admin must be promoted
through a trusted database or deployment process; an admin can then manage
other users through the API.

## API Endpoints

### Public endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Service health and version |
| `POST` | `/api/v1/users` | Register an active requester |
| `POST` | `/api/v1/auth/token` | Exchange email/password credentials for a JWT |

### Protected user endpoints

| Method | Path | Access |
| --- | --- | --- |
| `GET` | `/api/v1/users/me` | Current active user |
| `GET` | `/api/v1/users/{user_id}` | Same user or admin |
| `GET` | `/api/v1/users` | Admin only |
| `PATCH` | `/api/v1/users/{user_id}` | Admin only |

### Protected ticket endpoints

| Method | Path | Access |
| --- | --- | --- |
| `POST` | `/api/v1/tickets` | Authenticated user or admin, subject to creation rules |
| `GET` | `/api/v1/tickets` | Related tickets for non-admin users; all tickets for admin |
| `GET` | `/api/v1/tickets/{ticket_id}` | Requester, assignee, or admin |
| `PATCH` | `/api/v1/tickets/{ticket_id}` | Requester, assignee, or admin; relationship fields are admin-only |

## Ticket Examples

### Create a ticket as a requester

A non-admin user must use their own user ID and cannot set an initial assignee.

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/tickets" \
  -H "Authorization: Bearer <jwt-access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Cannot access dashboard",
    "description": "The dashboard returns an error after login.",
    "priority": "high",
    "requester_id": 1
  }'
```

Example response:

```json
{
  "title": "Cannot access dashboard",
  "description": "The dashboard returns an error after login.",
  "status": "open",
  "priority": "high",
  "requester_id": 1,
  "assignee_id": null,
  "id": 1,
  "created_at": "2026-01-01T12:00:00Z",
  "updated_at": null
}
```

### List accessible tickets

```bash
curl "http://127.0.0.1:8000/api/v1/tickets" \
  -H "Authorization: Bearer <jwt-access-token>"
```

Non-admin users receive only tickets where they are the requester or assignee.
Admins receive every ticket.

### Update a related ticket

```bash
curl -X PATCH "http://127.0.0.1:8000/api/v1/tickets/1" \
  -H "Authorization: Bearer <jwt-access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "in_progress",
    "description": "Investigation is in progress."
  }'
```

Only admins can change `requester_id` or `assignee_id`.

## Validation and Error Responses

Pydantic validates email addresses, password length, required fields, text
boundaries, explicit null values, and unknown PATCH fields.

Application errors use a consistent envelope:

```json
{
  "error": {
    "message": "Ticket not found."
  }
}
```

Validation failures include field details:

```json
{
  "error": {
    "message": "Validation failed.",
    "details": []
  }
}
```

Common status codes:

- `401 Unauthorized`: missing, invalid, or expired bearer token
- `403 Forbidden`: authenticated user lacks permission or is inactive
- `404 Not Found`: requested resource does not exist
- `409 Conflict`: duplicate user email
- `422 Unprocessable Content`: request validation failed
- `500 Internal Server Error`: unexpected server failure

## Testing

Install the test dependencies declared in `pyproject.toml`:

```bash
python -m pip install -e ".[test]"
```

Run the complete suite:

```bash
python -m pytest
```

Latest verified local result:

```text
78 passed
```

Coverage includes:

- Health and database configuration
- SQLAlchemy model registration and relationships
- User input validation and password protection
- OAuth2 login success and failure cases
- Valid, malformed, expired, and missing JWTs
- Inactive and missing users
- User RBAC for requester and admin
- Authentication requirements for every ticket endpoint
- Ticket creation, ownership, assignment, listing, reading, and updates
- Allowed and denied requester, assignee, unrelated-user, and admin scenarios
- Regression tests for existing user and ticket behavior

The test extra uses `httpx2`, which is compatible with the current
FastAPI/Starlette `TestClient`. Pytest is constrained below version 10 while
the current AnyIO plugin still uses an API scheduled for removal in Pytest 10.

## Continuous Integration

The repository contains a basic GitHub Actions workflow at
`.github/workflows/ci.yml`. It runs Pytest on:

- Pushes to `main`
- Pushes to `feat/**` branches
- Pull requests targeting `main`

The workflow installs `.[test]` and runs the full suite. This is test
automation only; advanced deployment pipelines, Jenkins, Terraform, and cloud
deployment are not implemented.

## Docker Status

The current `main` branch already contains a basic Docker setup:

- A Python application image
- A PostgreSQL 16 service
- Database health checks
- A persistent PostgreSQL volume
- API and database port mappings for local development

The authentication work does **not** claim the pending Docker improvements.
The following items belong to a separate Docker pull request:

- Copying Alembic files into the application image
- Automatically running `alembic upgrade head` before API startup
- A dedicated Compose migration service
- Final Compose wiring for the required `JWT_SECRET_KEY`
- Updated full-stack Docker startup instructions

Until that pull request is merged, the recommended authenticated development
flow is:

1. Start only PostgreSQL with `docker compose up -d db`.
2. Configure `.env` locally.
3. Run Alembic and FastAPI from the local virtual environment.

Do not assume that the uncommitted local Docker enhancements are available on
`main`.

## Current Limitations and Roadmap

Not currently implemented:

- Incident CRUD endpoints
- DELETE endpoints
- Pagination and filtering
- Refresh tokens and token revocation
- Public admin bootstrap
- Automated container migrations on `main`
- Advanced CI/CD or deployment automation
- Terraform, Jenkins, AWS, or another cloud deployment

Planned follow-up work:

1. Complete the dedicated Docker and Docker Compose pull request.
2. Add incident management endpoints.
3. Add pagination and filtering.
4. Extend authentication lifecycle and operational tooling as needed.

## Security Notes

- Never commit `.env`, JWT secrets, database passwords, or access tokens.
- Use a long random `JWT_SECRET_KEY` for every environment.
- Keep development and production credentials separate.
- Apply Alembic migrations before serving traffic.
- Review the assumed ticket authorization policy before production use.
