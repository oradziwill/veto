terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state — pass bucket and region at init time:
  #   terraform init \
  #     -backend-config="bucket=<your-tf-state-bucket>" \
  #     -backend-config="key=veto/dev/terraform.tfstate" \
  #     -backend-config="region=<your-region>"
  #
  # Create the bucket once: aws s3 mb s3://<bucket> --region <region>
  backend "s3" {}
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "veto"
      Environment = var.env
      ManagedBy   = "terraform"
    }
  }
}
