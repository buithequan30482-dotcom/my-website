"""Healthcheck container web.

Gọi GET /healthz (kiểm tra cả kết nối CSDL – core/health.py). Nếu URL /healthz chưa được gắn
(trả 404 hoặc chuyển hướng ngôn ngữ 30x) thì dùng dự phòng GET /robots.txt (không truy vấn DB).
Gửi Host hợp lệ (phần tử đầu của DJANGO_ALLOWED_HOSTS) và X-Forwarded-Proto: https
để không bị chuyển hướng khi DJANGO_HTTPS=1.
"""
import http.client
import os
import sys

host = (os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost").split(",")[0].strip() or "localhost").lstrip(".")
if host == "*":
    host = "localhost"
port = int(os.environ.get("PORT", "8000"))


def get(path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
    conn.request("GET", path, headers={"Host": host, "X-Forwarded-Proto": "https"})
    resp = conn.getresponse()
    resp.read()
    return resp.status


try:
    status = get("/healthz")
    if status == 404 or 300 <= status < 400:
        status = get("/robots.txt")
except Exception as exc:  # noqa: BLE001
    print(f"unhealthy: {exc}")
    sys.exit(1)
print(f"status={status}")
sys.exit(0 if status == 200 else 1)
