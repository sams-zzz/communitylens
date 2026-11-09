resource "aws_budgets_budget" "monthly" {
  count        = var.budget_email == "" ? 0 : 1
  name         = var.project
  budget_type  = "COST"
  limit_amount = var.budget_limit_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_email]
  }
}

resource "aws_cloudwatch_metric_alarm" "api_errors" {
  count               = local.deployed ? 1 : 0
  alarm_name          = "${var.project}-api-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.api[0].function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_metric_alarm" "job_failed" {
  count               = local.deployed ? 1 : 0
  alarm_name          = "${var.project}-job-failed"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.job[0].function_name }
  statistic           = "Sum"
  period              = 86400
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = var.project
  dashboard_body = jsonencode({
    widgets = [
      {
        type       = "metric"
        width      = 12
        height     = 6
        properties = {
          title   = "Latence de génération (ms)"
          region  = var.region
          stat    = "p95"
          period  = 3600
          metrics = [[{ expression = "SEARCH('{CommunityLens,Generator} MetricName=\"LatencyMs\"', 'p95', 3600)" }]]
        }
      },
      {
        type       = "metric"
        width      = 12
        height     = 6
        properties = {
          title   = "Coût estimé par jour (USD)"
          region  = var.region
          stat    = "Sum"
          period  = 86400
          metrics = [[{ expression = "SEARCH('{CommunityLens,Generator} MetricName=\"CostUsd\"', 'Sum', 86400)" }]]
        }
      },
      {
        type       = "metric"
        width      = 12
        height     = 6
        properties = {
          title   = "Replis sur le texte du code"
          region  = var.region
          stat    = "Sum"
          period  = 3600
          metrics = [[{ expression = "SEARCH('{CommunityLens,Generator} MetricName=\"Fallback\"', 'Sum', 3600)" }]]
        }
      },
      {
        type       = "metric"
        width      = 12
        height     = 6
        properties = {
          title   = "Tokens consommés"
          region  = var.region
          stat    = "Sum"
          period  = 3600
          metrics = [[{ expression = "SEARCH('{CommunityLens,Generator} MetricName=\"InputTokens\" OR MetricName=\"OutputTokens\"', 'Sum', 3600)" }]]
        }
      },
    ]
  })
}
