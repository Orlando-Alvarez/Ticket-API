# Ticket-API

Ticket-API is a backend and infrastructure portfolio project for managing
support tickets and operational incidents. It combines a versioned FastAPI REST
API with PostgreSQL persistence, JWT authentication, role-based and
resource-level authorization, automated tests, containerized local execution,
and an AWS foundation provisioned with Terraform and configured through
Ansible.

The project is intended to demonstrate practical Backend Engineering and
DevOps/Cloud Engineering skills. It does not include a frontend.

## Implementation Status

| Area | Status | Current scope |
| --- | --- | --- |
| FastAPI backend | Implemented | Users, authentication, tickets, incidents, health endpoints, validation, RBAC, and soft deletion |
| Automated tests | Implemented | SQLite-backed API tests and isolated PostgreSQL schema/migration tests |
| Local containers | Implemented | FastAPI, PostgreSQL, Alembic migrations, and Nginx through Docker Compose |
| CI validation | Implemented | Ruff, unit tests, PostgreSQL integration tests, and Docker image build |
| AWS infrastructure | Provisioned | VPC, public/private subnets, routing, security group, EC2, IAM/SSM integration, and private S3 bucket |
| EC2 configuration | Implemented | Docker Engine installed and enabled through Ansible over AWS Systems Manager |
| Application deployment to EC2 | In development | Docker Compose is not yet installed on EC2 and Ticket-API is not yet deployed there |
| Continuous deployment | Roadmap | Jenkins-based deployment automation has not been implemented |
| Production observability | Roadmap | Prometheus, Grafana, dashboards, alerts, and centralized observability have not been implemented |
| HTTPS | Roadmap | The current Nginx configuration serves HTTP only |

## Features

### Backend

- Versioned routes under `/api/v1`
- FastAPI-generated OpenAPI schema, Swagger UI, and ReDoc
- PostgreSQL persistence through SQLAlchemy 2 and psycopg 3
- Alembic migrations for users, tickets, incidents, constraints, indexes, and
  soft-delete audit fields
- Public requester registration with Argon2 password hashing
- OAuth2 password flow with HS256 JWT access tokens
- `requester` and `admin` authorization policies
- Ticket access based on requester and assignee relationships
- Incident access based on the authenticated reporter
- Incident pagination with `offset` and `limit`
- Incident filtering by `status` and `severity`
- Admin-only atomic soft deletion for tickets and incidents
- Consistent JSON error envelopes and Pydantic request validation
- Liveness and database readiness endpoints

### DevOps and Cloud

- Non-root FastAPI container based on `python:3.12-slim`
- Local Docker Compose orchestration with service health checks and an
  automatic Alembic migration job
- Separate base and production-like Compose configurations
- Nginx reverse proxy with rate limiting, upstream timeouts, and operational
  access logs
- GitHub Actions jobs for static analysis, API tests, PostgreSQL integration,
  and Docker image construction
- AWS networking, compute, IAM, Systems Manager, and S3 resources managed with
  Terraform
- SSH-free EC2 configuration through the
  `amazon.aws.aws_ssm` Ansible connection plugin
- Idempotent Docker Engine installation on Amazon Linux 2023

## Technology Stack

| Layer | Technology | Purpose |
| --- | --- | --- |
| Language | Python 3.11+ | Backend implementation; the container and CI use Python 3.12 |
| API | FastAPI and Uvicorn | REST endpoints, dependency injection, OpenAPI, and ASGI serving |
| Validation | Pydantic and pydantic-settings | Request/response schemas and environment-driven settings |
| Persistence | SQLAlchemy 2 and psycopg 3 | ORM mapping and PostgreSQL connectivity |
| Database | PostgreSQL 16 | Durable relational storage in the Compose environment |
| Migrations | Alembic | Versioned database schema changes |
| Security | PyJWT and pwdlib with Argon2 | JWT access tokens and password hashing |
| Testing | Pytest, FastAPI TestClient, and httpx2 | Unit, API, authorization, and integration tests |
| Static analysis | Ruff | Python linting in development and CI |
| Containers | Docker and Docker Compose | Reproducible application and database execution |
| Proxy | Nginx | Public HTTP entry point, throttling, forwarding, and logs |
| CI | GitHub Actions | Test, integration, and image-build validation |
| Infrastructure | Terraform and AWS Provider | Reproducible AWS resource provisioning |
| Configuration | Ansible and `amazon.aws` | EC2 configuration through Systems Manager |
| AWS | VPC, EC2, IAM, SSM, and S3 | Network, compute, access control, remote management, and temporary Ansible transfer storage |

## Architecture

### Local Docker architecture

The base Compose file defines four services and two bridge networks:

```mermaid
flowchart LR
    Client[Developer or API client] -->|127.0.0.1:8080| Nginx
    Nginx -->|proxy_net: api:8000| API[FastAPI]
    API -->|data_net: db:5432| DB[(PostgreSQL 16)]
    Migrate[Alembic migrate job] -->|data_net| DB
    DB --> Volume[(postgres_data volume)]
```

- `nginx` is the only HTTP entry point and is connected only to `proxy_net`.
- `api` connects to both `proxy_net` and `data_net`; its port is not published
  directly to the host.
- `migrate` runs `python -m alembic upgrade head` and must finish successfully
  before the API starts.
- `db` is connected only to `data_net`. Development access from the host is
  bound to `127.0.0.1:5434`.
- PostgreSQL data persists in the named `postgres_data` volume.

The production-like override removes the host database port, keeps FastAPI
debug mode disabled, and publishes Nginx on host port 80. This override is a
container runtime configuration; it is not evidence of a completed AWS
deployment.

### Container build and request path

The Dockerfile starts from `python:3.12-slim`, disables bytecode generation,
enables unbuffered logs, and installs Ticket-API as a regular Python package.
Its BuildKit cache mount reuses downloaded Python packages between builds.
Alembic configuration and migration files are included in the runtime image so
the same image can serve both the `api` and `migrate` services.

The image creates a system user and group and runs Uvicorn as the non-root
`appuser` on port 8000. Nginx reaches that internal port through `proxy_net`.
Nginx forwards the original host, client IP, forwarding chain, and scheme;
applies five-second connection and 30-second read/write timeouts; emits request
and upstream timing logs to standard output; and returns `429` when its request
limit is exceeded. Liveness and readiness traffic is excluded from rate
limiting.

### AWS infrastructure architecture

```mermaid
flowchart TB
    TF[Windows PowerShell<br/>Terraform with ticketapi-tf] --> AWS[AWS API]
    AWS --> VPC[VPC 10.20.0.0/16]
    VPC --> Public[Public subnet<br/>10.20.1.0/24]
    VPC --> Private[Private subnet<br/>10.20.2.0/24]
    Internet[Internet] --> IGW[Internet Gateway]
    IGW --> Public
    Public --> EC2[Amazon Linux 2023 EC2<br/>Docker Engine installed]
    EC2 --> Profile[IAM instance profile]
    Profile --> SSM[AWS Systems Manager]
    WSL[Ubuntu WSL<br/>Ansible with ticketapi-dev] --> SSM
    WSL -. temporary module transfer .-> S3[Private encrypted S3 bucket]
```

The EC2 instance currently resides in the public subnet, receives a public IP,
and accepts inbound HTTP on port 80. Port 22 is not opened; administration uses
AWS Systems Manager. The private subnet and its route table exist but currently
host no project workload and have no NAT or Internet Gateway default route.

Docker Engine 25.0.14 has been installed on EC2 through Ansible. Docker Compose
and the Ticket-API application stack have not yet been installed or deployed on
that instance.

## Project Structure

```text
app/
  api/
    routes/                 # Auth, health, users, tickets, and incidents
    router.py               # Versioned router registration
  core/
    config.py               # Environment-backed application settings
    errors.py               # Global exception handlers
    security.py             # Password hashing, JWTs, and current-user dependency
  crud/                     # Database queries and write operations
  db/                       # SQLAlchemy base, engine, and session dependency
  models/                   # User, Ticket, and Incident ORM models
  schemas/                  # Pydantic request and response models
  main.py                   # FastAPI application factory

alembic/
  versions/                 # Initial schema, Incident constraints, and soft delete

tests/
  integration/              # PostgreSQL schema and migration round-trip tests
  conftest.py               # SQLite test database and FastAPI client fixtures
  test_*.py                 # API, authorization, validation, and model tests

terraform/
  compute.tf                # EC2 instance and storage configuration
  iam.tf                    # EC2 SSM role and instance profile
  main.tf                   # VPC, subnets, Internet Gateway, and route tables
  providers.tf              # AWS provider configuration
  s3.tf                     # Private temporary-transfer bucket for Ansible
  security.tf               # HTTP ingress and outbound rules
  variables.tf              # Region, CIDRs, instance type, and pinned AMI input
  versions.tf               # Terraform and AWS provider constraints

ansible/
  Inventory/hosts.yml       # Static EC2 inventory using the SSM connection plugin
  playbooks/setup_docker.yml

.github/workflows/ci.yml
Dockerfile
docker-compose.yml
compose.prod.yaml
nginx/default.conf
alembic.ini
pyproject.toml
```

## API and Authorization

### Authentication model

- New public registrations are always stored as active `requester` users.
- Passwords are hashed with Argon2 and never returned by the API.
- `POST /api/v1/auth/token` accepts OAuth2 form data and returns a bearer token.
- JWTs use HS256, contain the user ID in `sub`, require an expiration claim, and
  expire after 30 minutes by default.
- Missing, invalid, or expired credentials return `401 Unauthorized`.
- Inactive users cannot log in or use protected endpoints.
- There is no public admin bootstrap endpoint. Initial admin promotion requires
  a trusted database or deployment process.
- Refresh tokens and token revocation are not currently implemented.

### Authorization summary

| Resource | Requester or related user | Admin |
| --- | --- | --- |
| Users | Read own profile | List, read, and update users |
| Tickets | Create for self; read/update requested or assigned tickets | Access all tickets, change relationships, and soft-delete |
| Incidents | Create for self; read/update own reported incidents except status | Access all incidents, change status, and soft-delete |

Incident ownership is derived from the authenticated user. The API does not
accept `reported_by_id` as an input or public list filter.

### Public endpoints

| Method | Path | Behavior |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Liveness response with service name and version |
| `GET` | `/api/v1/health/ready` | Executes `SELECT 1`; returns `503` on a SQLAlchemy database error |
| `POST` | `/api/v1/users` | Registers an active requester |
| `POST` | `/api/v1/auth/token` | Exchanges email/password credentials for a JWT |

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
| `POST` | `/api/v1/tickets` | Authenticated user subject to creation rules |
| `GET` | `/api/v1/tickets` | Related tickets for non-admins; all active tickets for admins |
| `GET` | `/api/v1/tickets/{ticket_id}` | Requester, assignee, or admin |
| `PATCH` | `/api/v1/tickets/{ticket_id}` | Related user or admin; relationship fields are admin-only |
| `DELETE` | `/api/v1/tickets/{ticket_id}` | Admin-only soft deletion |

### Protected incident endpoints

| Method | Path | Access |
| --- | --- | --- |
| `POST` | `/api/v1/incidents` | Authenticated user; reporter comes from the JWT |
| `GET` | `/api/v1/incidents` | Own incidents for requesters; all active incidents for admins |
| `GET` | `/api/v1/incidents/{incident_id}` | Reporter or admin |
| `PATCH` | `/api/v1/incidents/{incident_id}` | Reporter or admin; status changes are admin-only |
| `DELETE` | `/api/v1/incidents/{incident_id}` | Admin-only soft deletion |

Incident listing supports:

```text
GET /api/v1/incidents?status=open&severity=high&offset=0&limit=50
```

Supported severities are `low`, `medium`, `high`, and `critical`. Supported
statuses are `open`, `investigating`, `resolved`, and `closed`. The maximum
page size is 100.

### Soft deletion

Ticket and Incident deletion uses a conditional SQL `UPDATE` that applies only
when `deleted_at` is still null. A successful deletion records a UTC timestamp
and the authenticated admin ID, returns `204 No Content`, and cannot have its
audit metadata overwritten by a repeated delete. Deleted rows are excluded
from list, detail, and update operations.

Restore, include-deleted, and hard-delete endpoints are not implemented.

### Validation and errors

Pydantic validates email addresses, password length, required fields, text
limits, Incident enums, pagination, explicit null values, and forbidden extra
fields. Incident constraints are also enforced in PostgreSQL.

Application errors use a consistent envelope:

```json
{
  "error": {
    "message": "Ticket not found."
  }
}
```

Validation errors add a `details` array. Unexpected exceptions return a generic
`500` response, and readiness failures do not expose SQL, credentials, or
connection details.

## Local Development

### Prerequisites

- Python 3.11 or later
- Docker Engine or Docker Desktop
- Docker Compose v2
- Git

### Environment configuration

Create a local environment file from the placeholder-only example:

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS, Linux, or Ubuntu WSL:

```bash
cp .env.example .env
```

Replace every placeholder locally. Never commit `.env`.

| Variable | Required for | Description |
| --- | --- | --- |
| `DATABASE_URL` | Host API, Alembic, and PostgreSQL integration tests | SQLAlchemy PostgreSQL URL |
| `JWT_SECRET_KEY` | API and migration container startup | Secret used to sign and verify JWTs |
| `POSTGRES_USER` | Docker Compose | PostgreSQL user |
| `POSTGRES_PASSWORD` | Docker Compose | PostgreSQL password |
| `POSTGRES_DB` | Docker Compose | PostgreSQL database name |
| `APP_DEBUG` | Optional | FastAPI debug mode; defaults to `false` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Optional | JWT lifetime; defaults to `30` |
| `APP_NAME`, `APP_VERSION`, `API_V1_PREFIX` | Optional | Service metadata and API prefix |

Compose constructs an internal `DATABASE_URL` with hostname `db`. When the API
or Alembic runs on the host against the Compose database, use
`localhost:5434`. A separately installed local PostgreSQL server may use its
own port, commonly `5432`.

Generate a development-only JWT secret locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Run with Docker Compose

Build and start the local stack:

```bash
docker compose up -d --build
```

Startup order is:

1. PostgreSQL becomes healthy through `pg_isready`.
2. The one-shot `migrate` service applies Alembic migrations.
3. FastAPI starts and passes its `/openapi.json` container healthcheck.
4. Nginx starts and forwards requests to `api:8000`.

Local URLs:

- Swagger UI: <http://127.0.0.1:8080/docs>
- ReDoc: <http://127.0.0.1:8080/redoc>
- Liveness: <http://127.0.0.1:8080/api/v1/health>
- Readiness: <http://127.0.0.1:8080/api/v1/health/ready>

Inspect services and logs:

```bash
docker compose ps -a
docker compose logs migrate
docker compose logs -f api
docker compose logs -f nginx
```

Run the production-like override locally:

```bash
docker compose -f docker-compose.yml -f compose.prod.yaml up -d --build
```

This publishes Nginx on port 80 and does not publish PostgreSQL. It still uses
plain HTTP and is not a complete production deployment.

Stop services while preserving database data:

```bash
docker compose stop
```

Remove containers and Compose networks while preserving the named volume:

```bash
docker compose down
```

Do not use `docker compose down -v` unless permanent deletion of the local
database volume is intentional.

### Run directly with Python

Create and activate a virtual environment:

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

Install the application and development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

Apply migrations and start the API:

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Direct host execution serves Swagger at <http://127.0.0.1:8000/docs>.

### Authentication quick start

Register a requester:

```bash
curl -X POST "http://127.0.0.1:8080/api/v1/users" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "requester@example.com",
    "full_name": "Example Requester",
    "password": "<account-password>"
  }'
```

Obtain a token. The OAuth2 `username` field contains the user's email:

```bash
curl -X POST "http://127.0.0.1:8080/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=requester@example.com&password=<account-password>"
```

Use the returned token:

```bash
curl "http://127.0.0.1:8080/api/v1/users/me" \
  -H "Authorization: Bearer <jwt-access-token>"
```

## Testing and Static Analysis

Run Ruff:

```bash
python -m ruff check .
```

Run the complete Pytest collection:

```bash
python -m pytest -v
```

FastAPI tests use an in-memory SQLite database with dependency overrides. The
suite covers authentication, authorization, input validation, users, ticket
ownership and assignment, Incident scoping and filters, health behavior,
soft-delete visibility, and ORM metadata. No coverage percentage is currently
published.

The PostgreSQL integration tests inspect the migrated schema and perform a
soft-delete migration downgrade/upgrade round trip. They require an isolated
PostgreSQL database whose name is exactly `ticket_api_test`; otherwise they
skip or fail safely.

Example for an explicitly disposable database:

Windows PowerShell:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://<test-user>:<test-password>@127.0.0.1:5432/ticket_api_test"
python -m alembic upgrade head
python -m pytest tests/integration -v
```

The GitHub Actions integration job provisions this database automatically.

## AWS Infrastructure with Terraform

Terraform code in `terraform/` targets AWS region `us-west-2`. It requires
Terraform `>= 1.17.0, < 2.0.0`, constrains the AWS provider to `~> 6.0`, and
currently locks provider version `6.73.0`.

### Provisioned resources

| Resource | Current configuration and purpose |
| --- | --- |
| VPC | `10.20.0.0/16` with DNS support and DNS hostnames enabled |
| Public subnet | `10.20.1.0/24` in `us-west-2a`, with public IP assignment |
| Private subnet | `10.20.2.0/24` in `us-west-2a`, without public IP assignment |
| Internet Gateway | Attached to the VPC for public internet connectivity |
| Public route table | Sends `0.0.0.0/0` through the Internet Gateway |
| Private route table | Associated with the private subnet; no public default route or NAT is configured |
| Security group | Allows inbound TCP/80 from IPv4 internet and all outbound IPv4 traffic; no SSH ingress |
| EC2 | Amazon Linux 2023, `t2.small` by default, public subnet, public IP, encrypted 16 GiB gp3 root volume |
| EC2 hardening | IMDSv2 tokens are required and the root volume is deleted on termination |
| IAM role and profile | Allows the EC2 instance to register with Systems Manager through `AmazonSSMManagedInstanceCore` |
| S3 bucket | Private bucket for temporary Ansible/SSM transfers, AES-256 server-side encryption, full public-access blocking, and one-day object expiration |

All named resources carry project, environment, and `ManagedBy = Terraform`
tags where supported.

### Pinned EC2 AMI

The EC2 resource uses `var.ec2_ami_id` directly. This intentionally pins the
Amazon Linux 2023 image so that a later public AMI update does not silently
produce a replacement plan for the instance.

An SSM public-parameter data source for the latest Amazon Linux 2023 AMI is
declared in `compute.tf`, but it is not connected to the EC2 `ami` argument.
The operator must select and provide a compatible AMI ID for `us-west-2`.

The safest repository-independent option is an environment variable:

```powershell
$env:TF_VAR_ec2_ami_id = "ami-REPLACE_WITH_VALID_AMI"
```

Do not store account credentials or sensitive values in tracked variable
files. A tracked example `.tfvars` file is not currently part of the
repository; adding a placeholder-only template is a pending documentation
improvement. Until then, use `TF_VAR_ec2_ami_id` or an ignored local
`terraform.tfvars` file.

### Terraform workflow from Windows PowerShell

Terraform uses the standard AWS credential chain. The provider does not embed a
profile or credentials, so select the restricted Terraform profile in the
shell:

```powershell
$env:AWS_PROFILE = "ticketapi-tf"
$env:TF_VAR_ec2_ami_id = "ami-REPLACE_WITH_VALID_AMI"

aws sts get-caller-identity
Set-Location .\terraform

terraform init
terraform fmt -check
terraform validate
terraform plan -out=ticket-api.tfplan
terraform show ticket-api.tfplan
terraform apply ticket-api.tfplan
```

Review the saved plan before applying it. The workflow deliberately does not
use `terraform apply -auto-approve`.

The most recently recorded infrastructure verification was:

```text
terraform validate: successful
terraform plan: No changes. Your infrastructure matches the configuration.
```

These results refer to the last verified operator run. Always repeat
`terraform validate` and review a fresh `terraform plan` before applying
infrastructure changes.

### Terraform state and current limitations

- No remote backend is declared. State remains local unless the operator
  configures an external backend.
- `.gitignore` excludes `.terraform/`, state files, plans, crash logs, and
  non-example `.tfvars` files.
- State can contain sensitive infrastructure data and must never be committed.
- Some deployer and Ansible-controller IAM permissions were configured
  manually and are not fully represented by Terraform.
- Terraform currently defines no outputs for the EC2 instance ID, public IP, or
  Ansible S3 bucket. The static Ansible inventory must therefore be updated
  manually if those resources change.

## EC2 Configuration with Ansible

Ansible runs from Ubuntu WSL as the control node. It connects to the managed EC2
instance with `amazon.aws.aws_ssm`, not SSH. The security group therefore does
not need port 22.

### Control-node requirements

- Ubuntu WSL
- Python and Ansible
- AWS CLI configured with the `ticketapi-dev` profile
- AWS Session Manager Plugin
- `amazon.aws` Ansible collection
- Boto3 and Botocore for AWS API authentication and discovery
- Access to the project S3 bucket used for temporary module transfers

Example Python and collection setup inside Ubuntu WSL:

```bash
python3 -m venv ~/.venvs/ticket-api-ansible
source ~/.venvs/ticket-api-ansible/bin/activate
python -m pip install --upgrade pip ansible-core boto3 botocore
ansible-galaxy collection install amazon.aws
```

Install AWS CLI and the Session Manager Plugin using the official AWS
instructions for the WSL distribution, then confirm the selected identity:

```bash
export AWS_PROFILE=ticketapi-dev
aws --version
session-manager-plugin
aws sts get-caller-identity
```

AWS profiles and credentials are environment-specific. A profile configured in
Windows is not automatically available inside WSL unless its AWS configuration
is explicitly shared or recreated there.

### Inventory

`ansible/Inventory/hosts.yml` contains a static host in group `ticket_api` and
defines:

- The managed EC2 instance ID as `ansible_host`
- `amazon.aws.aws_ssm` as the connection method
- Region `us-west-2`
- The private S3 transfer bucket
- AWS profile `ticketapi-dev`

The inventory contains resource identifiers but no passwords, access keys, or
SSH private keys.

### Validation and execution

Run these commands from the repository root inside Ubuntu WSL:

```bash
export AWS_PROFILE=ticketapi-dev

ansible-inventory -i ansible/Inventory/hosts.yml --graph

ansible -i ansible/Inventory/hosts.yml ticket_api \
  -m ansible.builtin.ping

ansible-playbook -i ansible/Inventory/hosts.yml \
  ansible/playbooks/setup_docker.yml --syntax-check

ansible-playbook -i ansible/Inventory/hosts.yml \
  ansible/playbooks/setup_docker.yml
```

The playbook:

1. Installs the `docker` package through Amazon Linux `dnf`.
2. Starts Docker and enables it at boot.
3. Runs `docker --version` without marking the verification as a change.
4. Displays the installed Docker version.

The recorded first run completed with:

```text
ok=5 changed=2 unreachable=0 failed=0
```

The second run completed with:

```text
changed=0 failed=0
```

This demonstrates idempotence: after the host reaches the declared state,
running the same automation again produces no unnecessary changes. Idempotence
makes infrastructure automation safer, repeatable, and suitable for recovery
or continuous delivery workflows.

The inventory graph and playbook syntax check have also been validated
successfully from Ubuntu WSL.

## Security and IAM

### Separate AWS profiles

| Profile | Used by | Responsibility |
| --- | --- | --- |
| `ticketapi-tf` | Terraform from Windows PowerShell | Assumes `TicketAPI-Terraform-Deployer` and provisions the AWS resources represented in Terraform |
| `ticketapi-dev` | Ansible from Ubuntu WSL | Starts authorized SSM sessions and accesses the dedicated Ansible transfer bucket |

Separating profiles prevents routine configuration management from inheriting
infrastructure-provisioning permissions. This follows least privilege: each
workflow receives only the permissions needed for its role.

The repository intentionally does not contain AWS access keys. The required IAM
permissions include the resource-specific EC2, VPC, IAM, S3, and SSM actions
needed by Terraform, plus SSM session and dedicated bucket access for Ansible.
Exact policies should remain scoped to this project and environment. Some of
these controller-side permissions are currently managed manually.

### Application and infrastructure security

- `.env` is ignored; `.env.example` contains placeholders only.
- `.dockerignore` excludes environment files, Git metadata, virtual
  environments, caches, and local build artifacts.
- Terraform state, plans, and real `.tfvars` files are ignored.
- JWT secrets and database passwords must be different for development and
  deployment environments.
- FastAPI runs as the non-root `appuser` in the container.
- Development ports bind to `127.0.0.1`; production-like Compose publishes only
  Nginx.
- Nginx limits API traffic to 10 requests per second per client with a burst of
  20; liveness and readiness checks are exempt.
- EC2 requires IMDSv2 and uses an encrypted gp3 root volume.
- EC2 exposes HTTP port 80 but not SSH port 22.
- The Ansible S3 bucket blocks all public access, encrypts objects with AES-256,
  and expires temporary objects after one day.
- HTTPS, managed application secrets, backup policy, centralized logs, metrics,
  and alerts are still required before treating the platform as production
  ready.

## Continuous Integration and Delivery

`.github/workflows/ci.yml` runs on pushes to `main` and `feat/**`, and on pull
requests targeting `main`.

It defines three jobs:

1. **Unit and static analysis**
   - Uses Python 3.12
   - Installs `.[test]`
   - Runs Ruff against `app` and `tests`
   - Runs Pytest while excluding `tests/integration`
2. **PostgreSQL integration**
   - Starts an isolated PostgreSQL 16 service database named
     `ticket_api_test`
   - Applies all Alembic migrations
   - Runs `tests/integration`
3. **Docker image build**
   - Runs only after both test jobs succeed
   - Builds `ticket-api:ci`

The current workflow validates code and container construction. It does not run
Terraform or Ansible, publish an image, deploy to EC2, or implement continuous
delivery. Jenkins is planned but not present in the repository.

## Deployment Status

### Implemented and verified

- Backend API, authentication, RBAC, validation, and soft deletion
- Local Docker Compose stack with Nginx and PostgreSQL
- Automated CI validation
- AWS VPC, subnets, routing, security group, EC2, IAM instance profile, Systems
  Manager integration, and private Ansible S3 bucket
- Terraform validation and no-change plan in the last recorded operator run
- Ansible inventory and SSM connectivity workflow
- Idempotent Docker Engine installation on EC2

### In development

- Install and validate Docker Compose on EC2
- Define a secure deployment-time environment configuration
- Transfer or pull the application artifacts/image
- Start the Compose application stack on EC2
- Validate the public health and readiness paths through Nginx
- Reduce manually managed IAM dependencies where practical

### Not yet implemented

- Complete production deployment of Ticket-API in AWS
- HTTPS and certificate automation
- Jenkins continuous deployment
- Prometheus and Grafana
- Centralized logging, dashboards, alerting, and broader observability
- Remote Terraform state and locking
- Automated Terraform outputs or generated Ansible inventory

## Roadmap

1. Add Docker Compose to the Amazon Linux 2023 host and deploy the existing
   Nginx/API/PostgreSQL stack with environment-specific secrets.
2. Introduce HTTPS and a production domain/ingress strategy.
3. Add a secure image publishing and Jenkins deployment workflow.
4. Add Prometheus metrics, Grafana dashboards, log aggregation, and alerts.
5. Move Terraform state to a protected remote backend with locking.
6. Bring remaining manual IAM configuration under reviewed infrastructure as
   code.
7. Add Terraform outputs and reduce static inventory maintenance.
8. Define production backup, restore, retention, and disaster-recovery
   procedures.
