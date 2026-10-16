"""Cấu hình Gunicorn – mọi tham số chỉnh qua biến môi trường.

GUNICORN_WORKERS   số tiến trình (mặc định 2*CPU+1; VPS 2 vCPU -> 5)
GUNICORN_THREADS   số luồng mỗi tiến trình (mặc định 1 = worker sync)
GUNICORN_TIMEOUT   giây (mặc định 60)
"""
import multiprocessing
import os


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = _int("GUNICORN_WORKERS", 0) or (multiprocessing.cpu_count() * 2 + 1)
threads = _int("GUNICORN_THREADS", 1)
worker_class = "gthread" if threads > 1 else "sync"
timeout = _int("GUNICORN_TIMEOUT", 60)
graceful_timeout = _int("GUNICORN_GRACEFUL_TIMEOUT", 30)
keepalive = 5
# Tái khởi động tiến trình định kỳ để tránh rò rỉ bộ nhớ (xử lý ảnh Pillow)
max_requests = _int("GUNICORN_MAX_REQUESTS", 1000)
max_requests_jitter = _int("GUNICORN_MAX_REQUESTS_JITTER", 100)
# Thư mục tạm trong RAM cho heartbeat worker (tránh treo khi đĩa chậm)
worker_tmp_dir = "/dev/shm"
# Tin header X-Forwarded-* từ nginx trong mạng Docker
forwarded_allow_ips = os.environ.get("GUNICORN_FORWARDED_ALLOW_IPS", "*")
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOGLEVEL", "info")
access_log_format = '%({x-forwarded-for}i)s "%(r)s" %(s)s %(b)s %(M)sms "%(a)s"'
# Gunicorn ≥ 25 mở control socket tại ~/.gunicorn/ – user "app" không có HOME ghi được, và không cần dùng.
control_socket_disable = True
