#!/usr/bin/env bash
# Hàm dùng chung cho các script vận hành (được "source", không chạy trực tiếp).
# shellcheck disable=SC2034

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"
ENV_FILE="${APP_DIR}/.env"
COMPOSE_FILE_PATH="${APP_DIR}/docker-compose.yml"

log()  { printf '\033[1;36m[%s]\033[0m %s\n' "$(date '+%F %T')" "$*"; }
warn() { printf '\033[1;33m[CẢNH BÁO]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[LỖI]\033[0m %s\n' "$*" >&2; exit 1; }

# docker compose luôn chạy với thư mục gốc dự án (đọc ./.env tại đó)
dc() { docker compose --project-directory "${APP_DIR}" -f "${COMPOSE_FILE_PATH}" "$@"; }

# Đọc một biến từ ./.env (không "source" cả tệp để tránh chạy nội dung lạ)
env_get() {
  local key="$1" default="${2:-}" val
  val="$(grep -E "^${key}=" "${ENV_FILE}" 2>/dev/null | tail -n1 | cut -d= -f2- || true)"
  val="${val%\"}"; val="${val#\"}"; val="${val%\'}"; val="${val#\'}"
  printf '%s' "${val:-$default}"
}

require_env_file() {
  [[ -f "${ENV_FILE}" ]] || die "Chưa có ${ENV_FILE}. Chạy deploy/scripts/first-run.sh (hoặc: cp .env.example .env rồi sửa)."
}

confirm() {
  local prompt="${1:-Tiếp tục?}" ans
  if [[ "${ASSUME_YES:-0}" == "1" ]]; then return 0; fi
  read -r -p "${prompt} [gõ 'yes' để xác nhận]: " ans
  [[ "${ans}" == "yes" ]]
}

# Đang chạy bên trong container backup?
in_backup_container() { [[ -d /backups && -n "${PGHOST:-}" && ! -f "${ENV_FILE}" ]]; }
