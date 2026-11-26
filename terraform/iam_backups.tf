
resource "aws_iam_role_policy" "ec2_postgres_backups" {
  name = "${var.project_name}-${var.environment}-postgres-backups"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "ManagePostgreSQLBackupObjects"
        Effect = "Allow"

        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:AbortMultipartUpload"
        ]

        Resource = "${aws_s3_bucket.postgres_backups.arn}/postgresql/*"
      }
    ]
  })
}
