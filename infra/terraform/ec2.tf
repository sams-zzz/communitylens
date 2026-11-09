# Première version du schéma : tout le projet en Docker sur une seule instance.
data "aws_ssm_parameter" "al2023" {
  count = var.enable_ec2 ? 1 : 0
  name  = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_security_group" "prototype" {
  count       = var.enable_ec2 ? 1 : 0
  name        = "${var.project}-prototype"
  description = "Acces au prototype depuis une adresse choisie"
  ingress {
    description = "API et site"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.ec2_ingress_cidr]
  }
  ingress {
    description = "Streamlit"
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    cidr_blocks = [var.ec2_ingress_cidr]
  }
  egress {
    description = "Sortie vers Internet"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "prototype" {
  count              = var.enable_ec2 ? 1 : 0
  name               = "${var.project}-prototype"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy" "prototype" {
  count  = var.enable_ec2 ? 1 : 0
  role   = aws_iam_role.prototype[0].id
  policy = data.aws_iam_policy_document.api.json
}

resource "aws_iam_role_policy_attachment" "prototype_ssm" {
  count      = var.enable_ec2 ? 1 : 0
  role       = aws_iam_role.prototype[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "prototype" {
  count = var.enable_ec2 ? 1 : 0
  name  = "${var.project}-prototype"
  role  = aws_iam_role.prototype[0].name
}

resource "aws_instance" "prototype" {
  count                       = var.enable_ec2 ? 1 : 0
  ami                         = data.aws_ssm_parameter.al2023[0].value
  instance_type               = "t3.small"
  iam_instance_profile        = aws_iam_instance_profile.prototype[0].name
  vpc_security_group_ids      = [aws_security_group.prototype[0].id]
  user_data_replace_on_change = true
  user_data                   = file("${path.module}/../../deploy/ec2/user_data.sh")
  metadata_options {
    http_tokens = "required"
  }
  root_block_device {
    encrypted   = true
    volume_size = 20
  }
}
