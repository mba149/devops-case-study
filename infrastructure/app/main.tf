locals {
  bucket_prefix = "${var.project_name}-${var.environment}-"

  common_tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.project_name
  }
}

resource "aws_s3_bucket" "application" {
  bucket_prefix = local.bucket_prefix
  force_destroy = false

  tags = merge(local.common_tags, var.additional_tags, {
    Name = "${var.project_name}-${var.environment}"
  })
}

resource "aws_s3_bucket_public_access_block" "application" {
  bucket = aws_s3_bucket.application.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "application" {
  bucket = aws_s3_bucket.application.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "application" {
  bucket = aws_s3_bucket.application.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "application" {
  bucket = aws_s3_bucket.application.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "application" {
  bucket                                 = aws_s3_bucket.application.id
  transition_default_minimum_object_size = "varies_by_storage_class"

  depends_on = [aws_s3_bucket_versioning.application]

  rule {
    id     = "processed-csv-to-glacier-flexible-retrieval"
    status = "Enabled"

    filter {
      prefix = var.processed_prefix
    }

    transition {
      days          = var.glacier_transition_days
      storage_class = "GLACIER"
    }

    noncurrent_version_transition {
      noncurrent_days = var.glacier_transition_days
      storage_class   = "GLACIER"
    }
  }
}
