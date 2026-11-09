resource "aws_s3_bucket" "data" {
  bucket_prefix = "${var.project}-data-"
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_dynamodb_table" "app" {
  name         = var.project
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_s3vectors_vector_bucket" "passages" {
  vector_bucket_name = "${var.project}-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3vectors_index" "passages" {
  vector_bucket_name = aws_s3vectors_vector_bucket.passages.vector_bucket_name
  index_name         = "passages"
  data_type          = "float32"
  dimension          = var.embedding_dimensions
  distance_metric    = "cosine"

  metadata_configuration {
    non_filterable_metadata_keys = ["payload"]
  }
}

resource "aws_ecr_repository" "api" {
  name                 = "${var.project}-api"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "job" {
  name                 = "${var.project}-job"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy     = local.keep_last_images
}

resource "aws_ecr_lifecycle_policy" "job" {
  repository = aws_ecr_repository.job.name
  policy     = local.keep_last_images
}

locals {
  deployed = var.image_tag != ""
  keep_last_images = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Conserver les 5 dernières images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
      action       = { type = "expire" }
    }]
  })
  bedrock_resources = concat(var.bedrock_resource_arns, [
    "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/${var.bedrock_model_id}",
  ])
  common_environment = {
    CL_BACKEND              = "aws"
    CL_BUCKET               = aws_s3_bucket.data.id
    CL_TABLE                = aws_dynamodb_table.app.name
    CL_VECTOR_BUCKET        = aws_s3vectors_vector_bucket.passages.vector_bucket_name
    CL_VECTOR_INDEX         = aws_s3vectors_index.passages.index_name
    CL_LLM_BACKEND          = "bedrock"
    CL_BEDROCK_MODEL_ID     = var.bedrock_model_id
    CL_EMBEDDING_BACKEND    = "titan"
    CL_EMBEDDING_DIMENSIONS = tostring(var.embedding_dimensions)
    CL_GUARDRAIL_ID         = var.enable_guardrail ? aws_bedrock_guardrail.advice[0].guardrail_id : ""
    CL_GUARDRAIL_VERSION    = "DRAFT"
    CL_SEC_USER_AGENT       = var.sec_user_agent
    # Le site et l'API partagent la même origine via CloudFront : aucune autre origine n'est permise.
    CL_CORS_ORIGIN = "https://cors-non-utilise.invalid"
  }
}
