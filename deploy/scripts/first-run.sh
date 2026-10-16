#!/usr/bin/env bash
# =============================================================================
# CHẠY LẦN ĐẦU trên VPS (sau deploy/scripts/install.sh). Chạy tại thư mục gốc dự án:
#
#   DOMAIN=ditich.vandon.gov.vn LETSENCRYPT_EMAIL=it@vandon.gov.vn deploy/scripts/first-run.sh
#
# Thực hiện:
#   1. Tạo ./.env từ .env.example (nếu chưa có): DJANGO_SECRET_KEY, mật khẩu CSDL, đường dẫn quản trị
#      ngẫu nhiên; điền DOMAIN / ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS. Chưa có chứng chỉ -> DJANGO_HTTPS=0
#      tạm thời (init-letsencrypt.sh sẽ nhắc bật lại 1).
#   2. Build image, khởi động toàn bộ dịch vụ (nginx ở chế độ HTTP-only khi chưa có chứng chỉ)
#   3. migrate, nạp dữ liệu 44 di tích + nhóm quyền: python manage.py load_vandon
#   4. Tạo tài khoản quản trị hệ thống (superuser) – hỏi tên, email, mật khẩu (≥10 ký tự)
# Chạy lại an toàn: không ghi đè .env đã có; load_vandon chỉ chạy khi CSDL chưa có di tích
# (ép chạy lại: FORCE_SEED=1); bỏ bước tạo superuser: SKIP_SUPERUSER=1.
# =============================================================================
set -euo pipefail
# shellcheck source=_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

command -v docker >/dev/null 2>&1 || die "Chưa có Docker. Chạy: sudo deploy/scripts/install.sh"
docker compose version >/dev/null 2>&1 || die "Thiếu docker compose plugin"
command -v openssl >/dev/null 2>&1 || die "Thiếu openssl (apt-get install -y openssl)"
cd "${APP_DIR}"

# ---- 1. .env ----
setv() { # thay dòng KEY=... trong .env (giá trị không chứa ký tự '|')
  if grep -qE "^$1=" "${ENV_FILE}"; then sed -i "s|^$1=.*|$1=$2|" "${ENV_FILE}"; else echo "$1=$2" >> "${ENV_FILE}"; fi
}
if [[ -f "${ENV_FILE}" ]]; then
  log "Đã có ${ENV_FILE} – giữ nguyên."
else
  [[ -f "${APP_DIR}/.env.example" ]] || die "Thiếu .env.example"
  log "Tạo ${ENV_FILE} từ .env.example (sinh bí mật ngẫu nhiên)..."
  umask 077
  cp "${APP_DIR}/.env.example" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
  secret="$(openssl rand -base64 96 | tr -dc 'A-Za-z0-9' | head -c 64)"
  dbpass="$(openssl rand -hex 24)"
  admin_path="quan-tri-$(openssl rand -hex 4)/"
  domain="${DOMAIN:-}"
  if [[ -z "$domain" ]]; then
    read -r -p "Tên miền website (vd ditich.vandon.gov.vn; để trống = dùng IP/localhost thử nghiệm): " domain || true
  fi
  domain="${domain:-localhost}"
  setv DJANGO_SECRET_KEY "$secret"
  setv POSTGRES_PASSWORD "$dbpass"
  setv ADMIN_URL "$admin_path"
  setv DOMAIN "$domain"
  setv DJANGO_ALLOWED_HOSTS "$domain"
  setv DJANGO_CSRF_TRUSTED_ORIGINS "https://$domain,http://$domain"
  # Chưa có chứng chỉ: tắt chuyển hướng HTTPS phía Django để chạy được qua HTTP
  setv DJANGO_HTTPS 0
  [[ -n "${LETSENCRYPT_EMAIL:-}" ]] && setv LETSENCRYPT_EMAIL "${LETSENCRYPT_EMAIL}"
  log "Đường dẫn khu quản trị: /${admin_path}  (LƯU LẠI – có trong ${ENV_FILE})"
fi
mkdir -p "${DEPLOY_DIR}/rclone"

# ---- 2. Build + khởi động ----
log "Build image và khởi động dịch vụ (lần đầu mất vài phút)..."
dc build
dc up -d

log "Chờ web sẵn sàng..."
ok=0
for _ in $(seq 1 60); do
  if dc exec -T web python /usr/local/bin/healthcheck.py >/dev/null 2>&1; then ok=1; break; fi
  sleep 3
done
[[ "$ok" == "1" ]] || { dc logs --tail 80 web; die "web chưa sẵn sàng sau 3 phút – xem nhật ký ở trên"; }

# ---- 3. migrate + nạp dữ liệu ----
log "migrate..."
dc exec -T web python manage.py migrate --noinput
count="$(dc exec -T web python manage.py shell -c 'from heritage.models import DiTich; print(DiTich.objects.count())' | tail -n1 | tr -d '\r')"
if [[ "$count" == "0" || "${FORCE_SEED:-0}" == "1" ]]; then
  log "Nạp dữ liệu 44 di tích + nhóm quyền: python manage.py load_vandon"
  dc exec -T web python manage.py load_vandon
else
  log "CSDL đã có ${count} di tích – bỏ qua load_vandon (ép chạy lại: FORCE_SEED=1)."
fi

# ---- 4. Superuser ----
if [[ "${SKIP_SUPERUSER:-0}" != "1" ]]; then
  has_su="$(dc exec -T web python manage.py shell -c 'from django.contrib.auth import get_user_model; print(get_user_model().objects.filter(is_superuser=True).exists())' | tail -n1 | tr -d '\r')"
  if [[ "$has_su" == "True" ]]; then
    log "Đã có tài khoản quản trị hệ thống – bỏ qua (tạo thêm: make createsuperuser)."
  else
    log "Tạo tài khoản quản trị hệ thống (superuser)..."
    dc exec web python manage.py createsuperuser
  fi
fi

domain="$(env_get DOMAIN localhost)"
cat <<EOF

=====================================================================
 Đã chạy xong lần đầu.
  - Website (HTTP tạm thời):   http://${domain}/
  - Khu quản trị:              http://${domain}/$(env_get ADMIN_URL quan-tri-vd/ | sed 's#^/*##')
  - Lần đăng nhập đầu tiên superuser phải thiết lập OTP (ứng dụng Authenticator trên điện thoại).
 Tiếp theo:
  1. Trỏ DNS ${domain} về IP VPS, rồi: deploy/scripts/init-letsencrypt.sh
  2. Sau khi có HTTPS: đặt DJANGO_HTTPS=1 trong .env -> docker compose up -d web
  3. Cấu hình kho sao lưu ngoài (RCLONE_REMOTE) – xem README mục "Sao lưu".
=====================================================================
EOF
