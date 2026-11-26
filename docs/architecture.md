# Ticket-API Architecture

[Back to the main README](../README.md)

This document describes the implemented application, container, and AWS
architecture. Planned components are identified explicitly.

## System Boundaries

Ticket-API currently has four operating contexts:

1. **Direct development:** Uvicorn and Alembic run on the host against
   PostgreSQL.
2. **Local containers:** Docker Compose builds the API image and runs
   PostgreSQL, migrations, FastAPI, and Nginx.
3. **AWS delivery and deployment:** Terraform provisions infrastructure.
   GitHub Actions publishes commit-tagged images to private ECR after the
   quality gates on `main`. Jenkins delivers an approved digest to EC2
   through Ansible and Systems Manager. Ubuntu WSL remains an operator
   alternative.
4. **Local Jenkins control plane:** A Docker controller schedules jobs on an
   inbound agent. Deployment and rollback use this agent to run Ansible.

The AWS configuration serves
`https://api.orlandoalvarez.dev`. Nginx publishes HTTPS on TCP 443 while its
HTTP listener remains bound to `127.0.0.1:8080` for readiness checks.
Cloudflare supplies DNS only; requests connect directly to EC2.

## Backend Application Architecture

```mermaid
flowchart LR
    Client[API client] --> Router[FastAPI routers<br/>/api/v1]
    Router --> Schemas[Pydantic schemas]
    Router --> Auth[JWT authentication<br/>and authorization]
    Router --> CRUD[CRUD modules]
    CRUD --> ORM[SQLAlchemy ORM]
    ORM --> DB[(PostgreSQL)]
    Alembic[Alembic migrations] --> DB
    Router -. exceptions .-> Errors[Global exception handlers]
    Errors --> Client
```

### Responsibilities

| Component | Location | Responsibility |
| --- | --- | --- |
| Application factory | `app/main.py` | Creates FastAPI, registers handlers, and mounts the versioned router |
| Router composition | `app/api/router.py` | Registers auth, health, user, ticket, and incident routers under `/api/v1` |
| Route modules | `app/api/routes/` | Define HTTP contracts and enforce current authorization rules |
| Schemas | `app/schemas/` | Validate request data and shape responses |
| CRUD modules | `app/crud/` | Execute SQLAlchemy reads and writes |
| ORM models | `app/models/` | Map users, tickets, and incidents to relational tables |
| Database session | `app/db/session.py` | Creates the engine and request-scoped SQLAlchemy sessions |
| Security | `app/core/security.py` | Hashes passwords, signs and decodes JWTs, and resolves the current user |
| Errors | `app/core/errors.py` | Normalizes application, HTTP, validation, and unexpected errors |
| Settings | `app/core/config.py` | Loads environment-backed application configuration |

The repository does not currently use a separate service layer. Business
authorization is enforced in route modules, while persistence operations live
in CRUD modules.

### Request Lifecycle

1. Nginx forwards an API request to Uvicorn/FastAPI and preserves forwarding
   headers.
2. FastAPI matches the versioned route and resolves dependencies.
3. Pydantic validates path, query, form, or JSON input before route logic runs.
4. Protected routes decode the bearer JWT, load the current user through the
   request-scoped database session, and reject inactive or unknown users.
5. The route applies its admin, owner, reporter, requester, or assignee policy.
6. A CRUD function performs the SQLAlchemy query or mutation and commits only
   the intended transaction.
7. A response schema serializes the public fields. Password hashes and
   internal credentials are never response fields.
8. Application and framework exception handlers normalize errors into the
   documented JSON envelope without returning SQL or connection details.

OpenAPI, Swagger UI, and ReDoc are generated from the same route and schema
definitions. The endpoint summary in the main README is intentionally brief;
the deployed [Swagger UI](https://api.orlandoalvarez.dev/docs) is the detailed
interactive API reference.

## Authentication and Authorization Flow

1. Public registration creates an active `requester`, regardless of privileged
   fields supplied by a client.
2. Passwords are hashed with Argon2.
3. `POST /api/v1/auth/token` validates OAuth2 form credentials.
4. Successful authentication returns an HS256 JWT containing `sub` and `exp`.
5. Protected routes resolve the active user from the token and database.
6. Route-specific policies enforce admin, ownership, reporter, requester, or
   assignee access.

There is no public admin bootstrap, refresh-token flow, or token revocation
mechanism.

## Data Model

```mermaid
erDiagram
    USER ||--o{ TICKET : requests
    USER o|--o{ TICKET : assigned_to
    USER ||--o{ INCIDENT : reports
    USER o|--o{ TICKET : deletes
    USER o|--o{ INCIDENT : deletes

    USER {
        int id PK
        string email UK
        string full_name
        string hashed_password
        string role
        boolean is_active
        datetime created_at
    }

    TICKET {
        int id PK
        string title
        text description
        string status
        string priority
        int requester_id FK
        int assignee_id FK
        datetime deleted_at
        int deleted_by_id FK
    }

    INCIDENT {
        int id PK
        string title
        text description
        string severity
        string status
        int reported_by_id FK
        datetime deleted_at
        int deleted_by_id FK
    }
```

Incident severity and status are constrained in both Pydantic and PostgreSQL.
Incident listing uses a reporter/creation/index ordering strategy and supports
status, severity, offset, and limit.

Alembic owns the PostgreSQL schema history. The migration chain creates the
initial users, tickets, and incidents tables; adds Incident constraints and
indexes; and adds audited soft-delete fields and foreign keys. Application
startup does not call SQLAlchemy metadata creation in production; the one-shot
Compose migration service applies `alembic upgrade head` before FastAPI.

## Soft Deletion

Ticket and Incident deletion is admin-only. Each CRUD function uses a
conditional SQL `UPDATE` that succeeds only while `deleted_at` is null. The
operation records a UTC timestamp and the authenticated admin ID, preventing a
repeat request from overwriting audit metadata.

Deleted rows are excluded from list, detail, and update operations. Restore,
include-deleted, and hard-delete APIs are not implemented.

## Error Handling

Application errors use a consistent envelope:

```json
{
  "error": {
    "message": "Ticket not found."
  }
}
```

Validation errors add field details. Unexpected errors and database readiness
failures return generic messages without SQL, credentials, or connection
strings.

## Local Container Architecture

```mermaid
flowchart LR
    Client[Developer or API client] -->|127.0.0.1:8080| Nginx
    Nginx -->|proxy_net: api:8000| API[FastAPI]
    API -->|data_net: db:5432| DB[(PostgreSQL 16)]
    Migrate[Alembic migration job] -->|data_net| DB
    DB --> Volume[(postgres_data volume)]
```

### Services

| Service | Role | Host exposure in the base configuration |
| --- | --- | --- |
| `db` | PostgreSQL 16 with persistent storage | `127.0.0.1:5434` |
| `migrate` | One-shot `alembic upgrade head` | None |
| `api` | Uvicorn/FastAPI | None |
| `nginx` | Reverse proxy and rate-limiting boundary | `127.0.0.1:8080` |

### Startup Dependencies

1. PostgreSQL passes `pg_isready`.
2. The migration service exits successfully.
3. FastAPI starts and passes its `/openapi.json` container healthcheck.
4. Nginx starts after the API becomes healthy.

`proxy_net` isolates Nginx-to-API traffic. `data_net` isolates API,
migration, and PostgreSQL traffic. The API joins both networks; PostgreSQL and
Nginx do not share a network.

## AWS Infrastructure Architecture

```mermaid
flowchart TB
    Terraform[Terraform<br/>ticketapi-tf] --> AWS[AWS API]
    AWS --> VPC[VPC 10.20.0.0/16]
    VPC --> Public[Public subnet<br/>10.20.1.0/24]
    VPC --> Private[Private subnet<br/>10.20.2.0/24]
    Public -->|outbound route| IGW[Internet Gateway]
    IGW --> Internet[Internet and AWS public endpoints]
    Public --> EC2[Amazon Linux 2023 EC2]
    Client[Public API client] -->|DNS lookup| Cloudflare[Cloudflare DNS-only<br/>A record]
    Cloudflare -->|EC2 public IPv4| Client
    Client -->|HTTPS 443| SG[Security group]
    SG --> EC2
    AWS --> ECR[Private Amazon ECR]
    Actions[GitHub Actions<br/>push to main] -->|OIDC token| OIDC[IAM OIDC provider]
    OIDC --> Publisher[GitHub ECR<br/>publisher role]
    Publisher -->|repository-scoped push| ECR
    Controller[Local Jenkins controller] -->|"WebSocket"| Agent[Jenkins Docker agent]
    Agent -->|"Assume role and check identity"| STS[AWS STS]
    STS --> JenkinsRole[Jenkins development role]
    JenkinsRole -->|"ECR metadata read"| ECR
    JenkinsRole -->|"Scoped managed sessions"| SSM[AWS Systems Manager]
    JenkinsRole -->|"Temporary modules and files"| S3[S3 transfer bucket]
    AWS --> Parameters[Parameter Store<br/>SecureString]
    AWS --> KMS[Customer-managed KMS key]
    Parameters -->|encrypted with| KMS
    EC2 --> Profile[IAM instance profile]
    Profile -->|"Registers managed instance"| SSM
    Profile -->|pull only| ECR
    Profile -->|scoped read and decrypt| Parameters
    Profile -->|"Backup object write and read"| Backup[S3 PostgreSQL backup bucket]
    ManualAnsible["Manual Ansible in Ubuntu WSL<br/>ticketapi-dev"] --> SSM
    SSM -->|"Managed session"| EC2
    ManualAnsible -->|"Temporary modules and files"| S3
    EC2 --> DDNS[DDNS systemd service]
    IMDS[IMDSv2] -->|public IPv4| DDNS
    DDNS -->|update A record| Cloudflare
```

The EC2 instance has a public but non-elastic IPv4 address. Its security group
accepts public TCP 443 and has no public HTTP or SSH rule. Unrestricted outbound
IPv4 connectivity supports AWS APIs, ECR, package retrieval, Cloudflare, and
ACME operations. The private subnet exists without a NAT gateway and currently
hosts no workload. No Application Load Balancer or Elastic IP is provisioned.

## AWS Image and Deployment Flow

```mermaid
flowchart LR
    Change[Push to main] --> CI[GitHub Actions quality gates]
    CI --> OIDC[OIDC role assumption]
    OIDC -->|build and push<br/>sha-commit tag| ECR[Private ECR<br/>immutable tag]
    Jenkins[Jenkins Docker agent] -->|"Resolve commit tag to digest"| ECR
    Operator[Operator] -->|"Approve deployment or rollback"| Jenkins
    Operator -->|"Manual alternative"| ManualAnsible["Ansible in Ubuntu WSL"]
    Jenkins --> JenkinsAnsible["Ansible inside ticket-api-cd-agent"]
    ECR -->|"EC2 pulls selected digest"| Image[Local image on EC2]
    ManualAnsible --> SSM[AWS Systems Manager]
    JenkinsAnsible --> SSM
    SSM --> Deploy[Preflight, backup and deployment on EC2]
    Deploy --> Sync[Host-side Boto3<br/>secret synchronization]
    Role[EC2 IAM role] --> Parameters[Parameter Store<br/>SecureString]
    Parameters -->|KMS decryption| Sync
    Sync --> Env[Root-only .env]
    Parameters --> CloudTokens[DDNS and Certbot tokens]
    CloudTokens --> TLS[Host DDNS and Certbot automation]
    TLS --> Certs[Let's Encrypt certificates]
    Image --> API[FastAPI]
    Image --> Migrate[Alembic]
    Deploy --> Compose[Docker Compose]
    Env --> Compose
    Compose --> Nginx[Nginx<br/>HTTPS 443 and loopback HTTP]
    Certs -->|read-only mount| Nginx
    Compose --> API
    Compose --> Migrate
    Compose --> DB[(PostgreSQL volume)]
    Nginx --> API
    API --> DB
    Migrate --> DB
    DB -->|"Logical backup before changes"| Backups[(S3 backup bucket)]
```

The workflow requests permission to mint an OIDC token only in the ECR
publication job. AWS accepts the role session only for this repository's
`main` branch, and the resulting policy can publish to the Ticket-API
repository. The job rebuilds the image and publishes `sha-${GITHUB_SHA}`
after both test jobs and the Docker build succeed. A successful
[`main` run](https://github.com/Orlando-Alvarez/Ticket-API/actions/runs/44975797065)
confirmed role assumption and image publication.

Jenkins runs Ansible inside `ticket-api-cd-agent`. The operator can also run
the playbooks from Ubuntu WSL. Both use Systems Manager. Jenkins adds
approval, a shared lock across deployment and rollback, backup, and final
verification. Ansible copies Compose, Nginx, and synchronization files from
its current checkout, which can differ from the selected image's commit.

The API and migration services use the same ECR image. The image is pulled
before Compose runs and is selected through
`TICKET_API_IMAGE=<repository>@sha256:<digest>`. Compose does not build or pull
the application image on EC2. Before Compose starts, the host-side script uses
the EC2 role to retrieve and decrypt the two application parameters, validates any
existing `.env`, and reconstructs it only when absent. Containers read the
local file; they do not access Parameter Store directly. Separate host-side
automation retrieves the Cloudflare tokens, synchronizes DNS, renews the
certificate, and reloads Nginx only after configuration validation.

## Failure Domains and Planned Work

EC2 hosts the reverse proxy, API and PostgreSQL on one origin. An instance,
disk, or Docker outage can affect the request path and local data together.
S3 retains logical dumps independently. The transfer bucket serves Ansible
sessions. ECR or SSM failure can prevent a release while the current runtime
continues serving. Jenkins controller, agent, or credential loss affects
the delivery control plane.

The approved rollback job exchanges application images and keeps the live
PostgreSQL volume and migration history. A deployment failure after Ansible
starts triggers best-effort state collection for operator review. See
[Disaster Recovery](disaster-recovery.md) and [Backup and Restore](backup-and-restore.md).

Planned work includes:

- Automated clean-host certificate bootstrap
- Automated PostgreSQL and JWT secret rotation
- Build-once artifact promotion and release-aligned deployment configuration
- Centralized metrics, logs, dashboards, and alerts
- Remote Terraform state and locking
- Scheduled backups, recurring restore drills, and measured recovery objectives
- Multi-host scheduling or high availability

The current public deployment is a single EC2 origin using a DNS-only record.
Cloudflare proxying, a load balancer, an Elastic IP, and managed certificate
termination are not part of the architecture.

