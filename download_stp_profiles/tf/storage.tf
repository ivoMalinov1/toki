data "google_storage_bucket" "stp_profiles_data_bucket" {
  name = "stp_profiles_${terraform.workspace}"
}
