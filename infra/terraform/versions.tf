terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.27, < 7"
    }
  }
  # L'état distant se configure à l'init : voir docs/runbook.md.
  backend "s3" {}
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project = var.project
    }
  }
}

data "aws_caller_identity" "current" {}
