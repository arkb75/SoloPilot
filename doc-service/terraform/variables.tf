variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "solopilot"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "S3 bucket name for documents"
  type        = string
  default     = ""
}

variable "lambda_function_name" {
  description = "Name of the Lambda function that will access the bucket"
  type        = string
  default     = "solopilot-doc-generator"
}
