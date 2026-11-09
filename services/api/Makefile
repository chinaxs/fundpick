.PHONY: help install dev lint format typecheck test migrate revision seed clean

help:           ## 显示可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:        ## 安装依赖（含 dev）
	uv sync

dev:            ## 启动开发服务器（热重载）
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 3

lint:           ## 代码检查
	uv run ruff check .

format:         ## 代码格式化
	uv run ruff format .
	uv run ruff check --fix .

typecheck:      ## 类型检查
	uv run mypy app

test:           ## 运行测试
	uv run pytest

migrate:        ## 应用全部迁移
	uv run alembic upgrade head

revision:       ## 生成迁移，用法：make revision m="add xxx"
	uv run alembic revision --autogenerate -m "$(m)"

seed:           ## 写入初始数据
	uv run python -m scripts.seed

clean:          ## 清理缓存
	rm -rf .pytest_cache .mypy_cache .ruff_cache logs/*.log
