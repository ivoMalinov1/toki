locals {
  aligned_name = replace("${var.function_name}-${terraform.workspace}", "_", "-")
  short_name   = replace(replace(local.aligned_name, "-", ""), "tokidataplatform", "")
  file_sha512  = filesha512("${path.root}/../build/${var.function_name}.zip")
}
