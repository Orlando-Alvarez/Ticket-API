# Security Model and Limitations

[Back to the main README](../README.md)

Ticket-API implements several practical security controls, but the current AWS
deployment is not presented as production-ready. This document separates
implemented controls from remaining work.

## Application Security

### Passwords

- Public registration requires a password of 8–128 characters.
- Passwords are hashed with pwdlib's recommended Argon2 implementation.
- Plain-text passwords and hashes are not included in API responses.

### JWT Authentication

- Tokens use HS256.
- `sub` contains the numeric user ID as a string.
- `exp` is required.
- Access tokens expire after 30 minutes by default.
- Missing, malformed, invalid-signature, expired, or unknown-user tokens return
  `401 Unauthorized`.
- Inactive users cannot authenticate or access protected endpoints.

Refresh tokens, revocation, key rotation, and session management are not
implemented.

### Authorization

- New public registrations always become active `requester` users.
- User administration is admin-only.
- Non-admin ticket access requires requester or assignee relationship.
- Ticket relationship changes and deletion are admin-only.
- Incident reporters are derived from the authenticated user.
- Non-admin users see only their own incidents and cannot change Incident
  status.
- Incident status changes and deletion are admin-only.

### Validation and Errors

- Pydantic rejects invalid email, length, enum, pagination, null, and unknown
  field inputs where configured.
- PostgreSQL enforces Incident status and severity constraints.
- Global exception handlers return consistent JSON envelopes.
- Unexpected failures and readiness database errors do not expose SQL,
  credentials, connection URLs, or exception details.

## Soft-Delete Integrity

Ticket and Incident soft deletion uses conditional updates requiring
`deleted_at IS NULL`. This makes repeated deletion return not found and
prevents audit timestamp or actor information from being overwritten.

Soft-deleted records remain in PostgreSQL but are hidden from active API
queries. Retention, restoration, and hard deletion policies are not yet
defined.

## Container Security

- The application image runs as the non-root `appuser`.
- `.dockerignore` excludes `.env`, Git metadata, virtual environments, caches,
  and local build artifacts.
- The API does not publish a host port directly.
- Nginx and PostgreSQL do not share a Docker network.
- PostgreSQL is not published in the production-like or AWS merge.
- Nginx applies per-client rate limiting and sends operational logs to standard
  output/error.
- Liveness and readiness endpoints are exempt from rate limiting.

The current Nginx configuration serves HTTP only.

## Deployment Secret Management

Local development still uses an ignored `.env` file created from
`.env.example`. The AWS deployment uses two encrypted Systems Manager Parameter
Store `SecureString` parameters:

- `/ticket-api/dev/postgres-password`
- `/ticket-api/dev/jwt-secret`

The existing PostgreSQL password and JWT signing secret were preserved when
the parameters were created. This was a storage migration, not a credential
rotation, and the PostgreSQL volume was not recreated.

Parameter Store centralizes the encrypted source values and provides an
IAM-authorized retrieval path. It does not inject values into Docker
containers. Docker Compose still reads `/opt/ticket-api/.env`, which is a
protected host-local copy required by the current Compose design.

### AWS KMS

Terraform manages a customer-managed symmetric key and alias:

- `aws_kms_key.ticket_api_secrets`
- `aws_kms_alias.ticket_api_secrets`
- Alias `alias/ticket-api-dev-secrets` with the current default variables

The key has automatic KMS key-material rotation enabled and a 30-day deletion
window. The two `SecureString` parameters use this key for encryption.

KMS key rotation changes the backing cryptographic material used by AWS. It
does **not** change the PostgreSQL password, replace the JWT signing secret, or
invalidate existing JWTs. Application-secret rotation requires a separately
designed, coordinated operational procedure.

### Host-Side Synchronization

`ansible/files/sync_ssm_secrets.py` runs as root on EC2 before Compose starts:

1. Boto3 uses the EC2 instance role; no static AWS keys are placed on EC2.
2. The script requests each parameter with `WithDecryption=True`.
3. It rejects parameters that are not `SecureString` and values outside its
   restricted character set.
4. If `.env` exists, it compares both secrets and the expected database name
   and user. Any mismatch stops deployment instead of replacing credentials.
5. If `.env` is absent, it reconstructs the expected file with exclusive,
   no-follow creation and mode `0600`.
6. Ansible enforces root ownership and mode `0600`, suppresses synchronization
   output with `no_log`, and validates Compose before starting the stack.

The script also rejects a symlink, a non-regular environment path, and
duplicate keys in an existing file. These checks protect against accidental
replacement; they are not a general-purpose secret-rotation mechanism.

Current limitations include hard-coded development parameter paths, region,
database defaults, and environment-file location. Secret values must match
`[A-Za-z0-9_-]+`. The parameters themselves are not declared as Terraform
`aws_ssm_parameter` resources, so their secure values do not enter Terraform
state, but creation and migration are not fully reproducible from this
repository.

## AWS Identity Separation

| Identity | Current responsibility |
| --- | --- |
| `ticketapi-tf` | Assumes the Terraform deployer role |
| `ticketapi-dev` | Starts SSM sessions and accesses the Ansible transfer bucket |
| Authorized publisher profile | Authenticates and pushes to private ECR |
| EC2 instance role | Registers with SSM, pulls from ECR, and decrypts the two deployment secrets |

The EC2 role is named `ticket-api-dev-ec2-ssm-role` with the current defaults.
It uses AWS-managed Systems Manager core and ECR pull-only policies plus the
Terraform-managed `aws_iam_role_policy.ec2_secrets_read` inline policy. No
static AWS keys are stored on EC2.

The custom policy permits `ssm:GetParameter` and `ssm:GetParameters` only for
the two expected parameter ARNs. Its KMS statement permits `kms:Decrypt` only
for the designated key, through the regional SSM service, and for matching
parameter-ARN encryption contexts.

This does not mean every permission on the role is restricted to those two
parameter ARNs. In particular, the AWS-managed
`AmazonSSMManagedInstanceCore` policy has its own broader SSM-related
permissions required for managed-instance operation. Effective permissions
must be assessed across all attached and inline policies.

Temporary `ssm:PutParameter` and `kms:Encrypt` permissions were used for the
initial migration and removed from the custom EC2 secrets policy afterward.

The Terraform controller assumes `TicketAPI-Terraform-Deployer`, whose
manually bootstrapped permissions include KMS lifecycle, rotation inspection,
inline-role-policy, ECR, and IAM-attachment capabilities required by the
current root module. These provisioning permissions are distinct from EC2
runtime access and are not fully represented as code. See
[AWS Infrastructure](aws-infrastructure.md#terraform-controller-bootstrap) for
the reproducibility limitation and hardening direction.

## Systems Manager Instead of SSH

- The security group does not permit port 22.
- Ansible uses `amazon.aws.aws_ssm`.
- Session Manager provides authenticated, IAM-controlled remote access.
- The private S3 bucket transfers temporary Ansible modules and files.
- Temporary bucket objects expire after one day.

The controller still depends on correctly scoped IAM permissions, AWS CLI,
Session Manager Plugin, Boto3, Botocore, and CRT authentication support.

## Amazon ECR

- The repository is private.
- Tags are immutable.
- Basic scanning runs on push.
- Images use AES-256 server-side encryption.
- A lifecycle policy keeps the 10 most recent images.
- Deployments select an exact SHA-256 digest.
- EC2 receives pull-only access.

Image signing, provenance attestations, vulnerability gates, and automated
promotion are not implemented.

## AWS Network Boundary

- EC2 resides in the public subnet and has a public IP.
- The security group has no ingress-rule resources: neither HTTP nor SSH is
  accepted from the internet.
- The security group retains unrestricted outbound IPv4 connectivity required
  for AWS APIs, ECR, package retrieval, and other current host dependencies.
- The AWS Compose override binds Nginx only to `127.0.0.1:8080`.
- PostgreSQL has no host port in the AWS merge.
- Temporary access can use SSM port forwarding.

Public HTTP access is intentionally disabled. HTTPS, a custom domain, and a
controlled public ingress path are not implemented. A public IP and outbound
internet route remain, so this boundary alone does not make the environment
production-ready. Do not expose PostgreSQL for troubleshooting.

## Manually Validated Controls

Operator-run checks have confirmed:

- Terraform validation and successful application of the hardening changes
- A subsequent Terraform plan with no pending changes
- An enabled KMS key with automatic key-material rotation
- Migration of both existing credentials to encrypted `SecureString`
  parameters without intentional credential rotation
- Comparison of Parameter Store values with the protected EC2 environment
- Ansible deployment using the existing ECR image and the EC2 instance role
- Docker Compose startup and database readiness through Nginx

These are manual deployment checks, not GitHub Actions jobs, penetration-test
results, compliance certifications, or automated secret-rotation evidence.

## Infrastructure Data

- Terraform state is local.
- State, backups, plans, and populated `.tfvars` files are ignored.
- State may contain sensitive infrastructure metadata and must not be
  published.
- The static inventory and playbooks contain environment-specific resource
  identifiers; this README and the advanced documentation intentionally omit
  those values.

## Outstanding Security Work

1. Add HTTPS and certificate automation before public exposure.
2. Implement coordinated PostgreSQL and JWT secret rotation and recovery.
3. Parameterize secret paths and region, and manage the migration lifecycle
   reproducibly without storing plaintext in Terraform state.
4. Move Terraform state to an encrypted remote backend with locking.
5. Bring remaining manual IAM permissions under reviewed code.
6. Define PostgreSQL backups, restore testing, retention, and disaster
   recovery.
7. Add centralized logs, metrics, dashboards, and alerts.
8. Add automated dependency, container, deployment, and security checks.
9. Evaluate image signing and provenance after publication is automated.

