terraform {
  required_version = ">= 1.1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.14.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.27.0"
    }
  }
}

provider "google" {}
provider "google-beta" {}