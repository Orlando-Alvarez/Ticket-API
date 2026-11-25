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

resource "aws_iam_role_policy" "jenkins_ssm_deploy" {
  name = "jenkins-ssm-deploy"
  role = aws_iam_role.jenkins_deployer.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "StartTicketAPISession"
        Effect = "Allow"

        Action = [
          "ssm:StartSession"
        ]

        Resource = [
          "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/i-0641d95f96183c01d",
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:document/SSM-SessionManagerRunShell"
        ]
      },
      {
        Sid    = "ManageOwnSSMSessions"
        Effect = "Allow"

        Action = [
          "ssm:TerminateSession",
          "ssm:ResumeSession",
          "ssmmessages:OpenDataChannel"
        ]

        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:session/*"

        Condition = {
          StringEquals = {
            "ssm:resourceTag/aws:ssmmessages:session-id" = "$${aws:userid}"
          }
        }
      },
      {
        Sid    = "AccessAnsibleS3Bucket"
        Effect = "Allow"

        Action = [
          "s3:GetBucketLocation",
          "s3:ListBucket"
        ]

        Resource = aws_s3_bucket.ansible.arn
      },
      {
        Sid    = "ManageAnsibleTemporaryObjects"
        Effect = "Allow"

        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]

        Resource = "${aws_s3_bucket.ansible.arn}/i-0641d95f96183c01d/*"
      }
    ]
  })
}
