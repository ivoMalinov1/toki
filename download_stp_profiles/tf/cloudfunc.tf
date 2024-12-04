data "google_storage_bucket" "source_bucket" {
  name = "source_${terraform.workspace}"
}

resource "google_storage_bucket_object" "archive" {
  name   = "${local.file_md5}.zip"
  bucket = data.google_storage_bucket.source_bucket.name
  source = "${path.root}/../build/${var.function_name}.zip"
}

resource "google_service_account" "service_account" {
  account_id   = local.short_name
  display_name = "Download stp profiles Service Account"
}

resource "google_cloudfunctions_function" "function" {
  name        = local.aligned_name
  description = "Cloud function that gets stp profile data"
  runtime     = "python310"
  service_account_email = google_service_account.service_account.email

  environment_variables = {
    ENVIRONMENT     = terraform.workspace
    RAW_DATA_BUCKET = data.google_storage_bucket.stp_profiles_data_bucket.name
    ROOT_FOLDER_ID  = var.root_folder_id
  }

  available_memory_mb   = 256
  source_archive_bucket = data.google_storage_bucket.source_bucket.name
  source_archive_object = google_storage_bucket_object.archive.name
  trigger_http          = true
  entry_point           = var.entry_point
  timeout               = 540
}

resource "google_storage_bucket_iam_member" "bucket_object_creator" {
  bucket = data.google_storage_bucket.stp_profiles_data_bucket.name
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.service_account.email}"
}

resource "google_cloudfunctions_function_iam_member" "download_stp_profiles_invoker" {
  project        = google_cloudfunctions_function.function.project
  region         = google_cloudfunctions_function.function.region
  cloud_function = google_cloudfunctions_function.function.name

  role   = "roles/cloudfunctions.invoker"
  member = "serviceAccount:${google_service_account.service_account.email}"
}

resource "google_cloud_scheduler_job" "job" {
  paused           = terraform.workspace == "toki-data-platform-prod" ? false : true
  name             = local.aligned_name
  description      = "Trigger the ${google_cloudfunctions_function.function.name} Once a Year."
  schedule         = "0 10 15 1 *" # Once a Year on 15 Dec
  time_zone        = "Europe/Dublin"
  attempt_deadline = "320s"

  http_target {
    http_method = "GET"
    uri         = google_cloudfunctions_function.function.https_trigger_url

    oidc_token {
      service_account_email = google_service_account.service_account.email
    }
  }
}
