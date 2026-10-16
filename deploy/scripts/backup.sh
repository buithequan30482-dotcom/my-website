#!/usr/bin/env bash
# =============================================================================
# SAO LƯU (TR 8.3): CSDL hằng ngày (giữ BACKUP_KEEP_DAYS bản, mặc định 30);
#                   media: bản đầy đủ hằng tuần + bản gia tăng hằng ngày; đẩy ra kho ngoài (rclone).
#
# Cách dùng (trên VPS, trong thư mục dự án):
#   deploy/scripts/backup.sh            # = all: db + media + đẩy kho ngoài + dọn bản cũ
#   deploy/scripts/backup.sh db         # chỉ CSDL
#   deploy/scripts/backup.sh media      # media (tự chọn đầy đủ/gia tăng)
#   deploy/scripts/backup.sh media-full # ép tạo bản media đầy đủ
#   deploy/scripts/backup.sh remote     # chỉ đẩy ra kho ngoài
#   deploy/scripts/backup.sh list       # liệt kê bản sao lưu
# Trên máy chủ, script tự chuyển vào container "backup"; lịch tự động do cron trong container đó.
#
# Cấu trúc trong volume backups (/backups):
#   db/vandon-YYYYMMDD-HHMMSS.dump                    pg_dump định dạng custom (-Fc)
#   media/full-YYYYMMDD-HHMMSS.tar.gz (+ .snar)       bản đầy đủ (GNU tar --listed-incremental)
#   media/inc-YYYYMMDD-HHMMSS-of-<FULLID>.tar.gz      thay đổi kể từ bản đầy đủ <FULLID> (vi sai)
# =============================================================================
set -euo pipefail
# shellcheck source=_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

# ---- Ngoài container: chuyển lệnh vào container backup ----
if ! in_backup_container; then
  require_env_file
  if [[ -n "$(dc ps -q backup 2>/dev/null)" ]]; then
    dc exec -T backup /scripts/backup.sh "$@"; exit $?
  else
    dc run --rm -T backup /scripts/backup.sh "$@"; exit $?
  fi
fi

# ---- Trong container backup ----
B=/backups
MEDIA=/srv/media
KEEP="${BACKUP_KEEP_DAYS:-30}"
KEEP_WEEKS="${MEDIA_KEEP_WEEKS:-5}"
FULL_WEEKDAY="${MEDIA_FULL_WEEKDAY:-7}"   # 1=Thứ Hai ... 7=Chủ nhật
TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$B/db" "$B/media" "$B/logs"

# Không chạy chồng 2 phiên sao lưu
exec 9>"$B/.lock"
flock -n 9 || die "Đang có phiên sao lưu khác chạy."

backup_db() {
  local out="$B/db/vandon-${TS}.dump"
  log "CSDL: pg_dump ${PGDATABASE} -> ${out}"
  pg_dump -Fc --no-owner --no-privileges -Z 6 -f "${out}.part"
  pg_restore --list "${out}.part" >/dev/null   # kiểm tra tệp đọc được
  mv "${out}.part" "${out}"
  sha256sum "${out}" > "${out}.sha256"
  log "CSDL: xong ($(du -h "${out}" | cut -f1))"
  # Giữ KEEP bản mới nhất
  find "$B/db" -maxdepth 1 -name 'vandon-*.dump' -printf '%f\n' | sort -r | tail -n "+$((KEEP + 1))" |
    while read -r f; do rm -f "$B/db/$f" "$B/db/$f.sha256"; log "CSDL: xóa bản cũ $f"; done
}

latest_full_id() {
  find "$B/media" -maxdepth 1 -name 'full-*.tar.gz' -printf '%f\n' | sort | tail -n1 |
    sed -e 's/^full-//' -e 's/\.tar\.gz$//'
}

backup_media_full() {
  local id="$TS" out="$B/media/full-${TS}.tar.gz"
  log "Media: bản ĐẦY ĐỦ -> ${out}"
  rm -f "$B/media/full-${id}.snar"
  tar --listed-incremental="$B/media/full-${id}.snar" -czf "${out}.part" -C "$MEDIA" .
  mv "${out}.part" "${out}"
  log "Media: xong ($(du -h "${out}" | cut -f1))"
  prune_media
}

backup_media_inc() {
  local full_id snap out
  full_id="$(latest_full_id)"
  [[ -n "$full_id" ]] || { backup_media_full; return; }
  out="$B/media/inc-${TS}-of-${full_id}.tar.gz"
  snap="$(mktemp)"
  cp "$B/media/full-${full_id}.snar" "$snap"     # vi sai so với bản đầy đủ gần nhất
  log "Media: bản GIA TĂNG (so với full-${full_id}) -> ${out}"
  tar --listed-incremental="$snap" -czf "${out}.part" -C "$MEDIA" .
  rm -f "$snap"
  mv "${out}.part" "${out}"
  log "Media: xong ($(du -h "${out}" | cut -f1))"
}

backup_media_auto() {
  if [[ "$(date +%u)" == "$FULL_WEEKDAY" || -z "$(latest_full_id)" ]]; then
    backup_media_full
  else
    backup_media_inc
  fi
}

prune_media() {
  # Giữ KEEP_WEEKS bản đầy đủ gần nhất cùng các bản gia tăng của chúng
  local keep_ids
  keep_ids="$(find "$B/media" -maxdepth 1 -name 'full-*.tar.gz' -printf '%f\n' | sort -r | head -n "$KEEP_WEEKS" |
              sed -e 's/^full-//' -e 's/\.tar\.gz$//')"
  local f id
  for f in "$B"/media/full-*.tar.gz; do
    [[ -e "$f" ]] || continue
    id="$(basename "$f" .tar.gz)"; id="${id#full-}"
    if ! grep -qx "$id" <<<"$keep_ids"; then
      rm -f "$f" "$B/media/full-${id}.snar" "$B"/media/inc-*-of-"${id}".tar.gz
      log "Media: xóa bộ cũ full-${id} (+ gia tăng)"
    fi
  done
}

push_remote() {
  if [[ -z "${RCLONE_REMOTE:-}" ]]; then
    log "Kho ngoài: chưa cấu hình RCLONE_REMOTE -> bỏ qua (KHUYẾN NGHỊ cấu hình, TR 8.3)."
    return 0
  fi
  [[ -f "${RCLONE_CONFIG:-/config/rclone/rclone.conf}" ]] || die "Thiếu rclone.conf (deploy/rclone/rclone.conf)"
  log "Kho ngoài: rclone copy -> ${RCLONE_REMOTE}"
  # copy (không sync): bản trên kho ngoài không bị xóa nếu VPS bị xâm nhập/xóa nhầm
  rclone copy "$B" "${RCLONE_REMOTE}" --exclude '.lock' --exclude 'logs/**' --exclude '*.part' \
    --transfers 2 --checkers 4 --retries 5 --low-level-retries 10 --stats-one-line -v 2>&1 | tail -n 3
  # Dọn kho ngoài sau RCLONE_KEEP_DAYS ngày (0 = không dọn)
  if [[ "${RCLONE_KEEP_DAYS:-90}" != "0" ]]; then
    rclone delete "${RCLONE_REMOTE}" --min-age "${RCLONE_KEEP_DAYS:-90}d" --exclude 'media/full-*.snar' || warn "Không dọn được kho ngoài"
  fi
  log "Kho ngoài: xong"
}

list_backups() {
  echo "== CSDL ($B/db) =="
  find "$B/db" -maxdepth 1 -name '*.dump' -printf '%TY-%Tm-%Td %TH:%TM  %10s  %f\n' | sort
  echo "== Media ($B/media) =="
  find "$B/media" -maxdepth 1 -name '*.tar.gz' -printf '%TY-%Tm-%Td %TH:%TM  %10s  %f\n' | sort
  df -h "$B" | tail -n1 | awk '{print "Dung lượng volume backups: dùng " $3 " / " $2 " (còn " $4 ")"}'
}

rotate_log() {
  local lf="$B/logs/backup.log"
  if [[ -f "$lf" && $(stat -c %s "$lf") -gt 5242880 ]]; then mv "$lf" "$lf.1"; fi
}

status() {
  echo "$(date '+%F %T') $1" > "$B/logs/last_status.txt"
}

trap 'status "THẤT BẠI (dòng $LINENO)"; rm -f "$B"/db/*.part "$B"/media/*.part' ERR

case "${1:-all}" in
  all)        rotate_log; backup_db; backup_media_auto; push_remote; status "OK"; log "Hoàn tất sao lưu." ;;
  db)         backup_db; status "OK (db)" ;;
  media)      backup_media_auto; status "OK (media)" ;;
  media-full) backup_media_full; status "OK (media-full)" ;;
  remote)     push_remote ;;
  list)       list_backups ;;
  *) die "Tham số không hợp lệ: $1 (all|db|media|media-full|remote|list)" ;;
esac
