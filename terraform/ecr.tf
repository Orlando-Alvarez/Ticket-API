resource "aws_ecr_repository" "ticket_api" {
  name                 = "ticket-api"
  image_tag_mutability = "IMMUTABLE"

  encryption_configuration {
    encryption_type = "AES256"
  }

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "ticket-api"
    Project     = "TicketAPI"
    Environment = "dev"
    ManagedBy   = "Terraform"
  }
}

resource "aws_ecr_lifecycle_policy" "ticket_api" {
  repository = aws_ecr_repository.ticket_api.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the 10 most recent images"

        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }

        action = {
          type = "expire"
        }
      }
    ]
  })
}

output "ecr_repository_url" {
  description = "Private ECR repository for Ticket-API"
  value       = aws_ecr_repository.ticket_api.repository_url
}