# syntax=docker/dockerfile:1
# =============================================================================
# Website di tích Đặc khu Vân Đồn – image ứng dụng Django (Gunicorn)
# Multi-stage: "builder" cài thư viện + biên dịch .mo + collectstatic;
#              "runtime" chỉ chứa venv, mã nguồn, static đã băm – chạy user không phải root.
# Phiên bản Python khớp môi trường đã kiểm thử (3.13); đổi bằng --build-arg PYTHON_VERSION=3.12.
# =============================================================================
ARG PYTHON_VERSION=3.13

# ---------------------------------------------------------------- builder ---
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# gettext: để chạy compilemessages (.po -> .mo). Chỉ cần ở stage build.
RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
 && pip install --only-binary=:all: -r /tmp/requirements.txt

WORKDIR /app
COPY . /app

# Thư viện vendor đôi khi trỏ tới tệp .map không kèm theo (vd leaflet.markercluster.js, chart.umd.min.js) ->
# ManifestStaticFilesStorage báo MissingFileError. Bỏ dòng sourceMappingURL bị "treo" (chỉ trong image, không sửa mã nguồn).
RUN set -eu; \
    grep -rlE 'sourceMappingURL=' /app/static 2>/dev/null | while read -r f; do \
      m="$(grep -oE 'sourceMappingURL=[^ *]+' "$f" | head -n1 | cut -d= -f2)"; \
      if [ -n "$m" ] && [ ! -f "$(dirname "$f")/$m" ]; then \
        echo "Bỏ sourceMappingURL treo: $f -> $m"; sed -i -E '\#^[[:space:]]*(//|/\*)[#@] sourceMappingURL=[^[:space:]]*([[:space:]]*\*/)?[[:space:]]*$#d' "$f"; \
      fi; \
    done

# Biên dịch bản dịch giao diện và gom tệp tĩnh (WhiteNoise Manifest: tên tệp có mã băm).
# SECRET_KEY tạm chỉ dùng lúc build; DB tạm sqlite trong /tmp (không truy cập DB thật).
RUN set -eux; \
    export DJANGO_SECRET_KEY=build-only-not-secret DJANGO_DEBUG=0 \
           DATABASE_URL=sqlite:////tmp/build.sqlite3 MEDIA_ROOT=/tmp/media; \
    if find /app -path /app/staticfiles -prune -o -name '*.po' -print | grep -q .; then \
        python manage.py compilemessages --ignore 'staticfiles/*'; \
    fi; \
    python manage.py collectstatic --noinput; \
    rm -f /tmp/build.sqlite3; \
    find /app -name '__pycache__' -prune -exec rm -rf {} +

# ---------------------------------------------------------------- runtime ---
FROM python:${PYTHON_VERSION}-slim AS runtime

LABEL org.opencontainers.image.title="vandon-web" \
      org.opencontainers.image.description="Website gioi thieu, quang ba di tich Dac khu Van Don"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    MEDIA_ROOT=/srv/media \
    STATIC_SHARED_DIR=/srv/static \
    PORT=8000

# User cố định UID/GID 10001 (khớp quyền thư mục media/static trên volume)
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=root:root /app /app
COPY --chmod=0755 deploy/docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --chmod=0644 deploy/docker/gunicorn.conf.py /etc/gunicorn.conf.py
COPY --chmod=0644 deploy/docker/healthcheck.py /usr/local/bin/healthcheck.py

# Thư mục dữ liệu ghi được (gắn volume khi chạy). Mã nguồn /app chỉ đọc với user app.
RUN mkdir -p /srv/media /srv/static \
 && chown -R app:app /srv/media /srv/static

WORKDIR /app
USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD ["python", "/usr/local/bin/healthcheck.py"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "-c", "/etc/gunicorn.conf.py"]
