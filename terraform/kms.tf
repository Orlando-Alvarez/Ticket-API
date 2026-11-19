
resource "aws_kms_key" "ticket_api_secrets" {
  description = "KMS key for Ticket-API deployment secrets"

  enable_key_rotation     = true
  deletion_window_in_days = 30

  tags = {
    Name        = "${var.project_name}-${var.environment}-secrets"
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_kms_alias" "ticket_api_secrets" {
  name          = "alias/${var.project_name}-${var.environment}-secrets"
  target_key_id = aws_kms_key.ticket_api_secrets.key_id
}
