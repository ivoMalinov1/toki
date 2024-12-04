locals {
  short_name   = replace(replace(local.aligned_name, "-", ""), replace("toki-data-platform", "-", ""), "")
  aligned_name = replace("${var.function_name}-${terraform.workspace}", "_", "-")
  file_md5     = filemd5("${path.root}/../build/${var.function_name}.zip")
}
