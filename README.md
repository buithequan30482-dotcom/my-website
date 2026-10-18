# Website giới thiệu, quảng bá di tích Đặc khu Vân Đồn

Website đa ngôn ngữ (Tiếng Việt, English, 中文) giới thiệu 44 di tích của Đặc khu Vân Đồn (Quảng Ninh): danh mục,
bản đồ, tuyến tham quan, lễ hội, tin tức, đánh giá và góp ý của người dân; khu quản trị tiếng Việt cho cán bộ
Phòng Văn hóa – Xã hội. Kỹ thuật: Django 5.2 LTS, Python 3.13, PostgreSQL 16, Redis 7, Gunicorn, nginx, Docker Compose.


> **Bản xem trước tĩnh (GitHub Pages):** https://buithequan30482-dotcom.github.io/my-website/
> Chỉ để xem giao diện và nội dung. Bộ lọc, tìm kiếm chạy ngay trên trình duyệt; gửi nhận xét, góp ý, gợi ý tìm kiếm
> và khu quản trị chỉ chạy khi triển khai Django lên máy chủ.
> Ảnh di tích là ảnh thật dạng liên kết ngoài (ghi nguồn từng ảnh; ảnh khu vực được ghi rõ "khu vực"). Tạo lại bản xem trước:
> `python manage.py export_static_preview --out preview --prefix /my-website/preview/`

**Tài liệu kèm theo:** hướng dẫn sử dụng khu quản trị [docs/HDSD_Quan_tri_Website_Di_tich_Van_Don.docx](docs/HDSD_Quan_tri_Website_Di_tich_Van_Don.docx)
(bản PDF: `static/docs/HDSD_Quan_tri.pdf`).

Tài liệu này hướng dẫn **triển khai lên một VPS Ubuntu Server 24.04 LTS** và vận hành. Quy trình vận hành định kỳ
(hằng ngày / tuần / tháng): [docs/VAN_HANH.md](docs/VAN_HANH.md).

---

## Mục lục
1. [Kiến trúc](#1-kiến-trúc)
2. [Yêu cầu VPS](#2-yêu-cầu-vps)
3. [Cài đặt trên VPS mới](#3-cài-đặt-trên-vps-mới)
4. [Chạy lần đầu](#4-chạy-lần-đầu)
5. [Lấy chứng chỉ SSL (HTTPS)](#5-lấy-chứng-chỉ-ssl-https)
6. [Cấu hình Google Maps](#6-cấu-hình-google-maps)
7. [Tài khoản và vai trò](#7-tài-khoản-và-vai-trò)
8. [Sao lưu và phục hồi](#8-sao-lưu-và-phục-hồi)
9. [Cập nhật phiên bản](#9-cập-nhật-phiên-bản)
10. [Giám sát](#10-giám-sát)
11. [Xử lý sự cố thường gặp](#11-xử-lý-sự-cố-thường-gặp)
12. [Phát triển local](#12-phát-triển-local)
13. [Danh mục tệp triển khai](#13-danh-mục-tệp-triển-khai)

---

## 1. Kiến trúc

```
                     Internet (người dân, du khách, cán bộ quản trị)
                                     │  80 / 443 (ufw: chỉ mở 80, 443, SSH)
┌────────────────────────────────────┼──────────────────────────────── VPS Ubuntu 24.04 ─┐
│                                    ▼                                                  │
│   ┌──────────────────────────────────────────────┐        ┌──────────────────────┐    │
│   │ nginx 1.28                                   │        │ certbot              │    │
│   │ - HTTP→HTTPS, TLS 1.2/1.3, HSTS              │◄──────►│ Let's Encrypt        │    │
│   │ - /static/ (mã băm, cache 1 năm), /media/    │ certs  │ webroot, gia hạn 12h │    │
│   │ - gzip, limit_req (góp ý, đánh giá, đăng nhập)│        └──────────────────────┘    │
│   └───────────────┬──────────────────────────────┘                                    │
│                   │ proxy :8000          mạng "edge"                                  │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─│─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │
│                   ▼                      mạng "backend" (internal, không ra Internet) │
│   ┌──────────────────────────────┐                                                    │
│   │ web: Django + Gunicorn       │──── SMTP cơ quan (qua mạng edge)                   │
│   │ (user không root, UID 10001) │                                                    │
│   └──────┬─────────────┬─────────┘                                                    │
│          ▼             ▼                                                              │
│   ┌────────────┐ ┌───────────┐     ┌───────────────────────────────────────────┐      │
│   │ db         │ │ redis 7   │     │ backup (cron 02:00)                       │      │
│   │ PostgreSQL │ │ cache,    │     │ pg_dump hằng ngày (giữ 30 bản)            │      │
│   │ 16         │ │ giới hạn  │     │ media: đầy đủ hằng tuần + gia tăng ngày   │──────┼──► Kho ngoài
│   └─────┬──────┘ │ tần suất  │     │ rclone → kho ngoài (S3/Drive/SFTP...)     │      │    (rclone)
│         │        └───────────┘     └───────────────────────────────────────────┘      │
│   Volumes: pgdata · media · static · backups · certs · certbot-www                    │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

| Dịch vụ | Image | Vai trò | Giới hạn tài nguyên |
|---|---|---|---|
| nginx | nginx:1.28-alpine | Reverse proxy, TLS, tệp tĩnh/media, giới hạn tần suất | 0,5 CPU / 256 MB |
| web | build từ `Dockerfile` | Django + Gunicorn (workers = 2×CPU+1, timeout 60s) | 1,5 CPU / 1,5 GB |
| db | postgres:16-alpine | CSDL | 1 CPU / 1 GB |
| redis | redis:7-alpine | Cache, bộ đếm giới hạn tần suất (không lưu đĩa) | 0,25 CPU / 128 MB |
| backup | build từ `deploy/backup/` | cron sao lưu, phục hồi, rclone | 0,5 CPU / 512 MB |
| certbot | certbot/certbot | Cấp và gia hạn chứng chỉ | 0,25 CPU / 128 MB |

Giới hạn tài nguyên là **ước tính ban đầu** cho VPS 2 vCPU / 4 GB, chưa qua kiểm thử tải; điều chỉnh theo số liệu
thực tế (`docker stats`).

## 2. Yêu cầu VPS

Theo TR mục 8.4 (ước tính của đơn vị lập cho MVP):

| Hạng mục | Khuyến nghị |
|---|---|
| CPU / RAM | 2 vCPU / 4 GB (script cài đặt tạo thêm 2 GB swap) |
| Ổ đĩa | 80 GB SSD |
| Hệ điều hành | Ubuntu Server 24.04 LTS (64-bit) |
| Vị trí | Trung tâm dữ liệu tại Việt Nam |
| Mạng | 1 IPv4 công khai; cổng 80, 443 vào được từ Internet |
| Tên miền | Bản ghi DNS A trỏ về IP VPS (Chủ đầu tư cung cấp) |
| Email | Hộp thư SMTP của cơ quan (thông báo kiểm duyệt, đặt lại mật khẩu, cảnh báo lỗi) |
| Kho sao lưu ngoài | Một kho nằm ngoài VPS mà rclone hỗ trợ (S3 tương thích, SFTP, Google Drive...) |

## 3. Cài đặt trên VPS mới

### 3.1. Đăng nhập SSH bằng khóa (khuyến nghị bắt buộc – TR 8.2)

Trên **máy tính của cán bộ kỹ thuật**:

```bash
ssh-keygen -t ed25519 -C "vandon-admin"          # tạo khóa (đặt passphrase)
ssh-copy-id -i ~/.ssh/id_ed25519.pub root@<IP_VPS>
ssh root@<IP_VPS>                                # thử đăng nhập bằng khóa
```

Tạo người dùng quản trị riêng (không làm việc bằng root):

```bash
adduser vandon && usermod -aG sudo vandon
rsync --archive --chown=vandon:vandon ~/.ssh /home/vandon
```

**Chỉ sau khi đã đăng nhập được bằng khóa** với user `vandon`, tắt đăng nhập bằng mật khẩu:

```bash
sudo tee /etc/ssh/sshd_config.d/99-hardening.conf >/dev/null <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
EOF
sudo sshd -t && sudo systemctl reload ssh
```

### 3.2. Cài Docker theo tài liệu chính thức

Theo hướng dẫn chính thức "Install Docker Engine on Ubuntu" (https://docs.docker.com/engine/install/ubuntu/):

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker vandon       # đăng xuất/đăng nhập lại để có hiệu lực
docker run --rm hello-world          # kiểm tra
```

### 3.3. Lấy mã nguồn

```bash
sudo mkdir -p /opt/vandon && sudo chown vandon:vandon /opt/vandon
git clone <địa-chỉ-kho-git> /opt/vandon      # hoặc giải nén gói bàn giao vào /opt/vandon
cd /opt/vandon
```

> Mọi lệnh trong tài liệu này chạy tại thư mục gốc dự án (`/opt/vandon`).

### 3.4. Chuẩn bị hệ thống: tường lửa, swap, bản vá tự động

```bash
sudo deploy/scripts/install.sh           # SSH khác cổng 22: sudo SSH_PORT=2222 deploy/scripts/install.sh
```

Script (chạy lại an toàn) thực hiện: cài Docker nếu chưa có (cùng kho chính thức ở 3.2), bật
`unattended-upgrades`, cấu hình **ufw chỉ mở SSH (giới hạn tần suất), 80, 443**, tạo swap 2 GB, giới hạn
kích thước log Docker.

Tường lửa làm thủ công (tương đương):

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw limit 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

> Lưu ý: Docker tự thêm luật iptables cho cổng đã publish và **bỏ qua ufw**. Vì vậy `docker-compose.yml` chỉ
> publish 80/443 của nginx; db và redis nằm trong mạng nội bộ `backend` (internal), không publish cổng nào.
> Không thêm `ports:` cho db/redis.

## 4. Chạy lần đầu

```bash
DOMAIN=ditich.vandon.gov.vn LETSENCRYPT_EMAIL=it@vandon.gov.vn deploy/scripts/first-run.sh
# hoặc: make first-run   (sẽ hỏi tên miền)
```

`first-run.sh` thực hiện:
1. Tạo `.env` từ `.env.example` (quyền 600) với `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD` và **đường dẫn khu
   quản trị ngẫu nhiên** (`ADMIN_URL=quan-tri-xxxxxxxx/`) – ghi lại đường dẫn này. Tạm đặt `DJANGO_HTTPS=0` vì
   chưa có chứng chỉ.
2. Build image, khởi động 6 dịch vụ (nginx ở chế độ HTTP-only khi chưa có chứng chỉ).
3. `python manage.py migrate` và `python manage.py load_vandon` (44 di tích, nội dung, nhóm quyền).
4. Tạo tài khoản quản trị hệ thống (`createsuperuser`, mật khẩu ≥10 ký tự).

Sau đó mở `.env` để điền các mục còn lại (mỗi biến có chú thích tiếng Việt): SMTP (`EMAIL_*`), `DJANGO_ADMINS`
(nhận email khi lỗi 500), `GOOGLE_MAPS_API_KEY`, `RCLONE_REMOTE`. Áp dụng thay đổi `.env`:

```bash
docker compose up -d          # tạo lại các container có cấu hình thay đổi
```

Kiểm tra: `docker compose ps` (mọi dịch vụ `running`/`healthy`), mở `http://<tên miền>/`.

## 5. Lấy chứng chỉ SSL (HTTPS)

Điều kiện: bản ghi DNS A của `DOMAIN` (và `EXTRA_DOMAINS`, vd `www.`) đã trỏ về IP VPS; cổng 80 mở.

```bash
deploy/scripts/init-letsencrypt.sh --staging   # (tùy chọn) thử với máy chủ staging, không tốn hạn mức
deploy/scripts/init-letsencrypt.sh             # cấp thật   (hoặc: make ssl)
```

Script: kiểm tra DNS → cấp chứng chỉ qua webroot (`/.well-known/acme-challenge/`) → nginx tự chuyển sang cấu hình
HTTPS (`NGINX_SSL=auto` phát hiện chứng chỉ) → đặt `DJANGO_HTTPS=1`, `DJANGO_CSRF_TRUSTED_ORIGINS=https://...`
và khởi động lại web.

Cấu hình HTTPS (`deploy/nginx/`): HTTP→HTTPS 301, TLS 1.2/1.3 (bộ mã "intermediate" của Mozilla), HSTS 1 năm,
`X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`; CSP cho trang HTML do Django đặt
(`core/middleware.py`). **Gia hạn tự động**: container `certbot` chạy `certbot renew` 12 giờ/lần; nginx nạp lại
cấu hình 6 giờ/lần. Kiểm tra: `docker compose run --rm --entrypoint certbot certbot certificates`.

## 6. Cấu hình Google Maps

Không có khóa, website tự dùng bản đồ OpenStreetMap. Để dùng Google Maps:

1. Vào Google Cloud Console bằng tài khoản của cơ quan → tạo project → bật **Maps JavaScript API**,
   **Maps Embed API**, **Places API** (mã nguồn dùng `maps/api/js` với `libraries=places` và `maps/embed/v1/place`).
2. Tạo API key → **Giới hạn ứng dụng: HTTP referrers** = `https://<DOMAIN>/*`; **Giới hạn API**: chỉ 3 API trên.
3. Đặt quota/ngân sách cảnh báo trong Google Cloud (Billing → Budgets & alerts) để tránh phát sinh chi phí ngoài dự kiến.
4. Nhập khóa ở **một trong hai nơi**: khu quản trị → *Cấu hình hệ thống* (ưu tiên, không cần khởi động lại),
   hoặc `GOOGLE_MAPS_API_KEY=` trong `.env` rồi `docker compose up -d web`.

## 7. Tài khoản và vai trò

| Vai trò | Cách tạo | Quyền |
|---|---|---|
| Quản trị hệ thống | `make createsuperuser` | Toàn quyền, **bắt buộc OTP** (`OTP_REQUIRED_FOR_SUPERUSER=1`) |
| Biên tập viên | Khu quản trị → Người dùng → Thêm → nhóm "Biên tập viên", tích *Là nhân viên* | Soạn nội dung, gửi duyệt |
| Duyệt nội dung | nhóm "Duyệt nội dung" | Duyệt/xuất bản di tích (`heritage.publish_ditich`) |
| Kiểm duyệt tương tác | nhóm "Kiểm duyệt tương tác" | Duyệt đánh giá, xử lý góp ý |

Các nhóm được tạo bởi `load_vandon`. Mật khẩu tối thiểu 10 ký tự; tài khoản tạm khóa 15 phút sau 5 lần sai.
Lần đăng nhập đầu, superuser quét mã QR bằng ứng dụng Authenticator (Google/Microsoft Authenticator).

(Tùy chọn TR 8.2) Giới hạn IP khu quản trị: sửa khối `location ^~ ${ADMIN_PATH}` trong
`deploy/nginx/templates/vandon-locations.inc.template` (bỏ chú thích `allow ...; deny all;`) rồi
`docker compose restart nginx`.

## 8. Sao lưu và phục hồi

### 8.1. Sao lưu tự động (TR 8.3)

Container `backup` chạy theo `BACKUP_CRON` (mặc định **02:00** hằng ngày, giờ Việt Nam):

| Đối tượng | Tần suất | Lưu giữ trên VPS | Tệp (volume `backups`) |
|---|---|---|---|
| CSDL (`pg_dump -Fc` + sha256) | Hằng ngày | 30 bản (`BACKUP_KEEP_DAYS`) | `db/vandon-YYYYMMDD-HHMMSS.dump` |
| Media – đầy đủ | Hằng tuần (`MEDIA_FULL_WEEKDAY`, mặc định Chủ nhật) | 5 tuần (`MEDIA_KEEP_WEEKS`) | `media/full-*.tar.gz` |
| Media – gia tăng | Các ngày còn lại (thay đổi so với bản đầy đủ gần nhất) | theo bộ đầy đủ | `media/inc-*-of-<full>.tar.gz` |
| Kho ngoài (rclone copy) | Sau mỗi lần sao lưu | `RCLONE_KEEP_DAYS` (mặc định 90 ngày) | `RCLONE_REMOTE` |

Lệnh thủ công: `make backup` · `make backup-list` · `deploy/scripts/backup.sh db|media|media-full|remote`.
Nhật ký: `docker compose exec backup tail -n 50 /backups/logs/backup.log`; trạng thái lần gần nhất:
`docker compose exec backup cat /backups/logs/last_status.txt`.

### 8.2. Cấu hình kho ngoài (bắt buộc theo TR 8.3)

```bash
docker compose run --rm backup rclone config --config /config/rclone/rclone.conf   # tạo remote, vd "kholuu"
# kiểm tra
docker compose run --rm backup rclone lsd kholuu: --config /config/rclone/rclone.conf
```

Đặt `RCLONE_REMOTE=kholuu:vandon-backup` trong `.env` → `docker compose up -d backup` → `make backup`.
Tệp `deploy/rclone/rclone.conf` chứa thông tin truy cập kho: `chmod 600`, không đưa lên git.
Khuyến nghị dùng tài khoản kho chỉ có quyền ghi/đọc (không quyền xóa) hoặc bật versioning/object-lock nếu kho hỗ trợ.

### 8.3. Phục hồi

```bash
make backup-list                                   # xem ngày có bản sao lưu
make restore DATE=20261015                         # CSDL + media về ngày 15/10/2026 (hỏi xác nhận "yes")
make restore DATE=20261015 ARGS=--db-only
make restore DATE=20261015 ARGS=--from-remote      # VPS mới / mất volume: tải từ kho ngoài trước
```

`restore.sh`: dừng web → tự sao lưu hiện trạng (`pre-restore-*`) → xóa và tạo lại CSDL từ bản dump (kiểm tra
sha256) → giải nén media đầy đủ + gia tăng → khởi động web (tự migrate).

**Phục hồi trên VPS mới** (mất toàn bộ VPS): làm mục 3 → chép `.env` và `deploy/rclone/rclone.conf` đã lưu
riêng (**phải cất giữ 2 tệp này ngoài VPS**, nơi an toàn) → `docker compose up -d --build` →
`make restore DATE=<ngày> ARGS=--from-remote` → `make ssl`.

### 8.4. Diễn tập phục hồi (RPO ≤ 24 giờ, RTO ≤ 4 giờ)

Thực hiện **1 lần trước nghiệm thu** và định kỳ mỗi quý, tốt nhất trên một VPS thử nghiệm (staging):

| Bước | Việc làm | Ghi nhận |
|---|---|---|
| 1 | Ghi thời điểm bắt đầu T0; ghi số di tích, số ảnh, 1 góp ý gần nhất trên hệ thống thật | T0 |
| 2 | Trên VPS thử: cài theo mục 3, chép `.env` + `rclone.conf` | |
| 3 | `make restore DATE=<hôm nay> ARGS=--from-remote --yes` | |
| 4 | `make ssl` (hoặc thử bằng HTTP), đăng nhập quản trị, mở 5 di tích có ảnh/video | |
| 5 | So sánh số liệu bước 1; thời điểm bản sao lưu dùng phải ≤ 24 giờ trước T0 (**RPO**) | thời điểm bản dump |
| 6 | Ghi thời điểm hoàn tất T1; **RTO = T1 − T0** phải ≤ 4 giờ | T1, RTO |
| 7 | Lập biên bản diễn tập (người thực hiện, kết quả, vướng mắc) | |

Ước tính thời gian (chưa đo thực tế): phục hồi CSDL vài phút; media phụ thuộc dung lượng và tốc độ tải từ kho ngoài –
đo trong lần diễn tập đầu tiên để xác nhận RTO.

## 9. Cập nhật phiên bản

```bash
make update                       # = deploy/scripts/update.sh
make update ARGS=--no-pull        # mã nguồn đã chép sẵn (không dùng git)
```

Quy trình: `git pull --ff-only` → build image mới (bản cũ vẫn phục vụ; `collectstatic` + `compilemessages` chạy lúc
build) → sao lưu CSDL → `migrate` bằng container tạm → chạy song song container web mới, chờ *healthy* → dừng
container cũ (graceful 40s) → nginx tự phân giải lại upstream. Nếu bản mới không healthy: tự hủy, giữ bản cũ.

Khuyến nghị (TR 8.5): cập nhật trên **staging** trước; với migration thay đổi cấu trúc lớn, thông báo bảo trì.
Quay lại bản trước: `git checkout <tag/commit cũ>` → `make update ARGS=--no-pull`; nếu migration không đảo ngược
được thì `make restore DATE=<ngày trước cập nhật> ARGS=--db-only` (update.sh đã sao lưu CSDL ngay trước khi migrate).

## 10. Giám sát

| Điểm kiểm tra | Ý nghĩa |
|---|---|
| `https://<DOMAIN>/healthz` | Trả `ok` (200) khi Django chạy **và** kết nối được CSDL; 503 nếu mất CSDL |
| `https://<DOMAIN>/nginx-health` | Chỉ kiểm tra nginx |
| `docker compose ps` | Trạng thái `healthy` của web (healthcheck 30s/lần), db, redis, nginx |

Giám sát uptime + cảnh báo email (TR 8.5): đăng ký một dịch vụ giám sát bên ngoài (vd Uptime Kuma tự cài trên máy
khác, hoặc dịch vụ uptime thương mại) kiểm tra `https://<DOMAIN>/healthz` mỗi 1–5 phút, tìm chuỗi `ok`, gửi email
khi lỗi 2 lần liên tiếp. Thêm kiểm tra hạn chứng chỉ SSL nếu dịch vụ hỗ trợ.

Nhật ký: `make logs` / `make logs-web`; nginx: `docker compose logs nginx`. Lỗi 500 được gửi email tới
`DJANGO_ADMINS` (cần SMTP). Log Docker giới hạn 10 MB × 5 tệp mỗi container.

## 11. Xử lý sự cố thường gặp

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `Bad Request (400)` | Tên miền chưa có trong `DJANGO_ALLOWED_HOSTS` | Sửa `.env` → `docker compose up -d web` |
| `403 CSRF verification failed` khi gửi form | Thiếu `https://<tên miền>` trong `DJANGO_CSRF_TRUSTED_ORIGINS` | Sửa `.env` → `docker compose up -d web` |
| Chuyển hướng vòng lặp | `DJANGO_HTTPS=1` khi nginx chưa có chứng chỉ | Đặt `DJANGO_HTTPS=0` hoặc chạy `make ssl` |
| `502 Bad Gateway` | web đang khởi động/lỗi | `docker compose ps`, `make logs-web` |
| `413 Request Entity Too Large` | Tệp vượt giới hạn (công khai 30 MB, quản trị 210 MB) | Nén/giảm kích thước tệp |
| `429 Too Many Requests` | Vượt giới hạn tần suất (góp ý/đánh giá 6/phút/IP; đăng nhập 10/phút/IP) | Chờ 1 phút; chỉnh `limit_req_zone` nếu cần |
| Ảnh tải lên lỗi quyền | Volume media sai chủ sở hữu | `docker compose run --rm --user root --entrypoint chown web -R 10001:10001 /srv/media` |
| Không cấp được chứng chỉ | DNS chưa trỏ đúng / cổng 80 bị chặn | `dig +short <DOMAIN>`, `sudo ufw status`, thử `--staging` |
| Không nhận email | SMTP sai / bị chặn cổng | `make shell` → `from django.core.mail import send_mail; send_mail("t","t",None,["x@y"])` |
| Ổ đĩa đầy | Bản sao lưu, image cũ, log | `df -h`; `docker system df`; `docker image prune -f`; giảm `BACKUP_KEEP_DAYS` |
| Quên đường dẫn quản trị | — | `grep ADMIN_URL .env` |
| Superuser mất điện thoại OTP | — | `make shell` rồi chạy: `from core.models import AdminProfile; AdminProfile.objects.filter(user__username="TEN").update(otp_enabled=False, otp_secret="")` – lần đăng nhập sau sẽ thiết lập lại OTP |
| Tài khoản bị khóa tạm (5 lần sai) | — | Chờ 15 phút, hoặc `make shell`: `AdminProfile.objects.filter(user__username="TEN").update(failed_logins=0, locked_until=None)` |
| Sao lưu thất bại | Xem nhật ký | `docker compose exec backup cat /backups/logs/last_status.txt` |

## 12. Phát triển local

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
# tạo tệp .env.dev, ví dụ:
#   DATABASE_URL=postgres://vandon:vandon@localhost:5432/vandon   (bỏ trống = SQLite)
#   DJANGO_DEBUG=1
#   DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver
#   OTP_REQUIRED_FOR_SUPERUSER=0
set -a; . ./.env.dev; set +a
python manage.py migrate && python manage.py load_vandon
python manage.py runserver 0.0.0.0:8000
python manage.py test
```

Chạy thử toàn bộ stack Docker trên máy cá nhân: tạo `.env` với `DOMAIN=localhost`, `DJANGO_ALLOWED_HOSTS=localhost`,
`DJANGO_HTTPS=0`, `NGINX_SSL=off`, `HTTP_PORT=8080` → `make up` → mở `http://localhost:8080/`.

Kiểm thử trong container (CSDL test riêng, media vào /tmp): `make test`.

## 13. Danh mục tệp triển khai

```
Dockerfile                      image web đa tầng (python:3.13-slim), user không root, collectstatic, compilemessages
.dockerignore
docker-compose.yml              6 dịch vụ, volume có tên, mạng edge/backend
.env.example                    mẫu cấu hình (chú thích tiếng Việt)
Makefile                        lệnh tắt: make help
requirements.txt                thư viện Python ghim phiên bản
core/health.py                  view /healthz
deploy/docker/                  entrypoint.sh, gunicorn.conf.py, healthcheck.py
deploy/nginx/                   templates (HTTP-only / HTTPS / locations), snippets (ssl, proxy, header bảo mật)
deploy/backup/                  image sao lưu (postgres:16 + rclone + cron)
deploy/scripts/                 install, first-run, init-letsencrypt, backup, restore, update, createadmin
docs/VAN_HANH.md                quy trình vận hành định kỳ
```
