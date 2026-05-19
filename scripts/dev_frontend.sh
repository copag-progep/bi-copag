#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d "node_modules" ] || [ ! -d "frontend/node_modules" ]; then
  echo "Instalando dependências Node..."
  npm install
fi

export VITE_PROXY_TARGET="${VITE_PROXY_TARGET:-http://127.0.0.1:8000}"

echo "Subindo frontend local em http://127.0.0.1:5173"
echo "Proxy /api apontando para ${VITE_PROXY_TARGET}"
npm run dev --workspace frontend -- --host 127.0.0.1
