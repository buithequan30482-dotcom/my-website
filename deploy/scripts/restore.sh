#!/usr/bin/env bash
# =============================================================================
# PHỤC HỒI từ bản sao lưu theo NGÀY (TR 8.3: RPO ≤ 24h, RTO ≤ 4h).
#
#   deploy/scripts/restore.sh --list                       # liệt kê bản sao lưu
#   deploy/scripts/restore.sh --date 20261015              # phục hồi CSDL + media về ngày 15/10/2026
#   deploy/scripts/restore.sh --date 20261015 --db-only
#   deploy/scripts/restore.sh --date 20261015 --media-only
#   deploy/scripts/restore.sh --date 20261015 --from-remote   # tải từ kho ngoài (rclone) trước
#   Thêm --yes để không hỏi xác nhận (dùng trong diễn tập tự động).
#
# Quy tắc chọn bản: CSDL = bản mới nhất CỦA NGÀY đó (hoặc gần nhất trước đó nếu ngày đó không có);
#                   media = bản đầy đủ gần nhất ≤ ngày + bản gia tăng mới nhất của bộ đó ≤ ngày.
# Trước khi ghi đè, script tự sao lưu trạng thái hiện tại (pre-restore-*) để có thể quay lại.
# =============================================================================
set -euo pipefail
# shellcheck source=_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

usage() { sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

DATE="" DO_DB=1 DO_MEDIA=1 FROM_REMOTE=0 LIST=0 INNER=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --date) DATE="${2:-}"; shift 2 ;;
    --db-only) DO_MEDIA=0; shift ;;
    --media-only) DO_DB=0; shift ;;
    --from-remote) FROM_REMOTE=1; shift ;;
    --list) LIST=1; shift ;;
    --yes|-y) export ASSUME_YES=1; shift ;;
    --inner) INNER=1; shift ;;
    -h|--help) usage 0 ;;
    *) warn "Tham số lạ: $1"; usage 1 ;;
  esac
done

# =========================== PHẦN CHẠY TRÊN MÁY CHỦ ===========================
if [[ "$INNER" == "0" ]]; then
  require_env_file
  if [[ "$LIST" == "1" ]]; then exec "${DEPLOY_DIR}/scripts/backup.sh" list; fi
  [[ "$DATE" =~ ^[0-9]{8}$ ]] || die "Cần --date YYYYMMDD (xem --list)"

  warn "Sẽ GHI ĐÈ $( [[ $DO_DB == 1 ]] && echo 'CSDL ' )$( [[ $DO_MEDIA == 1 ]] && echo 'media ' )bằng bản sao lưu ngày ${DATE}."
  warn "Website sẽ tạm dừng trong lúc phục hồi."
  confirm "Xác nhận phục hồi?" || die "Đã hủy."

  t0=$(date +%s)
  log "Dừng web để không có dữ liệu ghi mới..."
  dc stop web
  args=(--inner --date "$DATE")
  [[ $DO_DB == 0 ]] && args+=(--media-only)
  [[ $DO_MEDIA == 0 ]] && args+=(--db-only)
  [[ $FROM_REMOTE == 1 ]] && args+=(--from-remote)
  # Chạy phần phục hồi trong container backup (có pg_restore, GNU tar, rclone)
  set +e
  dc up -d db   # bảo đảm CSDL đang chạy; --no-deps: không khởi động lại web trong lúc phục hồi
  dc run --rm --no-deps -T backup /scripts/restore.sh "${args[@]}"
  rc=$?
  set -e
  log "Khởi động lại web (tự migrate nếu bản sao lưu cũ hơn mã nguồn)..."
  dc up -d web
  [[ $rc -eq 0 ]] || die "Phục hồi lỗi (mã $rc). Bản trước phục hồi nằm trong /backups/*/pre-restore-*"
  log "Phục hồi xong sau $(( ($(date +%s) - t0) / 60 )) phút. Kiểm tra: curl -I https://$(env_get DOMAIN localhost)/healthz"
  exit 0
fi

# ======================= PHẦN CHẠY TRONG CONTAINER BACKUP =======================
B=/backups
MEDIA=/srv/media
TS="$(date +%Y%m%d-%H%M%S)"

if [[ "$FROM_REMOTE" == "1" ]]; then
  [[ -n "${RCLONE_REMOTE:-}" ]] || die "Chưa cấu hình RCLONE_REMOTE"
  log "Tải bản sao lưu từ kho ngoài ${RCLONE_REMOTE} (chỉ tệp đến ngày ${DATE})..."
  rclone copy "${RCLONE_REMOTE}" "$B" --include "db/vandon-*.dump*" --include "media/*" --stats-one-line -v 2>&1 | tail -n 2
fi

# Chọn tệp có ngày (YYYYMMDD trong tên) ≤ DATE, mới nhất
pick_le() { # $1 = thư mục, $2 = tiền tố, $3 = hậu tố
  find "$1" -maxdepth 1 -name "$2*$3" -printf '%f\n' | sort |
    awk -v d="$DATE" -v p="$2" '{ s=substr($0, length(p)+1, 8); if (s <= d) last=$0 } END { if (last) print last }'
}

restore_db() {
  local f
  f="$(pick_le "$B/db" "vandon-" ".dump")"
  [[ -n "$f" ]] || die "Không có bản sao lưu CSDL nào ≤ ${DATE}"
  [[ "$f" == vandon-${DATE}-* ]] || warn "Ngày ${DATE} không có bản CSDL; dùng bản gần nhất trước đó: $f"
  if [[ -f "$B/db/$f.sha256" ]]; then (cd "$B/db" && sha256sum -c "$f.sha256" >/dev/null) || die "Sai checksum $f"; fi
  log "CSDL: sao lưu trạng thái hiện tại -> db/pre-restore-${TS}.dump"
  pg_dump -Fc --no-owner --no-privileges -f "$B/db/pre-restore-${TS}.dump" || warn "Không sao lưu được CSDL hiện tại (bỏ qua)"
  log "CSDL: phục hồi từ $f (xóa và tạo lại CSDL ${PGDATABASE})..."
  psql -v ON_ERROR_STOP=1 -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${PGDATABASE}' AND pid <> pg_backend_pid();" >/dev/null
  dropdb --if-exists "${PGDATABASE}"
  createdb -O "${PGUSER}" -E UTF8 -T template0 "${PGDATABASE}"
  pg_restore --no-owner --no-privileges --exit-on-error -d "${PGDATABASE}" "$B/db/$f"
  log "CSDL: xong."
}

restore_media() {
  local full full_id inc
  full="$(pick_le "$B/media" "full-" ".tar.gz")"
  [[ -n "$full" ]] || die "Không có bản media đầy đủ nào ≤ ${DATE}"
  full_id="${full#full-}"; full_id="${full_id%.tar.gz}"
  inc="$(pick_le "$B/media" "inc-" "-of-${full_id}.tar.gz")"
  log "Media: sao lưu hiện trạng -> media/pre-restore-${TS}.tar.gz"
  tar -czf "$B/media/pre-restore-${TS}.tar.gz" -C "$MEDIA" . || warn "Không sao lưu được media hiện tại (bỏ qua)"
  log "Media: xóa nội dung hiện tại và giải nén $full"
  find "$MEDIA" -mindepth 1 -delete
  tar --listed-incremental=/dev/null -xzf "$B/media/$full" -C "$MEDIA"
  if [[ -n "$inc" ]]; then
    log "Media: áp bản gia tăng $inc"
    tar --listed-incremental=/dev/null -xzf "$B/media/$inc" -C "$MEDIA"
  fi
  chown -R 10001:10001 "$MEDIA"
  log "Media: xong ($(du -sh "$MEDIA" | cut -f1))."
}

[[ "$DO_DB" == "1" ]] && restore_db
[[ "$DO_MEDIA" == "1" ]] && restore_media
log "Phục hồi trong container hoàn tất."
