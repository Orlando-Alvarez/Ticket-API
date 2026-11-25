resource "aws_iam_role" "jenkins_deployer" {
  name = "${var.project_name}-${var.environment}-jenkins-deployer"

  permissions_boundary = "arn:aws:iam::891920435362:policy/TicketAPI-Jenkins-PermissionsBoundary"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::891920435362:user/ticketapi-dev"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_iam_role_policy" "jenkins_ecr_read" {
  name = "jenkins-ecr-read"
  role = aws_iam_role.jenkins_deployer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:DescribeImages",
          "ecr:ListImages"
        ]
        Resource = aws_ecr_repository.ticket_api.arn
      }
    ]
  })
}
