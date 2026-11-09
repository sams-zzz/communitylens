variable "project" {
  type    = string
  default = "communitylens"
}

variable "region" {
  type    = string
  default = "eu-west-3"
}

variable "image_tag" {
  description = "Tag des images dans ECR ; laisser vide pour ne créer que les dépôts au premier passage"
  type        = string
  default     = ""
}

variable "bedrock_model_id" {
  type    = string
  default = "eu.amazon.nova-micro-v1:0"
}

variable "bedrock_resource_arns" {
  description = "Modèles et profils autorisés ; à ajuster après le benchmark"
  type        = list(string)
  default = [
    "arn:aws:bedrock:*::foundation-model/amazon.nova-micro-v1:0",
    "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0",
  ]
}

variable "embedding_dimensions" {
  type    = number
  default = 512
}

variable "enable_guardrail" {
  description = "Active Bedrock Guardrails après test de compatibilité avec la sortie structurée"
  type        = bool
  default     = false
}

variable "enable_ec2" {
  description = "Crée le prototype Docker sur EC2 (première version du schéma)"
  type        = bool
  default     = false
}

variable "ec2_ingress_cidr" {
  description = "Adresse autorisée à joindre le prototype EC2, par exemple 203.0.113.10/32"
  type        = string
  default     = "127.0.0.1/32"
}

variable "budget_limit_usd" {
  type    = string
  default = "20"
}

variable "budget_email" {
  type    = string
  default = ""
}

variable "github_repository" {
  description = "owner/repo autorisé à déployer ; vide pour ne pas créer le rôle"
  type        = string
  default     = ""
}

variable "sec_user_agent" {
  description = "Nom et adresse de contact exigés par la SEC ; vide pour désactiver EDGAR"
  type        = string
  default     = ""
}

variable "api_rate_limit" {
  description = "Requêtes par seconde acceptées par API Gateway"
  type        = number
  default     = 5
}
