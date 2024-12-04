data "google_pubsub_topic" "billing-trigger" {
  name = "billing-trigger-${terraform.workspace}"
}
