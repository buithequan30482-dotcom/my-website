# Quy trình vận hành định kỳ – Website di tích Đặc khu Vân Đồn

Áp dụng cho cán bộ kỹ thuật vận hành VPS. Mọi lệnh chạy tại thư mục gốc dự án (vd `/opt/vandon`) bằng user
thuộc nhóm `docker`. Cài đặt ban đầu, sao lưu/phục hồi chi tiết: xem [README.md](../README.md).

Căn cứ: TR mục 8.2 (bản vá hằng tháng), 8.3 (sao lưu, RPO ≤24h, RTO ≤4h), 8.5 (giám sát, nhật ký).

---

## 1. Hằng ngày (5 phút, buổi sáng)

| # | Việc | Lệnh / cách làm | Đạt khi |
|---|---|---|---|
| 1 | Website hoạt động | Mở `https://<DOMAIN>/healthz` hoặc xem email của dịch vụ giám sát uptime | Trả `ok`, không có cảnh báo trong 24h |
| 2 | Trạng thái dịch vụ | `docker compose ps` | Cả 6 dịch vụ `running`; web, db, redis, nginx `healthy` |
| 3 | Sao lưu đêm qua | `docker compose exec backup cat /backups/logs/last_status.txt` | Dòng ngày hôm nay, `OK` |
| 4 | Lỗi ứng dụng | `docker compose logs --since 24h web \| grep -E " ERROR \| 500 " \| tail -n 20` và hộp thư `DJANGO_ADMINS` | Không có lỗi lặp lại |
| 5 | Nội dung chờ xử lý | Khu quản trị → Thống kê → Kiểm duyệt nhanh | Góp ý/đánh giá được xử lý theo quy định của Phòng VHXH |

Nếu bước 3 không `OK`: `docker compose exec backup tail -n 80 /backups/logs/backup.log`, khắc phục, rồi `make backup`.

## 2. Hằng tuần (20 phút, đầu tuần)

| # | Việc | Lệnh / cách làm | Đạt khi |
|---|---|---|---|
| 1 | Bản media đầy đủ đã tạo | `make backup-list` | Có `media/full-*` của tuần này |
| 2 | Kho ngoài nhận đủ bản | `docker compose run --rm backup rclone ls "$RCLONE_REMOTE" --config /config/rclone/rclone.conf \| tail` (thay `$RCLONE_REMOTE` bằng giá trị trong `.env`) | Có bản CSDL mới nhất và media tuần này |
| 3 | Dung lượng đĩa | `df -h /` và `docker system df` | Ổ gốc dùng < 75% |
| 4 | Nhật ký nginx bất thường | `docker compose logs --since 168h nginx \| grep -c ' 429 '`; `... \| grep -c ' 5[0-9][0-9] '` | Không tăng đột biến so với tuần trước |
| 5 | Tài nguyên | `docker stats --no-stream` | web < 1,2 GB RAM; không container nào sát giới hạn liên tục |
| 6 | Đăng nhập SSH lạ | `last -n 20`; `sudo grep -c "Failed" /var/log/auth.log` | Không có phiên lạ |

Ổ đĩa > 75%: dọn image cũ `docker image prune -f`; builder cache `docker builder prune -f`; xem dung lượng media/sao
lưu (`make backup-list`); cân nhắc giảm `BACKUP_KEEP_DAYS`/`MEDIA_KEEP_WEEKS` (không dưới mức TR 8.3) hoặc nâng ổ đĩa.

## 3. Hằng tháng (1–2 giờ, có thông báo bảo trì nếu cần khởi động lại)

| # | Việc | Lệnh / cách làm |
|---|---|---|
| 1 | Bản vá hệ điều hành | `sudo apt-get update && sudo apt-get upgrade -y`; nếu có `/var/run/reboot-required` → hẹn giờ thấp điểm `sudo reboot` (các container tự chạy lại nhờ `restart: unless-stopped`) |
| 2 | Bản vá image nền | `docker compose pull nginx db redis certbot` → `make update ARGS=--no-pull` (build lại web/backup với python:3.13-slim, postgres:16 mới nhất cùng nhánh) |
| 3 | Bản vá thư viện Python | Kiểm tra thông báo bảo mật Django (https://www.djangoproject.com/weblog/) và các gói trong `requirements.txt`; nâng phiên bản trên **staging** → `python manage.py test` → cập nhật chính thức bằng `make update` |
| 4 | Chứng chỉ SSL | `docker compose run --rm --entrypoint certbot certbot certificates` → còn hạn > 30 ngày (tự gia hạn khi < 30 ngày; nếu còn < 20 ngày là gia hạn tự động đang lỗi – xem `docker compose logs certbot`) |
| 5 | Kiểm tra bảo mật Django | `make check` (`manage.py check --deploy`) – không có cảnh báo mới |
| 6 | Tường lửa | `sudo ufw status verbose` – chỉ SSH, 80, 443 |
| 7 | Kiểm tra bản sao lưu đọc được | `docker compose exec backup sh -c 'f=$(ls -1 /backups/db/vandon-*.dump \| tail -n1); pg_restore --list "$f" \| head -n 5'` |
| 8 | Rà tài khoản quản trị | Khu quản trị → Người dùng: khóa tài khoản cán bộ đã nghỉ/chuyển công tác; superuser đều đã bật OTP |
| 9 | Nhật ký thao tác | Khu quản trị → Nhật ký thao tác (AuditLog): rà xóa/xuất bản bất thường |
| 10 | Ghi sổ vận hành | Ngày, người thực hiện, phiên bản đã cập nhật, sự cố, dung lượng đĩa |

## 4. Hằng quý / trước nghiệm thu

- **Diễn tập phục hồi** theo README mục 8.4: đo RPO (≤ 24 giờ) và RTO (≤ 4 giờ), lập biên bản.
- Kiểm tra lại `.env` và `deploy/rclone/rclone.conf` lưu ngoài VPS còn khớp bản đang dùng.
- Xem xét đổi mật khẩu CSDL/khóa kho ngoài nếu có thay đổi nhân sự vận hành.

## 5. Gia hạn chứng chỉ – cơ chế và kiểm tra

- Container `certbot` chạy `certbot renew` 12 giờ/lần; Let's Encrypt chỉ gia hạn khi chứng chỉ còn < 30 ngày.
- nginx tự `reload` 6 giờ/lần để nạp chứng chỉ mới.
- Ép gia hạn thử (không ghi đè): `docker compose run --rm --entrypoint certbot certbot renew --dry-run --webroot -w /var/www/certbot`.
- Email cảnh báo hết hạn gửi tới `LETSENCRYPT_EMAIL`.

## 6. Sự cố – trình tự xử lý nhanh

1. `docker compose ps` → dịch vụ nào không `running/healthy`.
2. `docker compose logs --tail 100 <dịch vụ>`.
3. Thử `docker compose restart <dịch vụ>`; nếu web lỗi sau cập nhật → quay lại phiên bản trước (README mục 9).
4. Mất dữ liệu / hỏng CSDL → `make restore DATE=<ngày gần nhất tốt>` (README mục 8.3).
5. Ghi nhận sự cố: thời điểm phát hiện, nguyên nhân, thời gian khắc phục (đối chiếu chỉ tiêu khả dụng 99,5%/tháng – TR NFR-05).

## 7. Bảng tra lệnh

| Mục đích | Lệnh |
|---|---|
| Trạng thái | `make ps` |
| Nhật ký | `make logs` / `make logs-web` |
| Sao lưu ngay | `make backup` |
| Danh sách bản sao lưu | `make backup-list` |
| Phục hồi | `make restore DATE=YYYYMMDD` |
| Cập nhật phiên bản | `make update` |
| Tạo superuser | `make createsuperuser` |
| Django shell | `make shell` |
| psql | `make dbshell` |
| Kiểm thử | `make test` |
