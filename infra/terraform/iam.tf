data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "api" {
  statement {
    sid       = "ReadServingData"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.data.arn}/serving/*"]
  }
  statement {
    sid       = "ListForNotFound"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.data.arn]
  }
  statement {
    sid = "AppTable"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
    ]
    resources = [aws_dynamodb_table.app.arn]
  }
  statement {
    sid       = "SearchPassages"
    actions   = ["s3vectors:QueryVectors", "s3vectors:GetVectors"]
    resources = [aws_s3vectors_index.passages.index_arn]
  }
  statement {
    sid       = "CallModels"
    actions   = ["bedrock:InvokeModel"]
    resources = local.bedrock_resources
  }
  dynamic "statement" {
    for_each = var.enable_guardrail ? [1] : []
    content {
      sid       = "ApplyGuardrail"
      actions   = ["bedrock:ApplyGuardrail"]
      resources = [aws_bedrock_guardrail.advice[0].guardrail_arn]
    }
  }
}

data "aws_iam_policy_document" "job" {
  statement {
    sid       = "ReadWriteData"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.data.arn}/*"]
  }
  statement {
    sid       = "ListForNotFound"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.data.arn]
  }
  statement {
    sid       = "WriteForecasts"
    actions   = ["dynamodb:PutItem", "dynamodb:Query"]
    resources = [aws_dynamodb_table.app.arn]
  }
  statement {
    sid       = "IndexPassages"
    actions   = ["s3vectors:PutVectors"]
    resources = [aws_s3vectors_index.passages.index_arn]
  }
  statement {
    sid       = "Embed"
    actions   = ["bedrock:InvokeModel"]
    resources = ["arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0"]
  }
}

resource "aws_iam_role" "api" {
  name               = "${var.project}-api"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "api" {
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

resource "aws_iam_role_policy_attachment" "api_logs" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role" "job" {
  name               = "${var.project}-job"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy" "job" {
  role   = aws_iam_role.job.id
  policy = data.aws_iam_policy_document.job.json
}

resource "aws_iam_role_policy_attachment" "job_logs" {
  role       = aws_iam_role.job.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
