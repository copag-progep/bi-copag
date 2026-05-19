#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f ".env.local" ]; then
  set -a
  # shellcheck disable=SC1091
  source ".env.local"
  set +a
else
  export DATABASE_URL="${DATABASE_URL:-sqlite:///backend/data/analyticsei-local.db}"
  export JWT_SECRET_KEY="${JWT_SECRET_KEY:-dev-local-troque-se-quiser}"
  export DEFAULT_ADMIN_NAME="${DEFAULT_ADMIN_NAME:-Administrador Local}"
  export DEFAULT_ADMIN_EMAIL="${DEFAULT_ADMIN_EMAIL:-admin.local@ufc.br}"
  export DEFAULT_ADMIN_PASSWORD="${DEFAULT_ADMIN_PASSWORD:-admin123}"
  export API_UPLOAD_KEY="${API_UPLOAD_KEY:-dev-upload-key}"
  export AUTO_IMPORT_SAMPLE_DATA="${AUTO_IMPORT_SAMPLE_DATA:-true}"
  export DISABLE_STARTUP_PRECOMPUTE="${DISABLE_STARTUP_PRECOMPUTE:-true}"
  export ANALYTICS_LOOKBACK_DAYS="${ANALYTICS_LOOKBACK_DAYS:-120}"
  export PRECOMPUTE_COOLDOWN_SECS="${PRECOMPUTE_COOLDOWN_SECS:-120}"
fi

if [ ! -d ".venv" ]; then
  echo "Criando ambiente virtual Python em .venv..."
  python3 -m venv .venv
fi

if ! .venv/bin/python -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "Instalando dependências Python..."
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi

echo "Subindo API local em http://127.0.0.1:8000"
echo "Login local padrão: ${DEFAULT_ADMIN_EMAIL:-admin.local@ufc.br} / ${DEFAULT_ADMIN_PASSWORD:-admin123}"
.venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
