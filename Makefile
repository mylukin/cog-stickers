# 项目配置
IMAGE_NAME := lukin/sticker
IMAGE_TAG := $(shell date +%Y%m%d)
SERVE_PORT := 5001

# 检查 cog 是否已安装（只有 build 需要）
COG_INSTALLED := $(shell command -v cog 2> /dev/null)

# 声明所有命令为 PHONY
.PHONY: help install-cog check-cog serve predict shell logs stop restart status build push release

# 默认目标
help:
	@echo "Available commands:"
	@echo "  help         - Show this help message"
	@echo "  install-cog  - Install cog binary (required for build)"
	@echo "  serve        - Start prediction server on port $(SERVE_PORT)"
	@echo "  shell        - Open bash shell in container"
	@echo "  logs         - Show container logs"
	@echo "  stop         - Stop all containers"
	@echo "  restart      - Restart the service"
	@echo "  status       - Show container status"
	@echo "  build        - Build model image (uses cog)"
	@echo "  push         - Push model to registry"
	@echo "  release      - Build and push model"

# Cog 安装和检查（只用于 build）
install-cog:
ifndef COG_INSTALLED
	@echo "Installing cog..."
	sudo curl -o /usr/local/bin/cog -L https://github.com/replicate/cog/releases/latest/download/cog_`uname -s`_`uname -m`
	sudo chmod +x /usr/local/bin/cog
	@echo "Cog installed successfully!"
else
	@echo "Cog is already installed"
endif

check-cog:
ifndef COG_INSTALLED
	@echo "Cog is not installed. Run 'make install-cog' first."
	@exit 1
endif

# 主要服务命令（使用 docker）
serve:
	docker stop sticker 2>/dev/null || true
	docker rm sticker 2>/dev/null || true
	docker run -d --restart always -v /home/lukin/code/sticker/ComfyUI:/src/ComfyUI --name sticker --gpus all -p $(SERVE_PORT):5000 $(IMAGE_NAME):latest

shell:
	docker exec -it sticker bash

# 容器管理
logs:
	@echo "Showing logs for containers..."
	docker logs -f $$(docker ps -q --filter ancestor=$(IMAGE_NAME) | head -1)

stop:
	@echo "Stopping containers..."
	docker stop $$(docker ps -q --filter ancestor=$(IMAGE_NAME)) 2>/dev/null || echo "No containers to stop"
	docker rm $$(docker ps -aq --filter ancestor=$(IMAGE_NAME)) 2>/dev/null || echo "No containers to remove"

restart: stop serve

status:
	@echo "Containers status:"
	docker ps --filter ancestor=$(IMAGE_NAME) --format "table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"

# 构建和发布（build 使用 cog，push 使用 docker）
build: check-cog
	cog build -t $(IMAGE_NAME):$(IMAGE_TAG)
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(IMAGE_NAME):latest

push:
	docker push $(IMAGE_NAME):$(IMAGE_TAG)
	docker push $(IMAGE_NAME):latest

release: build push