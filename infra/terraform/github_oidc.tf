resource "aws_iam_openid_connect_provider" "github" {
  count          = var.github_repository == "" ? 0 : 1
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "github_assume" {
  count = var.github_repository == "" ? 0 : 1
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github[0].arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github" {
  count              = var.github_repository == "" ? 0 : 1
  name               = "${var.project}-github"
  assume_role_policy = data.aws_iam_policy_document.github_assume[0].json
}

# Terraform doit gérer IAM, CloudFront, Lambda, etc. : ce rôle de projet étudiant reste large.
# Il n'est utilisable que depuis la branche main du dépôt indiqué.
resource "aws_iam_role_policy_attachment" "github" {
  count      = var.github_repository == "" ? 0 : 1
  role       = aws_iam_role.github[0].name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
