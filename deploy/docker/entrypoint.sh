#!/usr/bin/env bash
# =============================================================================
# Entrypoint container "web":
#   1. Chờ CSDL sẵn sàng (tối đa DB_WAIT_SECONDS giây)
#   2. Đồng bộ tệp tĩnh đã build sang volume dùng chung với nginx
#   3. (Chỉ khi chạy gunicorn) migrate; nạp dữ liệu 44 di tích nếu DB trống và AUTO_SEED=1
#   4. Chạy lệnh được truyền vào (mặc định: gunicorn)
# Lệnh một lần, ví dụ `docker compose run --rm web python manage.py shell`, chỉ thực hiện bước 1.
# =============================================================================
set -euo pipefail

log() { printf '[entrypoint %s] %s\n' "$(date '+%F %T')" "$*"; }

APP_HOME="${APP_HOME:-/app}"
cd "$APP_HOME"

# ---- 1. Chờ CSDL ----
DB_WAIT_SECONDS="${DB_WAIT_SECONDS:-60}"
log "Chờ CSDL (tối đa ${DB_WAIT_SECONDS}s)..."
python - <<'PY'
import os, sys, time
import django
django.setup()
from django.db import connection
deadline = time.time() + int(os.environ.get("DB_WAIT_SECONDS", "60"))
while True:
    try:
        connection.ensure_connection()
        break
    except Exception as exc:  # noqa: BLE001
        if time.time() > deadline:
            print(f"Không kết nối được CSDL: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(2)
PY
log "CSDL sẵn sàng."

is_server=0
case "${1:-}" in
  gunicorn|*/gunicorn) is_server=1 ;;
esac

if [[ "$is_server" == "1" ]]; then
  # ---- 2. Tệp tĩnh: chép (không xóa bản cũ) để trang đang mở vẫn tải được tệp băm cũ khi cập nhật ----
  if [[ -n "${STATIC_SHARED_DIR:-}" && -d "${STATIC_SHARED_DIR}" && -w "${STATIC_SHARED_DIR}" ]]; then
    cp -a "$APP_HOME/staticfiles/." "${STATIC_SHARED_DIR}/"
    log "Đã đồng bộ static -> ${STATIC_SHARED_DIR}"
  fi

  # Thư mục media phải ghi được (ảnh tải lên, ảnh WebP sinh tự động)
  mkdir -p "${MEDIA_ROOT:-/srv/media}" || true
  if [[ ! -w "${MEDIA_ROOT:-/srv/media}" ]]; then
    log "CẢNH BÁO: ${MEDIA_ROOT:-/srv/media} không ghi được bởi UID $(id -u). Sửa: chown -R 10001:10001 <volume media>"
  fi

  # ---- 3. Bản dịch: chỉ biên dịch khi có .po mà thiếu .mo và thư mục ghi được (bình thường đã làm lúc build) ----
  if [[ "${COMPILE_MESSAGES:-0}" == "1" ]]; then
    if command -v msgfmt >/dev/null 2>&1 && [[ -w "$APP_HOME/locale" ]]; then
      python manage.py compilemessages --ignore 'staticfiles/*' || log "compilemessages lỗi (bỏ qua)"
    else
      log "Bỏ qua compilemessages (thiếu gettext hoặc locale chỉ đọc – .mo đã biên dịch lúc build)."
    fi
  fi

  # ---- 4. Migrate ----
  if [[ "${RUN_MIGRATIONS:-1}" == "1" ]]; then
    log "Chạy migrate..."
    python manage.py migrate --noinput
  fi

  # ---- 5. Nạp dữ liệu lần đầu ----
  if [[ "${AUTO_SEED:-0}" == "1" ]]; then
    count="$(python manage.py shell -c 'from heritage.models import DiTich; print(DiTich.objects.count())' 2>/dev/null | tail -n1 || echo error)"
    if [[ "$count" == "0" ]]; then
      log "CSDL chưa có di tích -> chạy load_vandon (nạp 44 di tích + nhóm quyền)..."
      python manage.py load_vandon
    else
      log "Bỏ qua load_vandon (số di tích hiện có: ${count})."
    fi
  fi
fi

log "Khởi chạy: $*"
exec "$@"
