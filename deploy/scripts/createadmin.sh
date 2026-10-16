#!/usr/bin/env bash
# =============================================================================
# TẠO TÀI KHOẢN QUẢN TRỊ HỆ THỐNG (superuser).
#   deploy/scripts/createadmin.sh                 # hỏi tên đăng nhập, email, mật khẩu (≥10 ký tự)
#   deploy/scripts/createadmin.sh admin a@b.vn    # điền sẵn tên + email, vẫn hỏi mật khẩu
# Lần đăng nhập đầu tiên, hệ thống bắt buộc thiết lập xác thực 2 lớp (OTP) cho superuser
# (OTP_REQUIRED_FOR_SUPERUSER=1) – chuẩn bị điện thoại có ứng dụng Google Authenticator/Microsoft Authenticator.
# =============================================================================
set -euo pipefail
# shellcheck source=_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
require_env_file

args=()
[[ -n "${1:-}" ]] && args+=(--username "$1")
[[ -n "${2:-}" ]] && args+=(--email "$2")

dc exec web python manage.py createsuperuser "${args[@]}"
log "Đăng nhập tại: https://$(env_get DOMAIN localhost)/$(env_get ADMIN_URL quan-tri-vd/ | sed 's#^/*##')"
