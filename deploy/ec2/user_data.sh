#!/bin/bash
# Prépare l'instance : l'équipe se connecte ensuite via Session Manager (docs/runbook.md).
set -euxo pipefail
dnf install -y docker git
systemctl enable --now docker
mkdir -p /usr/libexec/docker/cli-plugins
curl -fsSL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/libexec/docker/cli-plugins/docker-compose
chmod +x /usr/libexec/docker/cli-plugins/docker-compose
