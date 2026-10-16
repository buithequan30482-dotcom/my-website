#!/usr/bin/env bash
# =============================================================================
# Container "backup": tạo lịch cron từ biến môi trường rồi chạy crond ở tiền cảnh.
#   BACKUP_CRON  (mặc định "30 2 * * *" = 02:30 hằng ngày, giờ Việt Nam)
# Lệnh tùy ý vẫn chạy được: docker compose run --rm backup /scripts/backup.sh db
# =============================================================================
set -euo pipefail

if [[ $# -gt 0 ]]; then
  exec "$@"
fi

mkdir -p /backups/db /backups/media /backups/logs
CRON="${BACKUP_CRON:-30 2 * * *}"

# crond của busybox không truyền biến môi trường -> lưu lại để backup.sh nạp
export -p | grep -E 'declare -x (PG|POSTGRES_|BACKUP_|MEDIA_|RCLONE|TZ)' > /etc/backup.env || true
chmod 600 /etc/backup.env

cat > /etc/crontabs/root <<EOF
# Sao lưu Website di tích Vân Đồn (sinh tự động bởi backup-entrypoint.sh)
${CRON} . /etc/backup.env; /scripts/backup.sh all >> /backups/logs/backup.log 2>&1
EOF

echo "[backup] Lịch sao lưu: '${CRON}' (TZ=${TZ:-UTC}). Nhật ký: /backups/logs/backup.log"
exec crond -f -l 8 -L /dev/stdout
