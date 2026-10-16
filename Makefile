# =============================================================================
# Lệnh tắt vận hành – Website di tích Đặc khu Vân Đồn. Chạy tại thư mục gốc dự án.
#   make help        liệt kê lệnh
# =============================================================================
SHELL := /bin/bash
DC    := docker compose
SCRIPTS := deploy/scripts

.DEFAULT_GOAL := help
.PHONY: help install first-run up down restart ps logs logs-web migrate shell dbshell backup backup-list \
        restore update createsuperuser test check ssl config health

help: ## Liệt kê các lệnh
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## (root) Chuẩn bị VPS mới: Docker, ufw, swap, cập nhật bảo mật tự động
	sudo $(SCRIPTS)/install.sh

first-run: ## Lần đầu: tạo .env, build, khởi động, migrate, load_vandon, tạo superuser
	$(SCRIPTS)/first-run.sh

up: ## Build (nếu cần) và khởi động toàn bộ dịch vụ
	$(DC) up -d --build

down: ## Dừng toàn bộ dịch vụ (giữ nguyên dữ liệu trong volume)
	$(DC) down

restart: ## Khởi động lại web + nginx
	$(DC) restart web nginx

ps: ## Trạng thái các container
	$(DC) ps

logs: ## Xem nhật ký tất cả dịch vụ (Ctrl+C để thoát)
	$(DC) logs -f --tail=200

logs-web: ## Nhật ký ứng dụng Django/Gunicorn
	$(DC) logs -f --tail=200 web

migrate: ## Chạy migrate CSDL
	$(DC) exec web python manage.py migrate --noinput

shell: ## Django shell
	$(DC) exec web python manage.py shell

dbshell: ## psql vào CSDL
	$(DC) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

createsuperuser: ## Tạo tài khoản quản trị hệ thống
	$(DC) exec web python manage.py createsuperuser

backup: ## Sao lưu ngay (CSDL + media + đẩy kho ngoài nếu cấu hình)
	$(SCRIPTS)/backup.sh all

backup-list: ## Liệt kê bản sao lưu
	$(SCRIPTS)/backup.sh list

restore: ## Phục hồi: make restore DATE=YYYYMMDD [ARGS="--db-only|--media-only|--from-remote"]
	@test -n "$(DATE)" || { echo "Cần DATE=YYYYMMDD (xem: make backup-list)"; exit 1; }
	$(SCRIPTS)/restore.sh --date $(DATE) $(ARGS)

update: ## Cập nhật phiên bản: git pull, build, sao lưu DB, migrate, thay container gần như không gián đoạn
	$(SCRIPTS)/update.sh $(ARGS)

ssl: ## Cấp chứng chỉ Let's Encrypt lần đầu
	$(SCRIPTS)/init-letsencrypt.sh $(ARGS)

test: ## Chạy kiểm thử Django trong container tạm (CSDL test_* riêng, media ghi vào /tmp – không đụng dữ liệu thật)
	$(DC) run --rm -T -e MEDIA_ROOT=/tmp/test-media -e AUTO_SEED=0 web python manage.py test --noinput $(ARGS)

check: ## Kiểm tra cấu hình bảo mật Django cho môi trường production
	$(DC) exec -T web python manage.py check --deploy

config: ## Kiểm tra cú pháp docker-compose.yml + .env
	$(DC) config --quiet && echo "docker-compose.yml hợp lệ"

health: ## Gọi /healthz qua nginx
	@curl -fsS -H "Host: $$(grep -E '^DOMAIN=' .env | cut -d= -f2)" http://127.0.0.1/healthz || echo "KHÔNG khỏe"
