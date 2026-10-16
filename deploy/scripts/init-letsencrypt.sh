#!/usr/bin/env bash
# =============================================================================
# CẤP CHỨNG CHỈ HTTPS LẦN ĐẦU (Let's Encrypt, phương thức webroot).
# Điều kiện: bản ghi DNS A/AAAA của DOMAIN (và EXTRA_DOMAINS) đã trỏ về IP VPS; cổng 80 mở.
#
#   deploy/scripts/init-letsencrypt.sh            # cấp thật
#   deploy/scripts/init-letsencrypt.sh --staging  # thử với máy chủ staging (không giới hạn lượt, chứng chỉ không tin cậy)
#
# Sau khi cấp: nginx tự chuyển sang chế độ HTTPS (NGINX_SSL=auto). Gia hạn tự động do container certbot.
# =============================================================================
set -euo pipefail
# shellcheck source=_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
require_env_file

STAGING=0
[[ "${1:-}" == "--staging" ]] && STAGING=1

DOMAIN="$(env_get DOMAIN)"
EXTRA="$(env_get EXTRA_DOMAINS)"
EMAIL="$(env_get LETSENCRYPT_EMAIL)"
[[ -n "$DOMAIN" && "$DOMAIN" != "example.gov.vn" && "$DOMAIN" != "localhost" ]] || die "Chưa đặt DOMAIN (tên miền thật) trong .env"
[[ -n "$EMAIL" ]] || die "Chưa đặt LETSENCRYPT_EMAIL trong .env (nhận cảnh báo hết hạn)"

# Kiểm tra DNS trỏ đúng (cảnh báo, không chặn)
if command -v getent >/dev/null; then
  ip_dns="$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}')"
  ip_me="$(curl -4 -fsS --max-time 5 https://api.ipify.org 2>/dev/null || true)"
  if [[ -n "$ip_me" && "$ip_dns" != "$ip_me" ]]; then
    warn "DNS ${DOMAIN} -> '${ip_dns:-không phân giải được}', IP VPS -> '${ip_me}'. Let's Encrypt sẽ thất bại nếu DNS chưa trỏ đúng."
    confirm "Vẫn tiếp tục?" || exit 1
  fi
fi

log "Bảo đảm nginx đang chạy (chế độ HTTP-only khi chưa có chứng chỉ)..."
dc up -d nginx
sleep 3
curl -fsS --max-time 5 "http://127.0.0.1:$(env_get HTTP_PORT 80)/nginx-health" >/dev/null || die "nginx chưa phản hồi trên cổng 80"

domains=(-d "$DOMAIN")
for d in $EXTRA; do domains+=(-d "$d"); done
staging_arg=()
[[ "$STAGING" == "1" ]] && staging_arg=(--staging)

log "Yêu cầu chứng chỉ cho: ${DOMAIN} ${EXTRA}"
dc run --rm --entrypoint certbot certbot certonly --webroot -w /var/www/certbot \
  --cert-name "$DOMAIN" "${domains[@]}" --email "$EMAIL" --agree-tos --no-eff-email \
  --rsa-key-size 4096 --non-interactive --keep-until-expiring "${staging_arg[@]}"

log "Khởi động lại nginx để bật HTTPS..."
dc restart nginx
dc up -d certbot
sleep 3
if curl -fsS --max-time 10 -o /dev/null "https://${DOMAIN}/nginx-health" 2>/dev/null; then
  log "HTTPS hoạt động: https://${DOMAIN}/"
else
  warn "Chưa truy cập được https://${DOMAIN}/ từ chính VPS (có thể do NAT/hairpin). Kiểm tra từ máy khác."
fi
if [[ "$STAGING" == "1" ]]; then
  warn "Đây là chứng chỉ STAGING. Khi đã ổn: docker compose down; docker volume rm vandon_certs; chạy lại không có --staging."
  exit 0
fi

# Bật HTTPS phía Django (cookie Secure, chuyển hướng HTTPS) và chỉ tin nguồn https://
if [[ "$(env_get DJANGO_HTTPS 0)" != "1" ]]; then
  log "Bật DJANGO_HTTPS=1 trong .env và khởi động lại web..."
  sed -i "s|^DJANGO_HTTPS=.*|DJANGO_HTTPS=1|" "${ENV_FILE}"
  origins="https://${DOMAIN}"
  for d in $EXTRA; do origins="${origins},https://${d}"; done
  sed -i "s|^DJANGO_CSRF_TRUSTED_ORIGINS=.*|DJANGO_CSRF_TRUSTED_ORIGINS=${origins}|" "${ENV_FILE}"
  dc up -d web
fi
log "Xong. Gia hạn tự động: container certbot (12 giờ/lần), nginx nạp lại chứng chỉ 6 giờ/lần."
