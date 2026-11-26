# Testing and Validation

[Back to the main README](../README.md)

Ticket-API separates fast application tests, PostgreSQL integration tests,
GitHub Actions CI and image publication, Jenkins delivery checks, and
operator-reported infrastructure and recovery tests.

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
- Runs only for `push` events on `main`, including merge commits
- Requests `id-token: write` at the job level
- Assumes a Terraform-managed AWS role through GitHub OIDC
- Authenticates to the private ECR registry
- Rebuilds and pushes `sha-<full-commit-sha>`

The OIDC trust policy limits role assumption to this repository's `main`
branch. The role can push to the Ticket-API repository. The EC2 runtime role
has pull-only ECR access. The [successful `main` run](https://github.com/Orlando-Alvarez/Ticket-API/actions/runs/44975797065)
completed all four jobs, including the OIDC, ECR login, and image push steps.

The workflow does not run Terraform or Ansible and does not deploy to EC2. It
provides Continuous Integration and a gated image-publication step, not
Continuous Deployment. See [CI/CD and Image Delivery](ci-cd.md) for the full
boundary.

## Jenkins Pipeline Validation

Use the controller's Declarative Pipeline linter from the repository root.
From Bash, set `JENKINS_USER` to your local user and enter your Jenkins API
token at the password prompt. The SCM paths are
[`Jenkinsfile`](../Jenkinsfile) and [`Jenkinsfile.rollback`](../Jenkinsfile.rollback).

```bash
for pipeline in Jenkinsfile Jenkinsfile.rollback; do
  curl --fail-with-body --user "$JENKINS_USER" \
    --form "jenkinsfile=<$pipeline" \
    http://localhost:18081/pipeline-model-converter/validate || break
done
```

Check for `Jenkinsfile successfully validated.` in the response. The linter
checks declarative syntax. AWS behavior is tested at runtime.
[Jenkins Declarative Pipeline linter](https://www.jenkins.io/doc/book/pipeline/development/#command-line-pipeline-linter)

Review each linter response. It checks the declarative structure and cannot
validate shell argument boundaries, credentials, or live AWS behavior.
Use syntax-only checks before commit. An inline copy of either current
pipeline can execute production operations if run and approved. See
[Jenkins job configuration](jenkins.md#pipeline-definitions-and-syntax-checks).

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

These are operator-run checks. The GitHub Actions run above provides separate
evidence of automated ECR publication.

The application suite does not exercise live KMS, Parameter Store,
Cloudflare, ACME, systemd, or certificate renewal. DDNS unit tests mock
external calls. Delivery preflight and verification exercise the specific
AWS and runtime paths described in [Jenkins Operations](jenkins.md).

## Operator-Verified Delivery Evidence

The following results were reported by the operator. The release identifiers
describe historical runs and do not identify the currently active release.

| Scenario | Reported result |
| --- | --- |
| Jenkins deployment | `SUCCESS` from `a4205d5de9d08e616231111c14f85ecb316d3126` to `99a45f5e7a69cf47e1c07584c0b43c8a3c65c9cd`. New digest `sha256:b4214bf194e16ae82d2b90c92fc4ab3687f394e2d19f625884ff7d86650e6f3d`. |
| Controlled rollback | `SUCCESS` from `99a45f5` to `a4205d5`. Restored digest `sha256:456b23568de3adabcbf9deef2fa178843d9043105e5284455edf8d41200dab59`. The current rollback source has a [shell caveat](jenkins.md#controlled-rollback) requiring a separate retest. |
| PostgreSQL backup | Custom archive created, catalog checked, uploaded to S3, and encryption metadata verified. |
| PostgreSQL restore | Manual restore succeeded in an isolated PostgreSQL container. |
| Shared lock | Two independent Jenkins jobs exercised serialization. One held the resource about 45 seconds and the waiting job completed in about 90 seconds. |
| Recovery inspection | WSL rollback preflight and recovery inspection were exercised. An independent Jenkins inspection produced and archived `recovery-state.json`. Recovery simulations exercised `recovery-report.txt` archival and both before- and after-initiation paths without intentionally damaging the running API. |
| Unknown release | A 40-zero `RELEASE_SHA` returned ECR `ImageNotFoundException`. Backup and deployment were skipped, Jenkins reported that deployment had not started and no application rollback was indicated, and the shared lock was released. The expected result was `FAILURE`. |

Pending coverage includes scheduled restore drills and measured RPO/RTO,
timeout and agent-loss scenarios, rollback shell regression checks, and
release/configuration compatibility under failure.

## Evidence Worth Capturing

No screenshots are currently required by the codebase. Useful authentic
portfolio evidence would include:

1. Swagger UI showing the real endpoint groups.
2. A redacted authenticated API response.
3. The successful GitHub Actions run on `main`, including the ECR job.
4. Ansible recap for the first and repeat deployment.
5. Public Swagger and readiness responses with certificate details redacted.
6. ECR repository settings showing immutable tags and scan on push, with
   account identifiers redacted.
7. Redacted `systemctl list-timers` output for DDNS and certificate renewal.

Do not include `.env` values, tokens, AWS account IDs, instance IDs, registry
hostnames, database URLs, or Terraform state in screenshots.

