#!/usr/bin/env bash
# =============================================================================
# CẬP NHẬT PHIÊN BẢN (một lệnh, gần như không gián đoạn).
#   deploy/scripts/update.sh              # git pull + build + sao lưu CSDL + migrate + thay container
#   deploy/scripts/update.sh --no-pull    # dùng mã nguồn hiện có (đã chép bằng tay)
#   deploy/scripts/update.sh --no-backup  # bỏ bước sao lưu CSDL trước cập nhật (không khuyến nghị)
#
# Cơ chế: image mới được build trong khi bản cũ vẫn phục vụ; migrate chạy bằng container tạm;
# sau đó chạy song song 2 container web, chờ bản mới "healthy", rồi dừng bản cũ. nginx tự
# phân giải lại tên "web" (resolver Docker) nên không cần khởi động lại.
# Lưu ý: migration làm thay đổi cấu trúc không tương thích ngược có thể gây lỗi ngắn ở bản cũ
#        trong vài giây chuyển đổi – với thay đổi lớn, nên báo bảo trì.
# collectstatic chạy lúc build image; entrypoint chép static mới sang volume dùng chung.
# =============================================================================
set -euo pipefail
# shellcheck source=_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
require_env_file

PULL=1 BACKUP=1
for a in "$@"; do
  case "$a" in
    --no-pull) PULL=0 ;;
    --no-backup) BACKUP=0 ;;
    *) die "Tham số lạ: $a" ;;
  esac
done

cd "$APP_DIR"
if [[ "$PULL" == "1" ]]; then
  if [[ -d .git ]]; then
    log "Lấy mã nguồn mới (git pull --ff-only)..."
    git pull --ff-only
    log "Phiên bản: $(git log -1 --format='%h %ci %s')"
  else
    warn "Không phải kho git – bỏ qua git pull (dùng --no-pull để ẩn cảnh báo)."
  fi
fi

log "Build image mới (bản đang chạy vẫn phục vụ)..."
dc build --pull web backup

# Lần đầu (chưa có container web) -> khởi động bình thường
if [[ -z "$(dc ps -q web)" ]]; then
  log "Chưa có web đang chạy -> docker compose up -d"
  dc up -d
  exit 0
fi

if [[ "$BACKUP" == "1" ]]; then
  log "Sao lưu CSDL trước khi cập nhật..."
  "${DEPLOY_DIR}/scripts/backup.sh" db
fi

log "Chạy migrate bằng container tạm (image mới)..."
dc run --rm --no-deps -T web python manage.py migrate --noinput

old_ids="$(dc ps -q web)"
log "Khởi động container web mới song song với bản cũ..."
dc up -d --no-deps --no-recreate --scale web=2 web

new_id=""
for id in $(dc ps -q web); do
  grep -q "$id" <<<"$old_ids" || new_id="$id"
done
[[ -n "$new_id" ]] || die "Không tìm thấy container mới"

log "Chờ container mới healthy (tối đa 180 giây)..."
ok=0
for _ in $(seq 1 90); do
  st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$new_id" 2>/dev/null || echo missing)"
  if [[ "$st" == "healthy" ]]; then ok=1; break; fi
  if [[ "$st" == "unhealthy" || "$st" == "exited" || "$st" == "missing" ]]; then break; fi
  sleep 2
done

if [[ "$ok" != "1" ]]; then
  warn "Container mới không healthy (trạng thái: ${st}). Hủy cập nhật, giữ bản cũ."
  docker logs --tail 50 "$new_id" || true
  docker stop "$new_id" >/dev/null && docker rm "$new_id" >/dev/null
  dc up -d --no-deps --no-recreate --scale web=1 web
  die "Cập nhật thất bại – website vẫn chạy bản cũ. Xem nhật ký ở trên."
fi

log "Dừng container cũ (graceful, phục vụ nốt yêu cầu đang xử lý)..."
for id in $old_ids; do
  docker stop -t 40 "$id" >/dev/null && docker rm "$id" >/dev/null
done
dc up -d --no-deps --no-recreate --scale web=1 web

log "Cập nhật các dịch vụ khác nếu cấu hình thay đổi (nginx, backup...)..."
dc up -d --no-deps nginx backup certbot redis db
dc exec -T nginx nginx -s reload || true
docker image prune -f >/dev/null || true

log "Hoàn tất. Kiểm tra: curl -fsS https://$(env_get DOMAIN localhost)/healthz"
