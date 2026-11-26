
resource "aws_s3_bucket" "postgres_backups" {
  bucket = "${var.project_name}-${var.environment}-postgres-backups-${data.aws_caller_identity.current.account_id}-${var.aws_region}"

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-postgres-backups"
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Purpose     = "PostgreSQL Backups"
  }
}

resource "aws_s3_bucket_public_access_block" "postgres_backups" {
  bucket = aws_s3_bucket.postgres_backups.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "postgres_backups" {
  bucket = aws_s3_bucket.postgres_backups.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "postgres_backups" {
  bucket = aws_s3_bucket.postgres_backups.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "postgres_backups" {
  bucket = aws_s3_bucket.postgres_backups.id

  rule {
    id     = "expire-postgresql-backups"
    status = "Enabled"

    filter {
      prefix = "postgresql/"
    }

    expiration {
      days = 90
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

output "postgres_backup_bucket_name" {
  description = "S3 bucket used for PostgreSQL backups"
  value       = aws_s3_bucket.postgres_backups.id
}
