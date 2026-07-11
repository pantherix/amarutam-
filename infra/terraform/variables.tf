variable "aws_region" {
  type        = string
  description = "Target AWS Region"
  default     = "us-east-1"
}

variable "db_password" {
  type        = string
  description = "Production database master password"
  sensitive   = true
}

variable "ecr_repository_url" {
  type        = string
  description = "Target ECR repository URL containing the container image"
}

variable "jwt_secret" {
  type        = string
  description = "Production secret for signing JWT access tokens"
  sensitive   = true
}

variable "field_encryption_key" {
  type        = string
  description = "Production 32-byte base64-encoded AES-256-GCM field encryption key"
  sensitive   = true
}
