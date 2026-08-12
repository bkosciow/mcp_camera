.PHONY: dev dev-build test test-unit test-integration test-coverage lint lint-fix format typecheck clean help build-prod prod-up prod-down prod-logs help

# ===========================================
# Development
# ===========================================

dev: ## Start development environment
	docker compose up

dev-build: ## Rebuild and start development
	docker compose up --build

# ===========================================
# Testing
# ===========================================

test: ## Run all tests
	uv run pytest tests/ -v

test-unit: ## Run unit tests
	uv run pytest tests/unit/ -v

test-integration: ## Run integration tests
	uv run pytest tests/integration/ -v

test-coverage: ## Run tests with coverage
	uv run pytest tests/ -v --cov=src --cov-report=term-missing

# ===========================================
# Code Quality
# ===========================================

lint: ## Run linter
	uv run ruff check .

lint-fix: ## Fix linting issues
	uv run ruff check . --fix

format: ## Format code
	uv run ruff format .

typecheck: ## Run type check
	uv run mypy src/

# ===========================================
# Production
# ===========================================

build-prod: ## Build production Docker image
	docker compose -f docker-compose.prod.yml build

prod-up: ## Start production environment
	docker compose -f docker-compose.prod.yml up -d

prod-down: ## Stop production environment
	docker compose -f docker-compose.prod.yml down

prod-logs: ## View production logs
	docker compose -f docker-compose.prod.yml logs -f

prod-restart: ## Restart production services
	docker compose -f docker-compose.prod.yml restart

# ===========================================
# Cleanup
# ===========================================

clean: ## Clean build artifacts and containers
	docker compose down -v
	docker compose -f docker-compose.prod.yml down -v 2>/dev/null || true
	rm -rf __pycache__ .ruff_cache .mypy_cache .pytest_cache coverage .htmlcov

# ===========================================
# Help
# ===========================================

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
