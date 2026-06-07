#!/usr/bin/env bash
# git_push.sh -- Execute no servidor para enviar o commit atual
set -euo pipefail
echo "Enviando branch 'main' para origin..."
git push origin main
echo "OK"
