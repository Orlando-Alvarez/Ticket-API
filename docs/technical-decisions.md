# Infrastructure and Deployment Decisions

[Back to the main README](../README.md)

This document records project-specific decisions and tradeoffs. It does not
claim that the selected tools are universally preferable.

## Terraform for Infrastructure Provisioning

**Decision:** Define the AWS network, EC2 host, IAM attachments, ECR repository,
and S3 transfer bucket with Terraform.

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
private ECR.

**Benefits**

- Avoids compiling and installing Python dependencies on the deployment host.
- Separates build and runtime concerns.
- Provides private IAM-controlled distribution.
- Supports immutable tags, scanning, encryption, and lifecycle cleanup.

**Tradeoffs**

- Publication remains manual.
- An authorized publisher identity is required.
- Scan results are not currently used as deployment gates.
- Registry hostnames should be parameterized.

## Digest-Pinned Deployment

**Decision:** Pass `image_digest` and deploy
`<repository>@sha256:<digest>`.

**Benefits**

- Selects the exact image content.
- Prevents tag movement from changing an existing release reference.
- Makes repeat pull checks deterministic.

**Tradeoffs**

- Operators must obtain and pass the digest.
- Human-readable release metadata still depends on tags or external records.
- Automated promotion and rollback workflows do not exist.

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

Kubernetes is not currently required to demonstrate the project's intended
engineering scope. It would add operational cost without solving a verified
scale requirement. Revisit orchestration only if availability, scaling, or
multi-host requirements become concrete.

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
- Backups, restore tests, replication, upgrades, and disaster recovery are not
  automated.
- A managed database may become appropriate when operational requirements
  justify it.

## Nginx as Reverse Proxy

**Decision:** Put Nginx in front of FastAPI.

**Benefits**

- Keeps the API container unexposed.
- Centralizes forwarding headers, timeouts, logging, and rate limiting.
- Provides a future TLS ingress boundary.

**Tradeoffs**

- TLS is not configured.
- Rate limiting is instance-local.
- The AWS override currently binds Nginx only to loopback, so public access
  requires a future ingress decision.

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

## Local Bootstrap Secrets

**Decision:** Generate initial database and JWT secrets on EC2 in a root-only
file.

**Benefits**

- Avoids transferring secret values through Ansible output.
- Creates strong random values.
- Protects an existing database from silent credential replacement.

**Tradeoffs**

- Secrets remain host-local.
- Rotation, recovery, centralized audit, and controlled application access are
  not implemented.
- Parameter Store or Secrets Manager is the intended next step.

