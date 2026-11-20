
locals {
  secret_names = [
    "/${var.project_name}/${var.environment}/postgres-password",
    "/${var.project_name}/${var.environment}/jwt-secret",
    "/${var.project_name}/${var.environment}/cloudflare-ddns-token"
  ]

  secret_arns = [
    for name in local.secret_names :
    "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${name}"
  ]
}

resource "aws_iam_role_policy" "ec2_secrets_read" {
  name = "${var.project_name}-${var.environment}-secrets-read"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "ReadTicketAPIParameters"
        Effect = "Allow"

        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]

        Resource = local.secret_arns
      },
      {
        Sid    = "DecryptTicketAPISecrets"
        Effect = "Allow"

        Action = [
          "kms:Decrypt"
        ]

        Resource = aws_kms_key.ticket_api_secrets.arn

        Condition = {
          StringEquals = {
            "kms:ViaService"                      = "ssm.${var.aws_region}.amazonaws.com"
            "kms:EncryptionContext:PARAMETER_ARN" = local.secret_arns
          }
        }
      }
    ]
  })
}
