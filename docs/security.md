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

## Environment Variables and Deployment Secrets

Local `.env` files are ignored and `.env.example` contains placeholders.

On first EC2 deployment, Ansible creates `/opt/ticket-api/.env` directly on the
host:

- Database and JWT secrets are generated with Python's `secrets` module.
- Secret output is suppressed with `no_log`.
- The file is root-owned with mode `0600`.
- Exclusive creation prevents silent replacement.
- Deployment fails when a PostgreSQL volume exists but its original `.env` is
  missing.

This is safer than transferring secrets from the controller, but it is still
host-local secret storage. Parameter Store or Secrets Manager integration,
rotation, recovery, and audit procedures remain pending.

## AWS Identity Separation

| Identity | Current responsibility |
| --- | --- |
| `ticketapi-tf` | Assumes the Terraform deployer role |
| `ticketapi-dev` | Starts SSM sessions and accesses the Ansible transfer bucket |
| Authorized publisher profile | Authenticates and pushes to private ECR |
| EC2 instance role | Registers with SSM and pulls from ECR |

The EC2 role uses AWS-managed Systems Manager core and ECR pull-only policies.
No static AWS keys are stored on EC2.

Some controller-side permissions were configured manually during development,
including permissions needed by Terraform to manage ECR and attach the EC2
pull policy. These permissions are not fully represented as code.

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
- The security group permits inbound HTTP/80.
- The AWS Compose override binds Nginx only to `127.0.0.1:8080`, so no
  application process currently listens publicly on host port 80.
- PostgreSQL has no host port in the AWS merge.
- Temporary access can use SSM port forwarding.

The unused HTTP security-group rule should be reviewed when HTTPS ingress is
designed. Do not expose PostgreSQL for troubleshooting.

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
2. Move deployment secrets to Parameter Store or Secrets Manager.
3. Implement credential rotation and recovery procedures.
4. Move Terraform state to an encrypted remote backend with locking.
5. Bring remaining manual IAM permissions under reviewed code.
6. Define PostgreSQL backups, restore testing, retention, and disaster
   recovery.
7. Add centralized logs, metrics, dashboards, and alerts.
8. Add automated dependency, container, deployment, and security checks.
9. Evaluate image signing and provenance after publication is automated.

