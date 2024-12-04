data "google_storage_bucket" "source_bucket" {
  name = "source_${terraform.workspace}"
}

resource "google_storage_bucket_object" "archive" {
  name   = "${local.file_sha512}.zip"
  bucket = data.google_storage_bucket.source_bucket.name
  source = "${path.root}/../build/${var.function_name}.zip"
}

resource "google_cloudfunctions_function" "function" {
  name        = local.aligned_name
  description = "Cloud Function that scrapes prices data."
  runtime     = "python310"

  environment_variables = {
    PROJECT_ID = terraform.workspace
  }

  available_memory_mb   = 256
  source_archive_bucket = data.google_storage_bucket.source_bucket.name
  source_archive_object = google_storage_bucket_object.archive.name
  trigger_http          = true
  entry_point           = var.entry_point
  service_account_email = google_service_account.service_account.email
  timeout               = 120

  secret_environment_variables {
    key     = "ENTSOE_API_KEY"
    secret  = "entsoe_api_key"
    version = "latest"
  }
}

resource "google_service_account" "service_account" {
  account_id   = local.short_name
  display_name = "Scrape Price Data Service Account"
}

resource "google_cloudfunctions_function_iam_member" "invoker" {
  project        = google_cloudfunctions_function.function.project
  region         = google_cloudfunctions_function.function.region
  cloud_function = google_cloudfunctions_function.function.name

  role   = "roles/cloudfunctions.invoker"
  member = "serviceAccount:${google_service_account.service_account.email}"
}

resource "google_cloud_scheduler_job" "job" {
  paused           = false
  name             = local.aligned_name
  description      = "Trigger the ${google_cloudfunctions_function.function.name} Cloud Function every day at 8."
  schedule         = "0 8 * * *"
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

resource "google_bigquery_dataset_iam_member" "editor" {
  dataset_id = "clean"
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.service_account.email}"
}

resource "google_project_iam_member" "secret_accessor" {
  project = terraform.workspace
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}

resource "google_project_iam_member" "project_bq_job_runner" {
  project = terraform.workspace
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}
