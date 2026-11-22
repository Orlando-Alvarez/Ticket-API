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

The AWS Nginx configuration serves TLS 1.2/1.3 on public TCP 443. Its HTTP
listener is bound to host loopback and exposes only the readiness path; other
HTTP paths return `404`.

## Deployment Secret Management

Local development still uses an ignored `.env` file created from
`.env.example`. The AWS deployment uses four encrypted Systems Manager
Parameter Store `SecureString` parameters:

- `/ticket-api/dev/postgres-password`
- `/ticket-api/dev/jwt-secret`
- `/ticket-api/dev/cloudflare-ddns-token`
- `/ticket-api/dev/cloudflare-certbot-token`

The existing PostgreSQL password and JWT signing secret were preserved when
the parameters were created. This was a storage migration, not a credential
rotation, and the PostgreSQL volume was not recreated.

Parameter Store centralizes the encrypted source values and provides an
IAM-authorized retrieval path. It does not inject values into Docker
containers. Docker Compose still reads `/opt/ticket-api/.env`, which is a
protected host-local copy required by the current Compose design. The DDNS
token is retrieved for each synchronization and is not written to a local
credential file. The Certbot token is synchronized to a protected host file.

### AWS KMS

Terraform manages a customer-managed symmetric key and alias:

- `aws_kms_key.ticket_api_secrets`
- `aws_kms_alias.ticket_api_secrets`
- Alias `alias/ticket-api-dev-secrets` with the current default variables

The key has automatic KMS key-material rotation enabled and a 30-day deletion
window. All four `SecureString` parameters use this key for encryption.

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

### Cloudflare Credential Handling

The DDNS and certificate workflows use separate tokens with different
operational purposes:

- `cloudflare_ddns.py` retrieves its token with `WithDecryption=True` on each
  systemd run, validates that the A record is DNS-only, and changes it only
  when the IMDSv2 public IPv4 differs.
- `sync_certbot_credentials.py` retrieves the Certbot token with
  `WithDecryption=True` and atomically synchronizes
  `/etc/ticket-api/cloudflare-certbot.ini`. The directory is mode `0700` and
  the credentials file is mode `0600`.

Both scripts use the EC2 instance role rather than static AWS credentials.
They run as root, so host root compromise remains inside the trust boundary.
The tokens should be scoped to the required Cloudflare zone and DNS actions.

## AWS Identity Separation

| Identity | Current responsibility |
| --- | --- |
| `ticketapi-tf` | Assumes the Terraform deployer role |
| `ticketapi-dev` | Starts SSM sessions and accesses the Ansible transfer bucket |
| GitHub ECR publisher role | Accepts short-lived OIDC sessions only from this repository's `main` branch and pushes to its ECR repository |
| Authorized publisher profile | Supports the verified manual ECR publication fallback |
| EC2 instance role | Registers with SSM, pulls from ECR, and decrypts the four deployment secrets |

The EC2 role is named `ticket-api-dev-ec2-ssm-role` with the current defaults.
It uses AWS-managed Systems Manager core and ECR pull-only policies plus the
Terraform-managed `aws_iam_role_policy.ec2_secrets_read` inline policy. No
static AWS keys are stored on EC2.

The custom policy permits `ssm:GetParameter` and `ssm:GetParameters` only for
the four expected parameter ARNs. Its KMS statement permits `kms:Decrypt` only
for the designated key, through the regional SSM service, and for matching
parameter-ARN encryption contexts.

This does not mean every permission on the role is restricted to those four
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

### GitHub Actions Publication Trust

The workflow does not require a stored AWS access key. The ECR publication job
requests `id-token: write`, exchanges the GitHub-issued token for a short-lived
AWS role session, and authenticates to ECR. Other jobs inherit only
`contents: read`.

Terraform constrains role assumption with the OIDC audience and the exact
subject for `Orlando-Alvarez/Ticket-API` on `refs/heads/main`. The role policy
grants the registry authentication action and limits image upload operations
to the Ticket-API repository. This identity is separate from the pull-only EC2
role and the Terraform provisioning role.

The OIDC provider, dedicated role, and inline ECR policy have been applied
through Terraform and operator-verified. GitHub role assumption and automatic
publication have not yet been verified by a successful main-branch run. Until
that evidence exists, the pipeline path must not be described as operationally
verified.

Image signing, provenance attestations, vulnerability gates, and automated
promotion are not implemented.

## TLS and Certificate Handling

- Nginx terminates TLS for `api.orlandoalvarez.dev` using TLS 1.2 or 1.3.
- Let's Encrypt certificates are issued with the Cloudflare DNS-01 plugin.
- `/etc/letsencrypt` is mounted read-only into the Nginx container.
- A root-run systemd timer invokes Certbot every 12 hours; Certbot renews only
  when the certificate is due.
- The renewal service refreshes the root-only Cloudflare credentials before
  each attempt.
- The deploy hook runs `nginx -t` inside the container before reloading Nginx.

Initial certificate issuance is manual. HSTS is not configured, and Cloudflare
is DNS-only, so Cloudflare proxy, WAF, CDN, and edge-TLS protections do not
apply. TLS availability depends on the single EC2 host, its certificate files,
and the Nginx container.

## AWS Network Boundary

- EC2 resides in the public subnet and has a public IP.
- The security group accepts public TCP 443 and has no public HTTP or SSH rule.
- The security group retains unrestricted outbound IPv4 connectivity required
  for AWS APIs, ECR, package retrieval, Cloudflare, ACME, and other current
  host dependencies.
- The AWS Compose override publishes Nginx on port 443 and binds HTTP only to
  `127.0.0.1:8080`.
- PostgreSQL has no host port in the AWS merge.
- Temporary access can use SSM port forwarding.

Public HTTP and SSH are intentionally disabled. The public DNS-only record
points directly to a non-elastic EC2 address; no Application Load Balancer or
Elastic IP is present. DDNS reduces address-change downtime but cannot remove
DNS propagation delays or provide high availability. Do not expose PostgreSQL
for troubleshooting.

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
- Public Swagger and readiness responses over valid HTTPS
- Cloudflare DNS synchronization with the EC2 public IPv4 address
- Successful simulated certificate renewal and deploy-hook reload
- Enabled DDNS and certificate-renewal systemd timers

These are manual deployment checks, not proof of successful GitHub OIDC
federation, penetration-test results, compliance certifications, or automated
secret-rotation evidence.

## Infrastructure Data

- Terraform state is local.
- State, backups, plans, and populated `.tfvars` files are ignored.
- State may contain sensitive infrastructure metadata and must not be
  published.
- The static inventory and playbooks contain environment-specific resource
  identifiers; this README and the advanced documentation intentionally omit
  those values.

## Outstanding Security Work

1. Automate clean-host certificate issuance and Cloudflare token rotation.
2. Evaluate HSTS and managed ingress when availability requirements justify
   them.
3. Implement coordinated PostgreSQL and JWT secret rotation and recovery.
4. Parameterize secret paths and region, and manage the migration lifecycle
   reproducibly without storing plaintext in Terraform state.
5. Move Terraform state to an encrypted remote backend with locking.
6. Bring remaining manual IAM permissions under reviewed code.
7. Define PostgreSQL backups, restore testing, retention, and disaster
   recovery.
8. Add centralized logs, metrics, dashboards, and alerts.
9. Add automated dependency, container, deployment, and security checks.
10. Verify OIDC publication, then add image signing, provenance, and promotion
    controls.

