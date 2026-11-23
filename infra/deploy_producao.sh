#!/usr/bin/env bash
# Deploy em produção — só a squad de plataforma executa.
set -euo pipefail
terraform -chdir="$(dirname "$0")/terraform" apply
