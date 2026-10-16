#!/usr/bin/env bash
# =============================================================================
# CÀI ĐẶT MÁY CHỦ MỚI (Ubuntu Server 24.04 LTS) – chạy bằng root hoặc sudo:
#
#   sudo deploy/scripts/install.sh            (SSH khác cổng 22: sudo SSH_PORT=2222 deploy/scripts/install.sh)
#
# Thực hiện:
#   1. Cập nhật hệ điều hành, cài Docker Engine + Compose plugin (kho chính thức của Docker)
#   2. Bật tự cập nhật bản vá bảo mật (unattended-upgrades)
#   3. Tường lửa ufw: chỉ mở 22 (SSH), 80, 443
#   4. Tạo swap 2 GB nếu chưa có (giảm rủi ro hết RAM khi xử lý ảnh lớn)
#   5. Bảo đảm quyền thực thi cho các script
# Chạy lại an toàn. Bước tiếp theo: deploy/scripts/first-run.sh (tạo .env, khởi động, nạp dữ liệu).
# =============================================================================
set -euo pipefail
# shellcheck source=_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

[[ "$(id -u)" == "0" ]] || die "Cần chạy bằng root: sudo $0"
if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  [[ "${ID:-}" == "ubuntu" ]] || warn "Script viết cho Ubuntu 24.04; hệ điều hành hiện tại: ${PRETTY_NAME:-?}"
fi
export DEBIAN_FRONTEND=noninteractive

# ---- 1. Docker ----
if ! command -v docker >/dev/null 2>&1; then
  log "Cài Docker Engine..."
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg git ufw openssl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME:-noble} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
else
  log "Docker đã có: $(docker --version)"
  apt-get install -y git ufw openssl curl >/dev/null
fi
docker compose version >/dev/null || die "Thiếu docker compose plugin"

# Giới hạn log mặc định của Docker (phòng khi container ngoài compose)
if [[ ! -f /etc/docker/daemon.json ]]; then
  cat > /etc/docker/daemon.json <<'EOF'
{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "5" } }
EOF
  systemctl restart docker
fi

# ---- 2. Bản vá bảo mật tự động ----
apt-get install -y unattended-upgrades >/dev/null
dpkg-reconfigure -f noninteractive unattended-upgrades || true

# ---- 3. Tường lửa ----
# Cổng SSH: đặt SSH_PORT nếu máy chủ không dùng 22 (sai cổng = mất kết nối SSH sau khi bật ufw!)
SSH_PORT="${SSH_PORT:-22}"
log "Cấu hình ufw: mở ${SSH_PORT}/tcp (SSH, giới hạn tần suất), 80/tcp, 443/tcp..."
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw limit "${SSH_PORT}/tcp" >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
ufw status verbose | head -n 12
warn "Docker tự mở cổng đã publish (80/443) qua iptables, không phụ thuộc ufw. Không publish thêm cổng db/redis."

# ---- 4. Swap ----
if [[ "$(swapon --show | wc -l)" == "0" ]]; then
  log "Tạo swap 2 GB..."
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -w vm.swappiness=10 >/dev/null; echo 'vm.swappiness=10' > /etc/sysctl.d/99-vandon.conf
fi

# ---- 5. Quyền thực thi script (khi mã nguồn được chép qua zip/scp) ----
chmod +x "${DEPLOY_DIR}"/scripts/*.sh "${DEPLOY_DIR}"/nginx/*.envsh "${DEPLOY_DIR}"/backup/*.sh 2>/dev/null || true
mkdir -p "${DEPLOY_DIR}/rclone"

# ---- Khuyến nghị SSH (không tự động để tránh khóa ngoài) ----
if grep -qiE '^\s*PasswordAuthentication\s+yes' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null; then
  warn "SSH đang cho đăng nhập bằng mật khẩu. Sau khi đã đăng nhập được bằng SSH key, đặt"
  warn "  PasswordAuthentication no  và  PermitRootLogin prohibit-password  rồi: systemctl reload ssh"
fi

cat <<EOF

=====================================================================
 Chuẩn bị máy chủ xong. Bước tiếp theo (trong thư mục ${APP_DIR}):
  1. DOMAIN=ten-mien.gov.vn LETSENCRYPT_EMAIL=it@co-quan.gov.vn deploy/scripts/first-run.sh
  2. deploy/scripts/init-letsencrypt.sh        (sau khi DNS đã trỏ về VPS)
=====================================================================
EOF
