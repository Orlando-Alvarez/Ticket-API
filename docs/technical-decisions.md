# Ticket-API Engineering Decisions

[Back to the main README](../README.md)

This document records project-specific decisions and tradeoffs. It does not
claim that the selected tools are universally preferable.

## FastAPI for the HTTP API

**Decision:** Build a versioned Python REST API with FastAPI, Pydantic models,
and generated OpenAPI documentation.

**Benefits**

- Keeps request validation and response schemas close to route contracts.
- Provides dependency injection for database sessions and authentication.
- Generates Swagger UI and ReDoc from the implemented API.
- Supports focused tests through dependency overrides and `TestClient`.

**Tradeoffs**

- Authorization remains application logic that must be reviewed and tested;
  generated schemas do not enforce ownership rules.
- The current codebase has route and CRUD layers but no separate service
  layer, so new business logic must avoid bloating either boundary.

This is an explanation of the implemented architecture, not a claim that
FastAPI was historically benchmarked against every alternative.

## PostgreSQL, SQLAlchemy, and Alembic

**Decision:** Use PostgreSQL for relational persistence, SQLAlchemy 2 for ORM
and transaction access, and Alembic for versioned schema changes.

**Benefits**

- Enforces foreign keys, uniqueness, defaults, and incident constraints in the
  database as well as in API validation.
- Supports transactional, conditional soft-delete updates.
- Makes schema evolution reviewable and testable in order.
- Keeps application models portable enough for fast SQLite-backed unit tests
  while retaining PostgreSQL integration coverage.

**Tradeoffs**

- SQLite unit tests cannot prove PostgreSQL-specific behavior.
- Migration downgrade tests are destructive and require the guarded,
  disposable `ticket_api_test` database.
- The current AWS database runs in Docker on one EC2 host rather than as a
  managed, highly available service.

## Docker for Runtime Consistency

**Decision:** Package FastAPI and its dependencies in a non-root image and use
layered Docker Compose files for local, production-like, and AWS execution.

**Benefits**

- Uses the same application image for FastAPI and Alembic migrations.
- Makes startup ordering, health checks, networks, and volumes explicit.
- Reduces host-level Python dependency drift.
- Keeps environment-specific differences in reviewable overrides.

**Tradeoffs**

- Compose merge order is significant and must be validated.
- The current single-host topology does not provide rolling updates or
  automatic failover.
- A protected host-local `.env` remains part of the runtime contract.

## GitHub Actions for CI, Jenkins for CD

**Decision:** Run application tests, PostgreSQL migration and integration
tests, Docker build validation, and ECR publication in GitHub Actions.
Run approved deployment and rollback separately in Jenkins.

**Benefits**

- Gives pull requests repeatable quality gates on clean runners.
- Exercises both the fast application suite and real PostgreSQL behavior.
- Prevents the Docker build and publication jobs from running after failed
  tests.
- Keeps the workflow and its permissions reviewable with the source.
- Keeps the GitHub publisher focused on ECR and lets deployment use a
  separately scoped identity.
- Gives the Docker agent the Ansible, Python, AWS CLI, and Session Manager
  tooling used for deployment.

**Tradeoffs**

- GitHub Actions verifies the publication path. EC2 configuration, Cloudflare,
  TLS, systemd, and Ansible runtime behavior require separate checks.
- Jenkins adds controller and agent maintenance, plugin upgrades, persistent
  storage, and responsibility for AWS identity renewal and job isolation.
- A GitHub Actions-only pipeline would reduce the number of systems to operate.
  The split lets this project develop a dedicated deployment runner while
  keeping the existing CI workflow and publisher permissions focused.
- Interactive source credentials can expire during operation and remain
  accessible to processes in the agent. Workload identity renewal is planned.

See [CI and Delivery](ci-cd.md) for publication and Jenkins evidence.

## Terraform for Infrastructure Provisioning

**Decision:** Define the AWS network, EC2 host, security group, IAM attachments,
KMS key, ECR repository, and S3 transfer bucket with Terraform.

**Benefits**

- Produces a reviewable infrastructure plan.
- Makes resource relationships explicit.
- Reduces manual recreation steps.
- Provides a repeatable foundation for Ansible.

**Tradeoffs**

- Terraform state is still local.
- Some controller IAM permissions were configured manually.
- Several useful outputs are missing.
- A public AMI data source remains declared even though EC2 intentionally uses
  a pinned AMI variable.

## Ansible for Host Configuration and Deployment

**Decision:** Use Ansible after Terraform creates the host.

**Benefits**

- Separates infrastructure provisioning from operating-system and application
  configuration.
- Encodes Docker, Compose, ECR pull, and deployment steps.
- Supports repeat execution and idempotent checks.
- Avoids maintaining ad hoc shell instructions.

**Tradeoffs**

- The inventory contains a static instance ID.
- ECR registry values are environment-specific.
- The control node requires AWS and Python dependencies in the correct Ansible
  environment.
- EC2 AWS CLI is assumed rather than installed by the playbooks.
- The migration service can report a change on repeat deployment.

## AWS Systems Manager Instead of Public SSH

**Decision:** Connect with `amazon.aws.aws_ssm` and leave port 22 closed.

**Benefits**

- Avoids distributing and rotating SSH private keys.
- Uses IAM-controlled sessions.
- Supports Ansible and temporary local port forwarding.

**Tradeoffs**

- Depends on the EC2 SSM agent, instance role, controller IAM permissions,
  Session Manager Plugin, and AWS service availability.
- Ansible transfers require a dedicated S3 bucket.
- Controller dependencies include Boto3, Botocore, and CRT support.

## Amazon ECR for Image Distribution

**Decision:** Build the API image away from EC2 and distribute it through
private ECR. GitHub Actions publishes commit-derived immutable tags after
main-branch quality gates. An authorized manual publisher remains available
as a fallback.

**Benefits**

- Avoids compiling and installing Python dependencies on the deployment host.
- Separates build and runtime concerns.
- Provides private IAM-controlled distribution.
- Supports immutable tags, scanning, encryption, and lifecycle cleanup.

**Tradeoffs**

- The publication job rebuilds the image rather than promoting the artifact
  produced by the preceding Docker build job.
- An authorized identity is still required for the manual fallback.
- Scan results are not currently used as deployment gates.
- Registry hostnames should be parameterized.

## GitHub OIDC Instead of Long-Lived CI Credentials

**Decision:** Federate GitHub Actions with AWS IAM through OpenID Connect and
grant a dedicated role permission to publish only to the Ticket-API ECR
repository.

**Benefits**

- Avoids storing a long-lived AWS access key and secret access key in GitHub.
- Produces short-lived role sessions for the publication job.
- Restricts the trust subject to this repository's `main` branch.
- Keeps publication permissions separate from EC2 pull access, Ansible, and
  Terraform provisioning.
- Limits `id-token: write` to the one job that needs federation.

**Tradeoffs**

- The role ARN in the workflow is environment-specific.
- OIDC provider, IAM trust, repository policy, workflow permissions, and ECR
  configuration must remain synchronized.
- A compromised trusted main-branch workflow could publish images, so branch
  protection and review remain part of the security boundary.

The [successful `main` run](https://github.com/Orlando-Alvarez/Ticket-API/actions/runs/44975797065)
confirmed OIDC role assumption and publication. Jenkins uses a different
trust relationship and role for its local ECR metadata checks.

## Commit-Derived Tags and Digest-Pinned Runtime

**Decision:** Publish `sha-<full-commit-sha>` and deploy the selected image by
its ECR SHA-256 digest.

**Benefits**

- Connects the registry artifact to a source revision.
- Works with immutable ECR tags.
- Prevents tag movement from changing the runtime image selection.
- Keeps deployment approval separate from image publication.

**Tradeoffs**

- The operator must resolve and record the digest before deployment.
- The current workflow does not generate provenance or cryptographic
  signatures.
- Jenkins requires approval for deployment and for the separate rollback job.
  The image digest is immutable. Playbooks and runtime configuration come
  from the current SCM checkout and may represent another commit.

## Docker Compose at the Current Scale

**Decision:** Run Nginx, FastAPI, migrations, and PostgreSQL with Docker Compose
on one EC2 instance.

**Benefits**

- Reuses the local service topology.
- Keeps operational complexity proportionate to a portfolio deployment.
- Supports health dependencies, networks, volumes, and one-shot migrations.

**Tradeoffs**

- One host is a single point of failure.
- There are no rolling deployments, replica scheduling, or automatic failover.
- PostgreSQL storage is tied to the host.

## EC2, Compose, and PostgreSQL at the Current Scale

The repository uses a single EC2 host with Docker Compose and a PostgreSQL
volume. The following alternatives describe engineering trade-offs of the
current design. They do not represent historical evaluations.

| Current decision | Alternative | Consequence and limit |
| --- | --- | --- |
| EC2 with SSM | ECS | Exposes Linux host configuration and keeps the existing Ansible workflow. The operator owns OS maintenance, the Docker daemon and host recovery. |
| Docker Compose | Kubernetes | Reuses a small service graph locally and on EC2. Scaling, node scheduling and rolling replacement require a different runtime design. |
| PostgreSQL in Docker | Amazon RDS | Keeps the database lifecycle explicit and the topology portable for local use. Backups, restores, storage sizing and availability remain operator responsibilities. |

## Approved Changes and Operator-Controlled Recovery

**Context.** Updating an image can restart the workload and run Alembic
migrations on the same host that stores live data.

| Decision | Rationale and alternative | Consequence and limit |
| --- | --- | --- |
| Manual approval for both Jenkins jobs | Allows review of release identity, backup implications, and runtime intent before mutation. Unattended deployment would require stronger automated evidence. | Approval adds wait time and depends on controller authorization. |
| Separate rollback job | Rechecks the expected running image and historical target independently. A rollback nested in the deployment job would couple recovery to the failing execution. | The operator chooses when to run it. Its path-based Git guard is incomplete and the current source caveat must be reviewed. |
| Shared Jenkins lock | Serializes work on the same EC2 target across jobs. Per-job concurrency alone permits overlap between deployment and rollback. | Jobs can wait for approval while holding the lock. WSL and external automation require coordination. |
| PostgreSQL backup before a change | Creates a recovery point independent of the image release. A local dump alone remains exposed to EC2 loss. | Backups take time and disk space. S3 metadata checks complement an isolated restore test. |
| Failure diagnostics with operator decision | Captures observed state and lets the operator account for migrations and partial failures. | The job reports the evidence and leaves rollback classification to the operator. An abort or lost agent can prevent artifact collection. |
| PostgreSQL restoration as a separate operation | Preserves live writes during image rollback. Automatic restoration could discard writes and obscure partial migrations. | Restoring data requires an isolated drill and an approved plan for any production recovery. |

See [Jenkins Operations](jenkins.md) and [Disaster Recovery](disaster-recovery.md).

### Optional Kubernetes Learning Environment

**Decision:** Kubernetes is planned as an additional, optional environment for
learning and demonstrating container orchestration. Docker Compose remains the
primary local and AWS deployment strategy. A lightweight local laboratory or
temporary single-node K3s environment is preferred to control infrastructure
costs.

Kubernetes is not currently required by the application's scale, traffic, or
availability requirements and is not implemented. A future learning scope may
cover:

- Pods, Deployments, Services, and Ingress or Gateway API
- ConfigMaps and Secrets without embedding credentials in manifests
- Jobs for Alembic migrations
- Helm packaging
- Existing readiness and liveness probes
- Rolling-update and rollback demonstrations
- A local Kind or k3d laboratory
- An optional, temporary K3s deployment on AWS EC2

The AWS laboratory has an incremental spending objective below USD 10 per
month by using temporary resources. This is a cost-control target, not a
guaranteed price. Amazon EKS is not the current deployment platform or the
primary planned production target.

## PostgreSQL in Docker

**Decision:** Keep PostgreSQL in the Compose stack for local/AWS topology
consistency.

**Benefits**

- Provides the relational constraints and transactions required by users,
  tickets, incidents, and auditing.
- Keeps development and current deployment behavior aligned.
- Simplifies initial infrastructure cost and setup.

**Tradeoffs**

- Data persistence depends on a named volume on one EC2 host.
- Jenkins runs pre-change logical backups with off-host storage.
  An isolated manual restore was reported. Scheduled backups, recurring
  restore validation, replication, and automated failover are future work.
- A managed database may become appropriate when operational requirements
  justify it.

## Nginx as Reverse Proxy

**Decision:** Put Nginx in front of FastAPI.

**Benefits**

- Keeps the API container unexposed.
- Centralizes forwarding headers, timeouts, logging, and rate limiting.
- Terminates TLS 1.2/1.3 at a single controlled ingress boundary.
- Keeps internal readiness available on an EC2 loopback-only HTTP listener.

**Tradeoffs**

- Rate limiting is instance-local.
- Certificate files and the private key must exist on the EC2 host.
- There is no managed load balancer, certificate service, or high-availability
  ingress.
- HSTS is not currently configured.

## Cloudflare DNS-Only DDNS Instead of an Elastic IP or ALB

**Decision:** Publish a DNS-only Cloudflare A record and synchronize it with
the EC2 public IPv4 address through a Python systemd service. Do not provision
an Elastic IP or Application Load Balancer at the current project scale.

**Benefits**

- Keeps the public hostname stable when the automatically assigned EC2 address
  changes.
- Reads the authoritative instance address through IMDSv2 rather than an
  external IP-discovery service.
- Uses a zone-scoped token from Parameter Store through the EC2 role.
- Avoids the additional architecture and cost of an ALB for a single-host
  portfolio deployment.
- Updates only an existing, DNS-only A record and supports a no-write dry run.

**Tradeoffs**

- DNS cache expiration creates a recovery window after an address change.
- Cloudflare does not proxy, cache, filter, or terminate TLS for the API.
- The EC2 origin remains directly reachable on TCP 443.
- The timer, Cloudflare API, IMDSv2, IAM, KMS, and Parameter Store must all be
  healthy for automatic correction.
- This design does not provide load balancing, failover, or high availability.

## Let's Encrypt DNS-01 and Host-Managed Certbot

**Decision:** Issue the domain certificate with Certbot's Cloudflare DNS-01
plugin, store certificate material on EC2, and mount `/etc/letsencrypt`
read-only into Nginx.

**Benefits**

- Does not require public port 80 for ACME validation.
- Supports automatic renewal through a dedicated systemd timer.
- Refreshes the root-only Cloudflare credentials before renewal.
- Validates Nginx configuration before the deploy hook reloads the container.

**Tradeoffs**

- Initial certificate issuance is an operator-run step.
- The EC2 host stores the certificate private key and a protected local copy of
  the Certbot token.
- Availability depends on one host, Let's Encrypt, Cloudflare DNS, and the
  renewal automation.
- There is no ACM-managed termination or centralized certificate lifecycle.

## Layered Compose Files

**Decision:** Reuse a base file with ordered production and AWS overrides.

**Benefits**

- Maintains one service definition for local and AWS use.
- Keeps environment differences explicit.
- Reuses health checks, networks, and volume definitions.

**Tradeoffs**

- Override order changes the final configuration.
- The AWS merge depends on both the production and AWS overrides.
- Every merged configuration must be validated before deployment.

## Separated AWS Identities

**Decision:** Separate infrastructure provisioning, configuration management,
image publication, and runtime pull access.

**Benefits**

- Limits the blast radius of each identity.
- Prevents the EC2 runtime role from receiving push or provisioning access.
- Keeps Ansible permissions distinct from Terraform.

**Tradeoffs**

- More policies and profiles must be maintained.
- Some permissions are still configured manually.
- Missing fine-grained permissions can interrupt provisioning or deployment.

## Parameter Store and KMS for Deployment Secrets

**Decision:** Preserve the PostgreSQL and JWT credentials and store separate
Cloudflare DDNS and Certbot tokens in Parameter Store `SecureString` parameters
encrypted with a customer-managed KMS key. Retrieve them on EC2 through its
instance role.

**Benefits**

- Removes the managed source values from playbooks and controller-side files.
- Uses the EC2 instance role instead of static AWS access keys.
- Restricts the custom read policy to the four expected parameter ARNs and the
  custom decrypt policy to the project key, regional SSM service, and matching
  encryption contexts.
- Stops deployment when an existing local environment file disagrees with the
  managed values.
- Keeps the current Compose contract without giving application containers AWS
  permissions.
- Gives DDNS and Certbot separate credentials and host-side workflows.

**Tradeoffs**

- Docker Compose still needs a root-owned `0600` `.env`; Parameter Store is not
  consumed directly by the containers.
- Certbot needs a root-only local credentials file; the DDNS token is retrieved
  for each run instead of being persisted.
- The parameters and their values are not Terraform-managed. This keeps secret
  plaintext out of Terraform state but leaves the initial migration less
  reproducible.
- Parameter paths, region, database defaults, and accepted secret format are
  currently fixed in the synchronization script.
- The EC2 role has effective permissions from both the narrow custom policy
  and broader AWS-managed Systems Manager policy.
- KMS introduces a recurring key cost and API usage considerations; advanced
  Parameter Store tiers or throughput can add cost.
- KMS key-material rotation does not rotate PostgreSQL or JWT credentials.
  Coordinated application-secret rotation and recovery remain future work.

Parameter Store was selected over embedding secrets in Compose, Ansible, or
Terraform variables because it supplies encrypted centralized storage and
IAM-controlled retrieval while fitting the current EC2 deployment. The
host-side synchronization step adds operational complexity, but avoids a
larger application or container-runtime redesign at this stage.

