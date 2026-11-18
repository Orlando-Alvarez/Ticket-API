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

## Provisioned Resources

| Resource | Implemented configuration |
| --- | --- |
| VPC | `10.20.0.0/16`, DNS support and hostnames enabled |
| Public subnet | `10.20.1.0/24` in `us-west-2a`, public IP assignment enabled |
| Private subnet | `10.20.2.0/24` in `us-west-2a`, no public IP assignment |
| Internet Gateway | Attached to the VPC |
| Public route table | `0.0.0.0/0` through the Internet Gateway |
| Private route table | No public default route or NAT gateway |
| Security group | Inbound TCP/80 from IPv4 internet; outbound IPv4 allowed; no SSH ingress |
| EC2 | Amazon Linux 2023, `t2.small` default, public subnet, public IP |
| Root storage | Encrypted 16 GiB gp3, deleted on instance termination |
| Instance metadata | IMDSv2 tokens required |
| IAM role/profile | Systems Manager core access and pull-only ECR access |
| Amazon ECR | Private repository, immutable tags, scan on push, AES-256 encryption |
| ECR lifecycle | Retains the 10 most recent images |
| Amazon S3 | Private Ansible transfer bucket, AES-256 encryption, one-day expiration |

The private subnet currently hosts no project workload. The S3 bucket exists
for temporary Ansible module and file transfers over the SSM connection.

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

The most recently recorded operator verification reported:

```text
terraform validate: successful
terraform plan: No changes. Your infrastructure matches the configuration.
```

These are operator-provided results. Repeat validation and planning before any
future infrastructure change.

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
| Authorized publisher profile | Authenticates and pushes images to ECR |
| EC2 instance role | Registers with SSM and pulls from ECR without static keys |

During development, the Terraform deployer role required additional
permissions to manage ECR and attach the ECR pull-only policy to the EC2 role.
Some controller-side IAM permissions were configured manually and are not fully
managed by this Terraform configuration.

Do not solve missing permissions by attaching broad administrator policies.
Grant the minimum project, environment, and action scope needed by each
identity.

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

## Current Infrastructure Limitations

- State is local and has no remote locking.
- Some IAM permissions remain manual.
- Inventory and ECR registry values are environment-specific.
- The private subnet has no NAT gateway and hosts no workload.
- There is no managed database service.
- There is no load balancer, HTTPS listener, or certificate automation.
- Backups, recovery, monitoring, and alerting are not provisioned.
- Public HTTP/80 is allowed by the security group, although the current Compose
  deployment binds Nginx only to EC2 loopback.

