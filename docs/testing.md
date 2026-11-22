# Testing and Validation

[Back to the main README](../README.md)

Ticket-API separates fast application tests, PostgreSQL integration tests,
Continuous Integration, configured image publication, and manual
infrastructure/deployment validation.

## Static Analysis

```bash
python -m ruff check app tests ansible/files/cloudflare_ddns.py
```

This is the scope enforced by GitHub Actions. A broader repository check is
also useful during maintenance:

```bash
python -m ruff check .
```

At the time of this documentation review, the broader command reports three
pre-existing findings in `ansible/files/sync_certbot_credentials.py`; that
file is outside the CI Ruff scope. The enforced CI command passes. This gap
should be fixed in a separate code change rather than hidden by documentation.

## Application Test Suite

```bash
python -m pytest --ignore=tests/integration -v
```

The FastAPI fixtures override the production database dependency with a shared
in-memory SQLite database. Covered behavior includes:

- User validation and password protection
- OAuth2 login and JWT success/failure cases
- Missing, invalid, expired, and malformed tokens
- Inactive and unknown users
- User admin authorization
- Ticket requester, assignee, unrelated-user, and admin policies
- Incident reporter scope, status/severity filters, and pagination
- Soft-delete authorization, auditing, visibility, and repeat handling
- Health liveness/readiness and safe database failures
- ORM relationships, constraints, defaults, and indexes
- DDNS unchanged, dry-run, apply, record-count, DNS-only, and identifier logic
  with mocked external calls

No test coverage percentage is published.

### Windows Temporary-Directory Workaround

If Pytest cannot access its shared Windows temporary directory, use a unique
base directory rather than changing assertions:

```powershell
python -m pytest --ignore=tests/integration -v `
  --basetemp "$env:TEMP\ticket-api-pytest-local"
```

Use a unique directory name when concurrent runs are possible.

## PostgreSQL Integration Tests

The integration suite:

- Requires PostgreSQL.
- Requires the database name to be exactly `ticket_api_test`.
- Inspects required tables, defaults, constraints, indexes, and foreign keys.
- Downgrades and reapplies the soft-delete migration.
- Verifies that records survive the migration round trip.
- Confirms atomic repeated deletion behavior.
- Restores the database to Alembic `head` in cleanup.

Only use an isolated disposable database.

Windows PowerShell example:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://<test-user>:<test-password>@127.0.0.1:5432/ticket_api_test"
$env:JWT_SECRET_KEY = "<test-only-secret>"

python -m alembic upgrade head
python -m pytest tests/integration -v
```

Never point these tests at development or production data.

## GitHub Actions CI

The workflow in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs
on pushes to `main` and `feat/**`, and pull requests targeting `main`.

### Unit and Static-Analysis Job

- Ubuntu runner
- Python 3.12
- Installs `.[test]`
- Runs Ruff
- Runs Pytest with `tests/integration` excluded

### PostgreSQL Integration Job

- Starts `postgres:16-alpine` as a service
- Uses an isolated database named `ticket_api_test`
- Waits for `pg_isready`
- Applies `alembic upgrade head`
- Runs `tests/integration`

### Docker Build Job

- Depends on both test jobs
- Builds `ticket-api:ci`

### ECR Publication Job

- Depends on the Docker build job
- Runs only for a direct push to `main`
- Requests `id-token: write` at the job level
- Assumes a Terraform-managed AWS role through GitHub OIDC
- Authenticates to the private ECR registry
- Rebuilds and pushes `sha-<full-commit-sha>`

The applied and operator-verified OIDC trust policy limits role assumption to
this repository's `main` branch. The role can push to the Ticket-API
repository, while the EC2 runtime role remains pull-only. Actual GitHub role
assumption and automatic publication have not yet been verified by a
successful main-branch run.

The workflow does not run Terraform or Ansible and does not deploy to EC2. It
provides Continuous Integration and a gated image-publication step, not
Continuous Deployment. See [CI/CD and Image Delivery](ci-cd.md) for the full
boundary.

## Configuration Validation

### Local Compose

```bash
docker compose -f docker-compose.yml config --quiet
```

### Production-Like Compose

```bash
docker compose \
  -f docker-compose.yml \
  -f compose.prod.yaml \
  config --quiet
```

### AWS Compose Merge

Configure `.env` and a placeholder-compatible image reference:

```powershell
$env:TICKET_API_IMAGE = "<ecr-repository-uri>@sha256:<64-hex-character-digest>"

docker compose `
  -f docker-compose.yml `
  -f compose.prod.yaml `
  -f compose.aws.yaml `
  config --quiet
```

### Ansible

```bash
ansible-inventory -i ansible/Inventory/hosts.yml --graph

ansible-playbook -i ansible/Inventory/hosts.yml \
  ansible/playbooks/setup_docker.yml --syntax-check

ansible-playbook -i ansible/Inventory/hosts.yml \
  ansible/playbooks/install_compose.yml --syntax-check

ansible-playbook -i ansible/Inventory/hosts.yml \
  ansible/playbooks/pull_ecr_image.yml --syntax-check

ansible-playbook -i ansible/Inventory/hosts.yml \
  ansible/playbooks/deploy_app.yml --syntax-check

ansible-playbook -i ansible/Inventory/hosts.yml \
  ansible/playbooks/setup_cloudflare_ddns.yml --syntax-check

ansible-playbook -i ansible/Inventory/hosts.yml \
  ansible/playbooks/setup_certbot.yml --syntax-check

ansible-playbook -i ansible/Inventory/hosts.yml \
  ansible/playbooks/setup_certbot_credentials.yml --syntax-check

ansible-playbook -i ansible/Inventory/hosts.yml \
  ansible/playbooks/setup_certbot_renewal.yml --syntax-check
```

### Terraform

See [AWS Infrastructure](aws-infrastructure.md) for the verified Windows
PowerShell syntax. Validation and planning require Terraform and authorized AWS
credentials.

## Manual Infrastructure and Deployment Validation

Operator-run validation has confirmed:

- Docker image construction for `linux/amd64`
- Image publication to private ECR
- Manual ECR pull from EC2
- Docker Engine installation and service enablement
- Docker Compose installation with architecture and checksum checks
- Idempotent Docker and Compose setup runs
- Valid syntax for all Ansible playbooks
- ECR pull playbook skipping download when the digest exists
- Terraform security hardening applied successfully and a later plan reported
  no pending changes
- KMS key enabled with automatic key-material rotation verified
- Existing credentials migrated to two encrypted Parameter Store
  `SecureString` values and compared without reporting the values
- Ansible host-side secret synchronization using the EC2 instance role
- PostgreSQL, Alembic, FastAPI, and Nginx startup on EC2
- HTTP 200 from `/api/v1/health/ready`
- Public Swagger UI and readiness responses over valid HTTPS
- Cloudflare DNS-only synchronization with the EC2 public IPv4 address
- Successful Let's Encrypt renewal simulation
- Successful Nginx validation and reload through the deploy hook
- DDNS and certificate-renewal systemd timer checks
- Successful second full deployment

The second full deployment reported `changed=1` because the one-shot Alembic
migration container ran again. It is inaccurate to describe the complete
deployment as unchanged.

These validations are not CI jobs and should not be represented as automated
release evidence. In particular, the previously verified manual ECR
publication does not prove that GitHub OIDC federation has executed
successfully.

No automated test currently exercises live KMS, Parameter Store, IAM,
Cloudflare, ACME, systemd, or certificate renewal. DDNS unit tests mock external
calls. Repository checks can validate Terraform and Ansible syntax and Python
logic statically, but live authorization, DNS propagation, TLS, and encrypted
value consistency remain operator-run checks.

## Evidence Worth Capturing

No screenshots are currently required by the codebase. Useful authentic
portfolio evidence would include:

1. Swagger UI showing the real endpoint groups.
2. A redacted authenticated API response.
3. GitHub Actions showing the three validation/build jobs passing and, after
   verification on `main`, the conditional ECR publication job.
4. Ansible recap for the first and repeat deployment.
5. Public Swagger and readiness responses with certificate details redacted.
6. ECR repository settings showing immutable tags and scan on push, with
   account identifiers redacted.
7. Redacted `systemctl list-timers` output for DDNS and certificate renewal.

Do not include `.env` values, tokens, AWS account IDs, instance IDs, registry
hostnames, database URLs, or Terraform state in screenshots.

