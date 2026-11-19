# Testing and Validation

[Back to the main README](../README.md)

Ticket-API separates fast application tests, PostgreSQL integration tests,
Continuous Integration, and manual infrastructure/deployment validation.

## Static Analysis

```bash
python -m ruff check .
```

GitHub Actions scopes Ruff to `app` and `tests`:

```bash
python -m ruff check app tests
```

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

The workflow does not publish to ECR, run Terraform or Ansible, or deploy to
AWS. It is Continuous Integration, not Continuous Deployment.

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
- Successful second full deployment

The second full deployment reported `changed=1` because the one-shot Alembic
migration container ran again. It is inaccurate to describe the complete
deployment as unchanged.

These validations are not CI jobs and should not be represented as automated
release evidence.

No automated test currently exercises live KMS, Parameter Store, IAM, or
secret-migration behavior. Repository checks can validate Terraform syntax,
Ansible syntax, and the Python synchronization script statically, but live AWS
authorization and encrypted-value consistency remain operator-run checks.

## Evidence Worth Capturing

No screenshots are currently required by the codebase. Useful authentic
portfolio evidence would include:

1. Swagger UI showing the real endpoint groups.
2. A redacted authenticated API response.
3. GitHub Actions showing all three CI jobs passing.
4. Ansible recap for the first and repeat deployment.
5. An SSM-forwarded readiness response from EC2.
6. ECR repository settings showing immutable tags and scan on push, with
   account identifiers redacted.

Do not include `.env` values, tokens, AWS account IDs, instance IDs, registry
hostnames, database URLs, or Terraform state in screenshots.

