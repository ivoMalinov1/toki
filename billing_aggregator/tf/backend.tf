terraform {
  backend "gcs" {
    bucket = "toki-data-platform-terraform"
    prefix = "state/billing_aggregator"
  }
}
