# AWS Image Publication and Deployment

[Back to the main README](../README.md)

This runbook covers the implemented manual image-publication and
Ansible-deployment workflow. It does not represent continuous delivery.

## Current Deployment Boundary

- The API image is stored in private Amazon ECR.
- EC2 pulls a specific SHA-256 digest through its instance role.
- Ansible connects through AWS Systems Manager, not SSH.
- KMS-encrypted application secrets are retrieved from Parameter Store by the
  EC2 instance role during deployment.
- Docker Compose runs PostgreSQL, migrations, FastAPI, and Nginx.
- Readiness has been verified with HTTP 200.
- Nginx is bound to `127.0.0.1:8080` on EC2.
- HTTPS and public application exposure are not implemented.

## Compose File Layering

| File | Responsibility |
| --- | --- |
| `docker-compose.yml` | Base services, local builds, networks, volume, health checks, and development ports |
| `compose.prod.yaml` | Forces debug off, removes PostgreSQL host exposure, and publishes Nginx on port 80 |
| `compose.aws.yaml` | Replaces API builds with the ECR image, disables Compose pulls, and rebinds Nginx to loopback port 8080 |

The AWS merge requires a valid deployment `.env` containing the PostgreSQL and
JWT variables consumed by the base Compose file. On EC2, Ansible creates or
validates `/opt/ticket-api/.env` before this configuration check. Do not copy
secret values into the command line or documentation.

From `/opt/ticket-api`, set the exact ECR image reference before validating the
files:

```bash
export TICKET_API_IMAGE="<ecr-repository-uri>@sha256:<64-hex-character-digest>"

docker compose \
  -f docker-compose.yml \
  -f compose.prod.yaml \
  -f compose.aws.yaml \
  config --quiet
```

`compose.aws.yaml` wins the final Nginx port override. PostgreSQL remains
unpublished because `compose.prod.yaml` resets its host ports.

Replace both placeholders with the real repository URI and a valid lowercase
64-character SHA-256 digest. The application and migration services use
`pull_policy: never`, so that exact image must already exist in the EC2 Docker
image store.

## Publish the API Image to ECR

### Prerequisites

- Docker Buildx
- AWS CLI
- Terraform output `ecr_repository_url`
- An AWS profile with scoped ECR push permissions
- A unique image tag because ECR tags are immutable

The EC2 role is pull-only and must not be used as a publishing identity.

### Windows PowerShell Workflow

Run from the repository root:

```powershell
$Region = "us-west-2"
$PublisherProfile = "<authorized-publisher-profile>"
$ImageTag = "<unique-version-or-commit>"
$RepositoryUri = terraform -chdir=terraform output -raw ecr_repository_url
$Registry = ($RepositoryUri -split '/')[0]
```

Authenticate through `cmd /c`:

```powershell
cmd /c "aws ecr get-login-password --region $Region --profile $PublisherProfile | docker login --username AWS --password-stdin $Registry"
```

This form is intentional. In the verified Windows environment, piping the AWS
CLI command directly through PowerShell produced `400 Bad Request`; executing
the complete pipe through `cmd /c` worked correctly.

Build for the EC2 `x86_64` architecture and push:

```powershell
docker buildx build `
  --platform linux/amd64 `
  --tag "${RepositoryUri}:${ImageTag}" `
  --push `
  .
```

Resolve the immutable digest:

```powershell
$ImageDigest = aws ecr describe-images `
  --repository-name ticket-api `
  --image-ids "imageTag=$ImageTag" `
  --query "imageDetails[0].imageDigest" `
  --output text `
  --region $Region `
  --profile $PublisherProfile

$ImageDigest
```

The tag records human-readable release context. The digest selects the exact
artifact deployed.

Log out when publication work is complete:

```powershell
docker logout $Registry
```

## Ansible Control Node

The verified controller is Ubuntu WSL.

### Required Tools

- Ansible installed with `pipx`
- AWS CLI
- AWS Session Manager Plugin
- `amazon.aws` collection
- `community.docker` collection
- Boto3
- Botocore with CRT support

Install dependencies into the same `pipx` environment as Ansible:

```bash
pipx install ansible
pipx runpip ansible install boto3 'botocore[crt]'
ansible-galaxy collection install amazon.aws community.docker
```

The verified environment specifically required:

```bash
pipx runpip ansible install 'botocore[crt]'
```

Do not install these packages with the system `pip` when the Ansible executable
comes from `pipx`; they would be installed into different Python environments.

As an alternative, install Ansible and all Python dependencies in one dedicated
virtual environment.

### Validate Identity and Connectivity

```bash
export AWS_PROFILE=ticketapi-dev
aws sts get-caller-identity

ansible-inventory \
  -i ansible/Inventory/hosts.yml \
  --graph

ansible \
  -i ansible/Inventory/hosts.yml \
  ticket_api \
  -m ansible.builtin.ping
```

The inventory uses `amazon.aws.aws_ssm`, region `us-west-2`, the dedicated
Ansible transfer bucket, and a static EC2 instance ID.

## Validate Playbooks

Run from the repository root in Ubuntu WSL:

```bash
ansible-playbook -i ansible/Inventory/hosts.yml \
  ansible/playbooks/setup_docker.yml --syntax-check

ansible-playbook -i ansible/Inventory/hosts.yml \
  ansible/playbooks/install_compose.yml --syntax-check

ansible-playbook -i ansible/Inventory/hosts.yml \
  ansible/playbooks/pull_ecr_image.yml --syntax-check

ansible-playbook -i ansible/Inventory/hosts.yml \
  ansible/playbooks/deploy_app.yml --syntax-check
```

## Configure the EC2 Host

Install and enable Docker Engine:

```bash
ansible-playbook \
  -i ansible/Inventory/hosts.yml \
  ansible/playbooks/setup_docker.yml
```

Install the checksum-verified Docker Compose CLI plugin:

```bash
ansible-playbook \
  -i ansible/Inventory/hosts.yml \
  ansible/playbooks/install_compose.yml
```

The playbook validates `x86_64`, installs Compose `v2.39.4` under
`/usr/local/lib/docker/cli-plugins`, and verifies `docker compose version`.

The EC2 host also needs AWS CLI for ECR login. The current host satisfied that
prerequisite during operator verification; the playbooks do not install it.

## Validate ECR Pull Independently

```bash
export IMAGE_DIGEST="sha256:<64-hex-character-digest>"

ansible-playbook \
  -i ansible/Inventory/hosts.yml \
  ansible/playbooks/pull_ecr_image.yml \
  -e "image_digest=${IMAGE_DIGEST}"
```

The playbook:

1. Validates the digest format.
2. Inspects the local Docker image store.
3. Authenticates and pulls only when the exact digest is missing.
4. Hides login output.
5. Logs out from ECR.
6. Verifies the local image.

When the digest already exists, authentication and download are skipped.

## Deploy Ticket-API

```bash
ansible-playbook \
  -i ansible/Inventory/hosts.yml \
  ansible/playbooks/deploy_app.yml \
  -e "image_digest=${IMAGE_DIGEST}"
```

`deploy_app.yml` imports `pull_ecr_image.yml`, so a separate pull is not
required for normal deployment.

The deployment:

1. Creates `/opt/ticket-api` and `/opt/ticket-api/nginx`.
2. Copies the three Compose files and Nginx configuration.
3. Creates a dedicated Python virtual environment, installs Boto3, and copies
   `ansible/files/sync_ssm_secrets.py` with mode `0700`.
4. Runs the script on EC2 under privilege escalation. Boto3 uses the EC2
   instance role and requests both `SecureString` parameters with
   `WithDecryption=True`.
5. If `/opt/ticket-api/.env` exists, compares its PostgreSQL password, JWT
   secret, database user, and database name with the expected values.
6. Refuses to overwrite the file when credentials or database settings do not
   match. This protects the existing PostgreSQL volume from an accidental
   password replacement.
7. If `.env` is absent, reconstructs it from Parameter Store and fixed
   deployment defaults using exclusive, no-follow creation.
8. Enforces root ownership and mode `0600` on `.env`.
9. Validates the merged Compose configuration without logging environment
   values.
10. Starts the stack without building or pulling through Compose.
11. Retries `/api/v1/health/ready` until it returns HTTP 200.

The synchronization occurs on the EC2 host; the application and PostgreSQL
containers do not call Parameter Store. Docker Compose continues to consume a
protected local `.env` copy. The playbook applies `no_log` to the secret task,
so decrypted values are not included in normal Ansible output.

The script rejects non-`SecureString` parameters, unexpected secret
characters, symlink or non-file environment paths, duplicate environment keys,
and credential mismatches. Its paths, region, database defaults, and accepted
secret character set are currently development-specific. It validates
consistency but does not rotate credentials.

## Validate Secret Infrastructure Without Printing Values

The following commands inspect metadata only. They do not request decrypted
parameter values.

Check the KMS key state and automatic rotation:

```bash
aws kms describe-key \
  --key-id alias/ticket-api-dev-secrets \
  --query 'KeyMetadata.{KeyState:KeyState,Enabled:Enabled,KeyManager:KeyManager}'

aws kms get-key-rotation-status \
  --key-id alias/ticket-api-dev-secrets \
  --query 'KeyRotationEnabled'
```

Check Parameter Store metadata:

```bash
aws ssm describe-parameters \
  --parameter-filters \
    'Key=Name,Option=BeginsWith,Values=/ticket-api/dev/' \
  --query 'Parameters[].{Name:Name,Type:Type,Tier:Tier,KeyId:KeyId}'
```

Check local file ownership and mode through Ansible without reading content:

```bash
ansible \
  -i ansible/Inventory/hosts.yml \
  ticket_api \
  --become \
  -m ansible.builtin.command \
  -a "stat -c '%U:%G %a %n' /opt/ticket-api/.env"
```

Expected metadata is a regular root-owned file with mode `600`. Never use
`cat`, shell tracing, `GetParameter --with-decryption`, or Ansible debug output
to troubleshoot secret values.

### Synchronization Failure Checklist

If deployment stops during secret synchronization:

1. Confirm the EC2 role contains the custom secret-read policy in addition to
   its Systems Manager and ECR attachments.
2. Confirm both parameter names and their `SecureString` type using metadata
   commands only.
3. Confirm the KMS key is enabled and its alias resolves.
4. Confirm `/opt/ticket-api/.env` is a root-owned regular file, not a symlink.
5. Treat a mismatch as an operational incident. Determine which credential is
   authoritative before changing either store; do not delete `.env` to bypass
   the guard.

## Secure Temporary Access with SSM Port Forwarding

The current AWS deployment is not publicly exposed. From Windows PowerShell,
forward a local port to Nginx on the managed EC2 instance:

```powershell
aws ssm start-session `
  --target "<ec2-instance-id>" `
  --document-name "AWS-StartPortForwardingSession" `
  --parameters '{"portNumber":["8080"],"localPortNumber":["18080"]}' `
  --region "us-west-2" `
  --profile "ticketapi-dev"
```

Keep the session open, then use:

- Swagger UI: <http://127.0.0.1:18080/docs>
- Liveness: <http://127.0.0.1:18080/api/v1/health>
- Readiness: <http://127.0.0.1:18080/api/v1/health/ready>

This forwards only the Nginx port. Do not expose PostgreSQL or copy deployment
credentials to a client machine for testing.

## Verified Operator Results

The following manual validations have been reported successfully:

- Docker Engine `25.0.14` installed and enabled
- Docker Compose `v2.39.4` installed with architecture and checksum validation
- First Docker setup run: `ok=5`, `changed=2`, `failed=0`
- Second Docker setup run: `changed=0`, `failed=0`
- First Compose setup run: `ok=6`, `changed=2`, `failed=0`, `unreachable=0`
- Second Compose setup run: `ok=6`, `changed=0`, `failed=0`, `unreachable=0`
- Image published successfully to ECR
- Image pulled manually from EC2
- ECR pull playbook unchanged when the digest already existed
- Terraform validation and successful security-hardening application
- A subsequent Terraform plan reporting no pending changes
- KMS key enabled with automatic key-material rotation verified
- Both application secrets migrated as encrypted `SecureString` parameters
  and compared with the existing protected values
- Ansible deployment synchronized secrets while reusing the existing ECR image
- PostgreSQL, migrations, FastAPI, and Nginx deployed successfully
- Readiness returned HTTP 200
- Second full deployment succeeded with `changed=1`

The second full deployment was not completely unchanged because the one-shot
Alembic migration container ran again. Other idempotent tasks skipped work when
their desired state was already satisfied.

These are operator-run validations, not GitHub Actions results.

## Current Deployment Limitations

- Publication and deployment are manual.
- ECR registry values are environment-specific in the current playbooks.
- The inventory uses a static EC2 instance ID.
- Nginx is loopback-only and does not terminate TLS.
- Parameter Store is the encrypted source for application secrets, but Docker
  Compose still requires a root-only local `.env` copy.
- Secret synchronization is environment-specific and rotation is not
  automated.
- PostgreSQL uses a host-bound Docker volume without automated backups.
- No automated rollback, release promotion, monitoring, or alerting exists.

