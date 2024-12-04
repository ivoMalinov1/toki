terraform {
  backend "gcs" {
    bucket = "toki-data-platform-terraform"
    prefix = "state/scrape_prices"
  }
}
