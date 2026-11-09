resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${var.project}-api"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "job" {
  name              = "/aws/lambda/${var.project}-job"
  retention_in_days = 30
}

resource "aws_lambda_function" "api" {
  count         = local.deployed ? 1 : 0
  function_name = "${var.project}-api"
  role          = aws_iam_role.api.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
  architectures = ["x86_64"]
  memory_size   = 512
  timeout       = 29
  # Plafonne le coût en cas d'abus : au-delà, API Gateway renvoie une erreur 503.
  reserved_concurrent_executions = 5
  environment {
    variables = local.common_environment
  }
  depends_on = [aws_cloudwatch_log_group.api]
}

resource "aws_lambda_function" "job" {
  count         = local.deployed ? 1 : 0
  function_name = "${var.project}-job"
  role          = aws_iam_role.job.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.job.repository_url}:${var.image_tag}"
  architectures = ["x86_64"]
  memory_size   = 3008
  timeout       = 900
  environment {
    variables = merge(local.common_environment, { GIT_SHA = var.image_tag })
  }
  depends_on = [aws_cloudwatch_log_group.job]
}

data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  count              = local.deployed ? 1 : 0
  name               = "${var.project}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

resource "aws_iam_role_policy" "scheduler" {
  count = local.deployed ? 1 : 0
  role  = aws_iam_role.scheduler[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.job[0].arn
    }]
  })
}

resource "aws_scheduler_schedule" "daily" {
  count = local.deployed ? 1 : 0
  name  = "${var.project}-daily"
  flexible_time_window {
    mode = "OFF"
  }
  # Du mardi au samedi à 23 h 30 UTC, après la clôture américaine de la veille ouvrée.
  schedule_expression = "cron(30 23 ? * TUE-SAT *)"
  target {
    arn      = aws_lambda_function.job[0].arn
    role_arn = aws_iam_role.scheduler[0].arn
  }
}

resource "aws_apigatewayv2_api" "http" {
  count         = local.deployed ? 1 : 0
  name          = var.project
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "api" {
  count                  = local.deployed ? 1 : 0
  api_id                 = aws_apigatewayv2_api.http[0].id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api[0].invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  count     = local.deployed ? 1 : 0
  api_id    = aws_apigatewayv2_api.http[0].id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.api[0].id}"
}

resource "aws_cloudwatch_log_group" "access" {
  name              = "/aws/apigateway/${var.project}"
  retention_in_days = 30
}

resource "aws_apigatewayv2_stage" "default" {
  count       = local.deployed ? 1 : 0
  api_id      = aws_apigatewayv2_api.http[0].id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_rate_limit  = var.api_rate_limit
    throttling_burst_limit = var.api_rate_limit * 2
  }
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access.arn
    format = jsonencode({
      requestId = "$context.requestId"
      route     = "$context.routeKey"
      status    = "$context.status"
      latency   = "$context.responseLatency"
    })
  }
}

resource "aws_lambda_permission" "api_gateway" {
  count         = local.deployed ? 1 : 0
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api[0].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http[0].execution_arn}/*/*"
}
