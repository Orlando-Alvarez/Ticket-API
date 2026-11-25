# AWS Infrastructure with Terraform

[Back to the main README](../README.md)

Terraform provisions the AWS foundation in `us-west-2`. Ansible is responsible
for operating-system configuration and application deployment after the
infrastructure exists.

## Tooling

- Terraform `>= 1.17.0, < 2.0.0`
- AWS provider constrained to `~> 6.0`
- Provider version `6.73.0` in `.terraform.lock.hcl`
- AWS CLI
- Restricted Terraform profile `ticketapi-tf`

The provider uses the standard AWS credential chain; credentials and profile
names are not embedded in Terraform.

## Terraform Resource Inventory

The table describes the resources represented by the current Terraform root
module. The baseline network, compute, runtime IAM, KMS, Parameter Store, ECR,
and S3 design has operator-reported deployment evidence. The GitHub OIDC
provider, dedicated publisher role, and inline ECR policy have also been
applied through Terraform and operator-verified. The GitHub Actions workflow
has successfully assumed the role and published an image on `main`.

| Resource | Implemented configuration |
| --- | --- |
| VPC | `10.20.0.0/16`, DNS support and hostnames enabled |
| Public subnet | `10.20.1.0/24` in `us-west-2a`, public IP assignment enabled |
| Private subnet | `10.20.2.0/24` in `us-west-2a`, no public IP assignment |
| Internet Gateway | Attached to the VPC |
| Public route table | `0.0.0.0/0` through the Internet Gateway |
| Private route table | No public default route or NAT gateway |
| Security group | Public TCP 443 ingress, no HTTP/SSH ingress, unrestricted outbound IPv4 connectivity |
| EC2 | Amazon Linux 2023, `t2.small` default, public subnet, public IP |
| Root storage | Encrypted 16 GiB gp3, deleted on instance termination |
| Instance metadata | IMDSv2 tokens required |
| IAM role/profile | Systems Manager core, pull-only ECR, and scoped secret-read access |
| AWS KMS | Customer-managed symmetric key, automatic key-material rotation, alias, and 30-day deletion window |
| Parameter Store | Four KMS-encrypted `SecureString` values for the application, DDNS, and Certbot |
| Amazon ECR | Private repository, immutable tags, scan on push, AES-256 encryption |
| ECR lifecycle | Retains the 10 most recent images |
| GitHub OIDC provider | Trusts tokens issued by GitHub Actions for the AWS STS audience |
| GitHub ECR publisher role | Trusts only this repository's `main` branch and can push only to the Ticket-API ECR repository |
| Jenkins development role and inline policy | Trusts one development IAM user and grants repository-scoped ECR metadata reads. References an existing managed permissions boundary. |
| Amazon S3 | Private Ansible transfer bucket, AES-256 encryption, one-day expiration |

The private subnet currently hosts no project workload. The S3 bucket exists
for temporary Ansible module and file transfers over the SSM connection.

## KMS and Parameter Store Integration

Terraform manages:

- `aws_kms_key.ticket_api_secrets`
- `aws_kms_alias.ticket_api_secrets`
- `aws_iam_role_policy.ec2_secrets_read`

With the default project and environment values, the alias is
`alias/ticket-api-dev-secrets` and the EC2 role is
`ticket-api-dev-ec2-ssm-role`. The key encrypts these Parameter Store paths:

- `/ticket-api/dev/postgres-password`
- `/ticket-api/dev/jwt-secret`
- `/ticket-api/dev/cloudflare-ddns-token`
- `/ticket-api/dev/cloudflare-certbot-token`

The first two parameters were populated with the application's existing
credentials. That migration did not rotate the database password or JWT
signing secret and did not recreate PostgreSQL. The Cloudflare parameters
provide separate credentials for A-record synchronization and Certbot DNS-01
challenges. Parameter values are not defined by
`aws_ssm_parameter` resources in this repository. This avoids placing their
plaintext values in Terraform state, but it also means parameter creation and
initial value migration are not fully reproducible from the Terraform files.

Automatic KMS rotation rotates key material, not application credentials.
PostgreSQL and JWT secret rotation remains an operational feature to design.

## Public HTTPS and Dynamic DNS

Terraform declares `aws_vpc_security_group_ingress_rule.https`, allowing
public TCP 443 to the EC2 security group. Port 22 remains closed and there is
no public port 80 rule. The AWS Compose override publishes container port 443
on the host and binds container port 80 only to `127.0.0.1:8080`.

The instance has an automatically assigned public IPv4 address rather than an
Elastic IP. Cloudflare hosts a DNS-only A record for
`api.orlandoalvarez.dev`; it is not acting as a reverse proxy, CDN, WAF, or TLS
endpoint. A host-side Python service reads the current address from IMDSv2 and
updates the existing A record through the Cloudflare API when it changes.

Nginx terminates TLS on EC2 using Let's Encrypt certificates issued through a
Certbot DNS-01 challenge. The certificate directory is mounted read-only into
the Nginx container. See [HTTPS and Dynamic DNS](https-ddns.md) for the
operational flow and recovery procedures.

## Pinned Amazon Linux AMI

The EC2 resource uses `var.ec2_ami_id` directly. Pinning the AMI prevents a
newer public Amazon Linux image from silently producing an unexpected instance
replacement plan.

An SSM public-parameter data source for the latest Amazon Linux 2023 AMI remains
declared in `compute.tf`, but it is not connected to the instance `ami`
argument.

Create a local variables file from the safe template:

```powershell
Set-Location .\terraform
Copy-Item terraform.tfvars.example terraform.tfvars
```

Replace the placeholder with a compatible `us-west-2` AMI. The populated
`terraform.tfvars` file is ignored.

Alternatively:

```powershell
$env:TF_VAR_ec2_ami_id = "ami-REPLACE_WITH_VALID_AMI"
```

## GitHub OIDC and ECR Publication

Terraform defines an IAM OpenID Connect provider for GitHub Actions and a
dedicated ECR publisher role. The role's trust policy requires both:

- Audience: `sts.amazonaws.com`
- Subject: `repo:Orlando-Alvarez/Ticket-API:ref:refs/heads/main`

This prevents pull requests, feature branches, forks, and other repositories
from satisfying the configured trust relationship. The attached inline policy
allows `ecr:GetAuthorizationToken`, which AWS requires with resource `*`, and
limits the remaining repository operations used for publication to the
Ticket-API ECR repository ARN.

The GitHub workflow requests `id-token: write` only for its publication job.
It does not store a long-lived AWS access key or secret access key in GitHub.
On a push to `main`, and only after the test, PostgreSQL integration, and Docker
build jobs succeed, it is configured to build and push an immutable
`sha-<full-commit-sha>` tag.

The [successful `main` run](https://github.com/Orlando-Alvarez/Ticket-API/actions/runs/44975797065)
shows successful OIDC authentication, ECR login, and image push. See
[CI/CD and Image Delivery](ci-cd.md) for the job dependencies and artifact
handoff.

## Jenkins Development Role

[`iam_jenkins.tf`](../terraform/iam_jenkins.tf) declares
`aws_iam_role.jenkins_deployer` (`ticket-api-dev-jenkins-deployer` with the
default variables) and `aws_iam_role_policy.jenkins_ecr_read`. The trust policy
allows `sts:AssumeRole` from a single development IAM user. The inline policy
grants `ecr:DescribeImages` and `ecr:ListImages` on the Ticket-API ECR repository.

Terraform attaches `TicketAPI-Jenkins-PermissionsBoundary` to the role by
referencing the ARN of a customer-managed policy created separately in AWS.
The boundary policy's document and lifecycle are outside this root module.
The Jenkins role's declared permissions cover ECR metadata reads. SSM
sessions, S3 transfers, image pulls, and EC2 deployment require other
identities or permissions.

## Terraform Workflow on Windows PowerShell

Run these commands from the repository root:

```powershell
$env:AWS_PROFILE = "ticketapi-tf"
# Omit the next line when terraform.tfvars contains ec2_ami_id.
$env:TF_VAR_ec2_ami_id = "ami-REPLACE_WITH_VALID_AMI"

aws sts get-caller-identity
Set-Location .\terraform

terraform init
terraform fmt -check
terraform validate
terraform plan '-out=ticket-api.tfplan'
terraform show ticket-api.tfplan
terraform apply ticket-api.tfplan
```

The quoted `'-out=ticket-api.tfplan'` form is intentional. It is the syntax
verified in the project's Windows PowerShell environment; the unquoted
`-out=ticket-api.tfplan` form produced an argument error there.

Review the saved plan before applying it. The workflow does not use
`-auto-approve`.

A recorded operator verification for the preceding security-hardening stage
reported:

```text
terraform validate: successful
terraform plan: No changes. Your infrastructure matches the configuration.
```

These are point-in-time, operator-provided results. The public HTTPS endpoint
has since been verified, but no current Terraform plan output is stored in the
repository. Repeat validation and planning against the local configuration
before any future infrastructure change.

## Outputs

Terraform currently exports:

```bash
terraform -chdir=terraform output -raw ecr_repository_url
```

It does not export the EC2 instance ID, public IP, or Ansible transfer bucket.
The static Ansible inventory must be maintained manually when those resources
change.

## IAM Responsibilities

| Identity | Purpose |
| --- | --- |
| `ticketapi-tf` | Assumes `TicketAPI-Terraform-Deployer` to provision represented resources |
| `ticketapi-dev` | Runs Ansible through SSM and accesses the dedicated transfer bucket |
| GitHub ECR publisher role | Accepts short-lived OIDC sessions from this repository's `main` branch and pushes only to its ECR repository |
| Jenkins development role | Assumed through the local `ticketapi-jenkins` profile for repository-scoped ECR metadata reads |
| Authorized publisher profile | Supports the documented manual publication fallback |
| EC2 instance role | Registers with SSM, pulls from ECR, and reads/decrypts deployment secrets without static keys |

### Terraform Controller Bootstrap

The `ticketapi-tf` profile assumes `TicketAPI-Terraform-Deployer`. That
controller role needs permission to manage the resources represented by the
Terraform configuration. During implementation, manually bootstrapped
permissions were required for:

- Creating, managing, and tagging KMS keys and aliases
- Reading the KMS key policy with `kms:GetKeyPolicy`
- Enabling and inspecting automatic KMS key rotation
- Creating the EC2 secrets inline policy with `iam:PutRolePolicy`
- Reading and listing existing inline role policies
- Managing the existing ECR resources and IAM policy attachments
- Creating and managing the GitHub OIDC provider, publisher role, and inline
  ECR policy

These are controller permissions used by Terraform. They are distinct from the
runtime permissions granted to the EC2 instance role and from the KMS key,
alias, IAM inline policy, ECR repository, and other resources that Terraform
manages.

The bootstrap permissions themselves are not fully defined by this repository.
That is a reproducibility limitation: a new controller cannot be recreated
solely from the current Terraform root module. Move this prerequisite into a
separate, controlled IAM-bootstrap process with reviewed least-privilege
policies. Do not compensate by granting broad administrator access.

The operator reported a separately configured, limited administrative IAM
policy for the Terraform role to create and manage the Jenkins role. That
administrative policy and the Jenkins boundary's rules are AWS-side bootstrap
dependencies. Provisioning authority belongs to the Terraform identity.
Jenkins uses the runtime role with the narrower ECR read policy.

The custom EC2 inline policy allows `ssm:GetParameter` and
`ssm:GetParameters` for only the four calculated parameter ARNs. It allows
`kms:Decrypt` only against the project KMS key and constrains use to the
regional SSM service and matching `PARAMETER_ARN` encryption contexts.

These restrictions describe the custom secrets policy, not the role's entire
effective permission set. The AWS-managed `AmazonSSMManagedInstanceCore`
policy supplies additional SSM-related permissions needed for managed-instance
operation. Temporary migration permissions for `ssm:PutParameter` and
`kms:Encrypt` were removed from the custom EC2 policy after the existing
credentials were stored.

The EC2 policy does not grant Terraform provisioning authority. Conversely,
the Terraform controller's bootstrap capabilities are not application runtime
permissions and must not be transferred to EC2.

## Terraform State

No remote backend is declared. State remains local and can contain sensitive
infrastructure metadata.

`.gitignore` excludes:

- `.terraform/`
- `*.tfstate` and backups
- Real `.tfvars` files
- Saved plans
- Crash logs

Never publish local state or copy its contents into documentation, CI output,
issues, or pull requests.

## Cost Considerations

- A customer-managed KMS key has a recurring key-storage charge and KMS API
  requests can add usage charges. Automatic rotations may affect key-storage
  cost. Review the current [AWS KMS pricing](https://aws.amazon.com/kms/pricing/)
  before changing the key strategy.
- Standard Parameter Store parameters are available at no additional charge
  within their documented quotas; advanced parameters and higher-throughput
  API usage are billable. Review the current
  [AWS Systems Manager pricing](https://aws.amazon.com/systems-manager/pricing/).
- EC2, EBS, public IPv4, S3, data transfer, and related service usage remain
  billable independently of this secret-management design.
- Cloudflare plan or domain charges, if applicable, remain external to AWS.
  Let's Encrypt does not add an AWS certificate-service charge, but the host,
  public IPv4, DNS traffic, and automation still consume their respective
  services.

Pricing changes over time. The repository intentionally does not embed a
fixed monthly cost estimate.

## Current Infrastructure Limitations

- State is local and has no remote locking.
- Some IAM permissions remain manual.
- Parameter values and their initial migration are not Terraform-managed.
- Inventory and ECR registry values are environment-specific.
- The workflow currently contains an environment-specific publisher role ARN;
  the account identifier is not a credential, but portability requires making
  this value configurable.
- The Jenkins role references an account-specific boundary, and its trust
  policy names an account-specific development IAM user. Bootstrapping the
  role in a new account requires corresponding IAM prerequisites.
- The private subnet has no NAT gateway and hosts no workload.
- There is no managed database service.
- There is no load balancer, Elastic IP, managed certificate service, or
  high-availability ingress.
- Initial certificate issuance is an operator-run step; only renewal is
  automated by the repository files.
- Public reachability depends on DDNS correcting the A record after an EC2
  public-address change and on DNS cache expiration.
- Backups, recovery, monitoring, and alerting are not provisioned.
- Cloudflare is configured as DNS-only, so client traffic reaches the EC2
  origin directly and does not receive Cloudflare proxy protections.

