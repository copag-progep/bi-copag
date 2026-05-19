#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

required_python_msg() {
  cat <<'EOF'
Python 3.12 não foi encontrado.

Instale com Homebrew:
  brew install python@3.12

Depois rode novamente:
  ./scripts/dev_backend.sh

Se preferir usar outro Python 3.12, informe o caminho assim:
  PYTHON_BIN=/caminho/para/python3.12 ./scripts/dev_backend.sh
EOF
}

python_is_312_plus() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1
}

select_python() {
  if [ -n "${PYTHON_BIN:-}" ]; then
    if python_is_312_plus "$PYTHON_BIN"; then
      echo "$PYTHON_BIN"
      return 0
    fi
    echo "PYTHON_BIN informado não é Python 3.12+: $PYTHON_BIN" >&2
    return 1
  fi

  for candidate in python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && python_is_312_plus "$candidate"; then
      command -v "$candidate"
      return 0
    fi
  done

  return 1
}

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

if ! SELECTED_PYTHON="$(select_python)"; then
  required_python_msg
  exit 1
fi

if [ -d ".venv" ] && ! .venv/bin/python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1; then
  backup=".venv.py$(.venv/bin/python -c 'import sys; print(f"{sys.version_info.major}{sys.version_info.minor}")')-backup-$(date +%Y%m%d%H%M%S)"
  echo "Ambiente virtual existente usa Python antigo. Movendo .venv para ${backup}..."
  mv .venv "$backup"
fi

if [ ! -d ".venv" ]; then
  echo "Criando ambiente virtual Python em .venv com $("$SELECTED_PYTHON" --version)..."
  "$SELECTED_PYTHON" -m venv .venv
fi

if ! .venv/bin/python -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "Instalando dependências Python..."
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi

echo "Subindo API local em http://127.0.0.1:8000"
echo "Login local padrão: ${DEFAULT_ADMIN_EMAIL:-admin.local@ufc.br} / ${DEFAULT_ADMIN_PASSWORD:-admin123}"
.venv/bin/uvicorn backend.main:app \
  --reload \
  --reload-dir backend \
  --reload-exclude ".venv/*" \
  --reload-exclude ".venv.*-backup-*/*" \
  --reload-exclude "node_modules/*" \
  --reload-exclude "frontend/node_modules/*" \
  --reload-exclude "frontend/dist/*" \
  --loop asyncio \
  --host 127.0.0.1 \
  --port 8000
