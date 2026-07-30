output "bucket_name" {
  description = "Generated bucket name to pass to the application as S3_BUCKET."
  value       = aws_s3_bucket.application.id
}

output "bucket_arn" {
  description = "Bucket ARN for the application's future IAM policy."
  value       = aws_s3_bucket.application.arn
}

output "application_environment" {
  description = "Environment variables required by the CSV processor."
  value = {
    AWS_REGION = var.aws_region
    S3_BUCKET  = aws_s3_bucket.application.id
    S3_PREFIX  = var.processed_prefix
  }
}

output "lifecycle_rule" {
  description = "Glacier Flexible Retrieval lifecycle configuration."
  value = {
    prefix        = var.processed_prefix
    storage_class = "GLACIER"
    after_days    = var.glacier_transition_days
  }
}
