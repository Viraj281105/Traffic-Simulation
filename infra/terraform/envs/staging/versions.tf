terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.70, < 6.0"
    }
  }

  # Partial configuration: pass the bucket with "terraform init -backend-config=backend.hcl".
  # See backend.hcl.example. The state bucket is created by hand once (see the README).
  backend "s3" {}
}

provider "aws" {
  region = var.region

  # Every resource that supports tags gets the mandatory cost tags from the tagging module.
  default_tags {
    tags = module.tagging.tags
  }
}
