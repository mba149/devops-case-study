variable "aws_region" {
  description = "AWS region where the application bucket is created."
  type        = string
  default     = "us-east-2"
}

variable "project_name" {
  description = "Project name used in the generated bucket prefix and tags."
  type        = string
  default     = "csv-processor"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]*[a-z0-9]$", var.project_name))
    error_message = "project_name must contain lowercase letters, numbers, or hyphens, and start and end with a letter or number."
  }
}

variable "environment" {
  description = "Deployment environment used in the generated bucket prefix and tags."
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]*[a-z0-9]$", var.environment))
    error_message = "environment must contain lowercase letters, numbers, or hyphens, and start and end with a letter or number."
  }

  validation {
    condition     = length("${var.project_name}-${var.environment}-") <= 37
    error_message = "The combined project_name and environment are too long for an S3 bucket prefix."
  }
}

variable "processed_prefix" {
  description = "Only objects under this prefix are transitioned."
  type        = string
  default     = "processed/"

  validation {
    condition     = length(var.processed_prefix) > 0 && endswith(var.processed_prefix, "/")
    error_message = "processed_prefix must be non-empty and end with a slash."
  }
}

variable "additional_tags" {
  description = "Additional tags to apply to the S3 bucket."
  type        = map(string)
  default     = {}
}

variable "glacier_transition_days" {
  description = "Days after creation before transitioning objects to Glacier Flexible Retrieval."
  type        = number
  default     = 30

  validation {
    condition     = var.glacier_transition_days >= 0
    error_message = "glacier_transition_days must be zero or greater."
  }
}
