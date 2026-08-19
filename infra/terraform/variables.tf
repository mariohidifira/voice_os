variable "aws_region" {
  type    = string
  default = "sa-east-1"
}

variable "environment" {
  type    = string
  default = "stg"
  validation {
    condition     = contains(["stg", "prod"], var.environment)
    error_message = "environment must be stg or prod"
  }
}

variable "account_suffix" {
  type        = string
  description = "Globally unique bucket suffix"
  default     = "replace-me"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "deploy_services" {
  type        = bool
  description = "Create ECS task definitions and services after images and secret values exist"
  default     = true
}
