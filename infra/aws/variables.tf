variable "name" {
  description = "Prefix for every resource name."
  type        = string
  default     = "interview-coach"
}

variable "region" {
  description = "AWS region. Bedrock's Nova Lite cross-region profile (us.*) needs a US region."
  type        = string
  default     = "us-east-1"
}

variable "image_tag" {
  description = "Tag of the backend and frontend images in ECR (deploy.sh passes the git commit)."
  type        = string
  default     = "latest"
}

variable "llm_provider" {
  description = "bedrock (signed by the task role, no key) or gemini (needs gemini_api_key)."
  type        = string
  default     = "bedrock"

  validation {
    condition     = contains(["bedrock", "gemini"], var.llm_provider)
    error_message = "llm_provider must be bedrock or gemini."
  }
}

variable "bedrock_model" {
  description = "Bedrock model or inference profile id."
  type        = string
  default     = "us.amazon.nova-lite-v1:0"
}

variable "gemini_api_key" {
  description = "Only when llm_provider = gemini. Stored in Secrets Manager; also kept in Terraform state."
  type        = string
  default     = ""
  sensitive   = true
}

variable "alert_email" {
  description = "Gets the monthly budget alerts and the error alarm."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Budget alerts fire at 50% and 100% of this, actual spend."
  type        = number
  default     = 10
}
