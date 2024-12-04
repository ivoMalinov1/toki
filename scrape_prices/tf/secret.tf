resource "google_secret_manager_secret" "secret_api_key" {
  secret_id = "entsoe_api_key"

  replication {
    automatic = true
  }
}
