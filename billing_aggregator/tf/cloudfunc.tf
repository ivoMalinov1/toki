# Creating a Cloud Storage bucket
resource "google_storage_bucket" "bucket" {
  name     = local.aligned_name
  location = "EU"
}

# Adding a file to a bucket
resource "google_storage_bucket_object" "archive" {
  name   = "${local.file_md5}.zip"
  bucket = google_storage_bucket.bucket.name
  source = "${path.root}/../build/${var.function_name}.zip"
}

# Creating a Cloud Function
resource "google_cloudfunctions_function" "function" {
  name                  = local.aligned_name
  description           = "Cloud function that fetches hourly consumption, validates it and aggregates it per point"
  runtime               = "python310"
  service_account_email = google_service_account.service_account.email

  environment_variables = {
    CURRENT_ENV = replace(replace(terraform.workspace, "toki-data-platform", ""), "-", "")
    PROJECT_ID  = terraform.workspace
  }

  available_memory_mb   = 256
  source_archive_bucket = google_storage_bucket.bucket.name
  source_archive_object = google_storage_bucket_object.archive.name
  entry_point           = var.function_name

  event_trigger {
    event_type = "google.pubsub.topic.publish"
    resource   = data.google_pubsub_topic.billing-trigger.id
  }
}

# Creating a service account
resource "google_service_account" "service_account" {
  account_id   = local.short_name
  display_name = "Billing aggregator service account"
}

resource "google_bigquery_dataset_iam_member" "clean_dataset_editor" {
  dataset_id = "clean"
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.service_account.email}"
}

# Since our data is in staging currently, we need permissions to access it. Remove once data is in clean
resource "google_bigquery_dataset_iam_member" "staging_dataset_editor" {
  dataset_id = "staging"
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.service_account.email}"
}

resource "google_project_iam_member" "project_bq_user" {
  project = terraform.workspace
  role    = "roles/bigquery.user"
  member  = "serviceAccount:${google_service_account.service_account.email}"
}
