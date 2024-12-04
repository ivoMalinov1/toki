terraform {
  backend "gcs" {
    bucket = "toki-data-platform-terraform"
    prefix = "state/download_stp_profiles"
  }
}
