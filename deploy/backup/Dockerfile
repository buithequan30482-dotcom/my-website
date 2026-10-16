# Image sao lưu: pg_dump/pg_restore (cùng phiên bản PostgreSQL 16) + GNU tar + rclone + cron (busybox crond)
FROM postgres:16-alpine
RUN apk add --no-cache bash tar gzip rclone tzdata coreutils findutils
ENV TZ=Asia/Ho_Chi_Minh
COPY --chmod=0755 backup-entrypoint.sh /usr/local/bin/backup-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/backup-entrypoint.sh"]
