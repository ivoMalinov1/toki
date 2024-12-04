provider "google" {
  project = terraform.workspace
  region  = "europe-west3"
}

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "4.42.0"
    }
  }
}
