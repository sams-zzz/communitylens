output "site_url" {
  value = "https://${aws_cloudfront_distribution.site.domain_name}"
}

output "site_bucket" {
  value = aws_s3_bucket.site.id
}

output "distribution_id" {
  value = aws_cloudfront_distribution.site.id
}

output "data_bucket" {
  value = aws_s3_bucket.data.id
}

output "job_function" {
  value = local.deployed ? aws_lambda_function.job[0].function_name : null
}

output "github_role_arn" {
  value = var.github_repository == "" ? null : aws_iam_role.github[0].arn
}

output "prototype_address" {
  value = var.enable_ec2 ? aws_instance.prototype[0].public_ip : null
}
