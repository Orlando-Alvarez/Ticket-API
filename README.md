# Ticket-API

Ticket-API is a portfolio-oriented backend for ticket and incident management.
It demonstrates modular FastAPI development, PostgreSQL persistence, database
migrations, OAuth2/JWT authentication, role-based authorization, resource-level
access control, automated testing, and a professional Git workflow.

The repository also provides a Docker Compose workflow that builds the API,
starts PostgreSQL, applies Alembic migrations, and exposes the application for
local use.

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
- Incident reporting with reporter/admin access control
- Paginated Incident listing with status and severity filters
- Admin-only soft deletion with UTC timestamp and actor auditing
- Pydantic request validation and consistent JSON errors
- Automated tests with Pytest and FastAPI's `TestClient`
- Basic GitHub Actions test workflow

## Authorization Model

New accounts are always created as active `requester` users. Supplying
`role` or `is_active` during public registration does not grant additional
privileges.

The application currently recognizes these effective roles:

- **requester**: the default account role
- **admin**: can list and update users and manage every ticket and incident

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
| Soft-delete a ticket | Denied | Allowed |

### Incident permissions

| Operation | Reporter | Admin |
| --- | --- | --- |
| Create an incident | For self | For self |
| List incidents | Own reported incidents | All incidents |
| Read an incident | Own reported incidents | Any incident |
| Update title, description, or severity | Own reported incidents | Any incident |
| Update status | Denied | Allowed |
| Soft-delete an incident | Denied | Allowed |

Incident reporters are always derived from the authenticated user and cannot be
supplied or reassigned through the API.

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
- **Docker and Docker Compose** for the containerized API, migrations, and database
- **GitHub Actions** for automated test execution

## Project Structure

```text
app/
  api/
    routes/
      auth.py
      health.py
      incidents.py
      tickets.py
      users.py
    router.py
  core/
    config.py
    errors.py
    security.py
  crud/
    incidents.py
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
    incident.py
    ticket.py
    user.py
  main.py

alembic/
  env.py
  script.py.mako
  versions/
    20260523_0001_create_initial_tables.py
    20261112_0002_constrain_and_index_incidents.py
    445042e29bcb_add_soft_delete_fields_to_tickets_and_.py

tests/
  integration/
    test_postgres_schema.py
  conftest.py
  test_auth.py
  test_database_config.py
  test_health.py
  test_incidents.py
  test_models.py
  test_tickets.py
  test_users.py

.github/
  workflows/
    ci.yml

Dockerfile
docker-compose.yml
.env.example
alembic.ini
pyproject.toml
```

## Docker Compose

### Requirements

- Docker Desktop on Windows or macOS, or Docker Engine on Linux
- Docker Compose v2, available through the `docker compose` command
- Local ports `8000` and `5432` available

### 1. Configure the environment

Create a local `.env` file from the tracked example.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS or Linux:

```bash
cp .env.example .env
```

Before starting the services, replace every placeholder in `.env` with your
own local values. In particular:

- Set `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` for PostgreSQL.
- Set `JWT_SECRET_KEY` to a long, random value. One way to generate one is:

  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```

Do not commit `.env`, database passwords, JWT secrets, or access tokens. The
repository ignores `.env`; `.env.example` contains placeholders only.

The two database URLs serve different execution contexts:

- `DATABASE_URL` in `.env.example` uses `localhost` and is intended for running
  Alembic or the API directly on the host machine.
- Docker Compose constructs and injects its own `DATABASE_URL` from the
  `POSTGRES_*` variables. It uses `db` as the host because containers reach
  PostgreSQL by its Compose service name.

The `api` and `migrate` containers receive the Compose-built URL, so the local
`DATABASE_URL` value is not used by those containers.

### 2. Build and start the stack

```bash
docker compose up -d --build
```

Compose starts the services in this order:

1. `db` starts PostgreSQL 16 and must pass its `pg_isready` healthcheck.
2. `migrate` runs `python -m alembic upgrade head` and exits after the schema is
   current.
3. `api` starts only after `migrate` completes successfully.

After startup, open:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Health check: <http://localhost:8000/api/v1/health>

### 3. Check service status and logs

Include stopped one-shot services, such as `migrate`, when checking status:

```bash
docker compose ps -a
```

Useful log commands:

```bash
docker compose logs migrate
docker compose logs -f api
docker compose logs -f db
```

Press `Ctrl+C` to stop following logs; the containers continue running.

### 4. Stop the stack without deleting data

Stop the containers while keeping them available to restart:

```bash
docker compose stop
```

Or remove the containers and Compose network while preserving the database
volume:

```bash
docker compose down
```

PostgreSQL stores its data in the named `postgres_data` volume mounted at
`/var/lib/postgresql/data`. Both commands above preserve that volume. Running
`docker compose down -v` deletes the volume and permanently removes the local
database data; use it only when an intentional full reset is required.

## Local Development

### Requirements

- Python 3.11 or newer
- `pip`
- A PostgreSQL instance
- Git

Docker can also be used to start only PostgreSQL while Alembic and the API run
directly on the host machine.

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

Configure the local `.env` file without committing it. Keep `DATABASE_URL`
pointing to `localhost` for this host-based workflow:

```dotenv
APP_NAME=ticket-api
APP_VERSION=0.1.0
APP_DEBUG=false
API_V1_PREFIX=/api/v1
DATABASE_URL=postgresql+psycopg://<db-user>:<db-password>@localhost:5432/<db-name>
JWT_SECRET_KEY=<long-random-secret>
```

`JWT_SECRET_KEY` is required and must not contain a real production key in
source control. The application supports `ACCESS_TOKEN_EXPIRE_MINUTES` as an
optional setting and defaults it to `30` when it is not set. Generate a
development JWT secret locally, for example:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`APP_DEBUG` controls FastAPI debug mode and defaults to `false`. The
application ignores Compose-only `POSTGRES_*` entries when reading the shared
local `.env` file.

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

The migrations create:

- `users`
- `tickets`
- `incidents`
- `alembic_version`

The Incident migration also enforces supported status and severity values,
adds database defaults, and creates an index for reporter-scoped pagination.
The Soft Delete migration adds nullable `deleted_at` and `deleted_by_id`
columns to Tickets and Incidents with foreign keys to `users.id`.

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
| `DELETE` | `/api/v1/tickets/{ticket_id}` | Admin only; soft-deletes the ticket |

### Protected incident endpoints

| Method | Path | Access |
| --- | --- | --- |
| `POST` | `/api/v1/incidents` | Authenticated user; reporter is derived from the JWT |
| `GET` | `/api/v1/incidents` | Own incidents for reporters; all incidents for admins |
| `GET` | `/api/v1/incidents/{incident_id}` | Reporter or admin |
| `PATCH` | `/api/v1/incidents/{incident_id}` | Reporter or admin; status is admin-only |
| `DELETE` | `/api/v1/incidents/{incident_id}` | Admin only; soft-deletes the incident |

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

## Incident Examples

### Create an incident

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/incidents" \
  -H "Authorization: Bearer <jwt-access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Payment service unavailable",
    "description": "Customers cannot complete checkout.",
    "severity": "high"
  }'
```

The API does not accept ownership input: `reported_by_id` and initial `status`
are server-controlled fields and are rejected if supplied.

### List accessible incidents

```bash
curl "http://127.0.0.1:8000/api/v1/incidents?status=open&severity=high&offset=0&limit=50" \
  -H "Authorization: Bearer <jwt-access-token>"
```

The response contains `items`, `total`, `offset`, and `limit`. Non-admin users
receive only their own incidents; admins receive all matching incidents. The
public filters are limited to `status` and `severity`.

Supported severity values are `low`, `medium`, `high`, and `critical`.
Supported status values are `open`, `investigating`, `resolved`, and `closed`.

## Soft Delete Behavior

Ticket and Incident DELETE endpoints return `204 No Content`. They retain the
database row, store a timezone-aware UTC `deleted_at` value, and record the
authenticated administrator in `deleted_by_id`.

Deleted resources are excluded from detail, update, and list operations. A
repeated DELETE and any subsequent GET or PATCH return `404 Not Found`.
Restore, include-deleted, and hard-delete operations are not exposed.

## Validation and Error Responses

Pydantic validates email addresses, password length, required fields, text
boundaries, controlled Incident values, pagination parameters, explicit null
values, and unknown fields.

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

- `204 No Content`: resource was soft-deleted successfully
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
122 passed, 2 skipped
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
- Incident creation, ownership, reporter/admin authorization, and updates
- Incident pagination, status and severity filtering, and database constraints
- Ticket and Incident soft deletion, audit metadata, and visibility rules
- PostgreSQL Soft Delete migration upgrade, downgrade, and reapplication
- Regression tests for existing user and ticket behavior

The test extra uses `httpx2`, which is compatible with the current
FastAPI/Starlette `TestClient`. Pytest is constrained below version 10 while
the current AnyIO plugin still uses an API scheduled for removal in Pytest 10.

## Continuous Integration

The GitHub Actions workflow at `.github/workflows/ci.yml` runs on:

- Pushes to `main`
- Pushes to `feat/**` branches
- Pull requests targeting `main`

It performs three jobs:

- Installs `.[test]`, runs Ruff, and runs the complete unit test suite.
- Starts an isolated PostgreSQL service, applies Alembic migrations, and runs
  the schema integration test against `ticket_api_test`.
- Builds the Docker image after the test jobs succeed.

This is validation automation only; advanced deployment pipelines, Jenkins,
Terraform, and cloud deployment are not implemented.

## Current Limitations and Roadmap

Not currently implemented:

- Restore, include-deleted, and hard-delete endpoints
- Pagination and filtering for Ticket and User collections
- Refresh tokens and token revocation
- Public admin bootstrap
- Advanced CI/CD or deployment automation
- Terraform, Jenkins, AWS, or another cloud deployment

Planned follow-up work:

1. Add pagination and filtering to the remaining collection endpoints.
2. Define authorization and retention requirements before adding restoration.
3. Extend authentication lifecycle and operational tooling as needed.

## Security Notes

- Never commit `.env`, JWT secrets, database passwords, or access tokens.
- Use a long random `JWT_SECRET_KEY` for every environment.
- Keep development and production credentials separate.
- Apply Alembic migrations before serving traffic.
- Review the assumed ticket authorization policy before production use.
