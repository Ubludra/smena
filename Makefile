COMPOSE      ?= docker compose
CURDIR_ABS   := $(CURDIR)
API_DIR      := $(CURDIR_ABS)/apps/api
WEB_DIR      := $(CURDIR_ABS)/apps/web
NODE_IMAGE   ?= docker.io/library/node:20-bookworm-slim
PLAYWRIGHT_IMAGE ?= mcr.microsoft.com/playwright:v1.48.2-jammy

.DEFAULT_GOAL := help
.PHONY: help env up down build restart logs ps migrate makemigration \
        test lint format mypy check shell-api psql health web-build \
        web-lint web-typecheck web-test web-e2e clean

help: ## Show available targets
	@grep -E '^[[:alnum:]_-]+:.*## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

env: ## Create .env from example with a random SECRET_KEY (once)
	@if [ -f .env ]; then \
		echo ".env already exists — leaving it untouched."; \
	else \
		cp .env.example .env; \
		python3 -c "import secrets,pathlib; p=pathlib.Path('.env'); p.write_text(p.read_text().replace('SECRET_KEY=dev-insecure-secret-key-change-me','SECRET_KEY='+secrets.token_urlsafe(48)))"; \
		echo "Created .env with a random SECRET_KEY."; \
	fi

up: ## Build and start the stack (detached)
	$(COMPOSE) up -d --build

down: 
	$(COMPOSE) down

build: 
	$(COMPOSE) build

restart: 
	$(COMPOSE) restart

logs: 
	$(COMPOSE) logs -f --tail=100

ps: ## Show container status
	$(COMPOSE) ps

migrate: 
	$(COMPOSE) exec api alembic upgrade head

makemigration: 
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(m)"


test: ## Run backend tests (starts postgres, live source mount)
	$(COMPOSE) run --rm --user root -e MAX_BOT_TOKEN= -v $(API_DIR):/app api pytest -v

lint: 
	$(COMPOSE) run --rm --no-deps --user root -v $(API_DIR):/app api ruff check .

format: 
	$(COMPOSE) run --rm --no-deps --user root -v $(API_DIR):/app api sh -c "ruff format . && ruff check --fix ."

mypy: 
	$(COMPOSE) run --rm --no-deps --user root -v $(API_DIR):/app api mypy src

check: lint mypy test ## Run lint + mypy + tests

shell-api: ## Interactive shell in the API container
	$(COMPOSE) exec api bash

psql: ## psql into the PostgreSQL container
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-smena} -d $${POSTGRES_DB:-smena}

health: ## Probe API live/ready from the host
	@curl -fsS http://localhost:8000/health/live && echo && curl -fsS http://localhost:8000/health/ready && echo

web-build: 
	$(COMPOSE) build web

web-lint: ## ESLint
	docker run --rm -v $(WEB_DIR):/app -w /app $(NODE_IMAGE) sh -c "npm install --no-audit --no-fund && npm run lint"

web-typecheck: ## TypeScript
	docker run --rm -v $(WEB_DIR):/app -w /app $(NODE_IMAGE) sh -c "npm install --no-audit --no-fund && npm run typecheck"

web-test: ## Frontend tests
	docker run --rm -v $(WEB_DIR):/app -w /app $(NODE_IMAGE) sh -c "npm ci --no-audit --no-fund && npm run test"

web-e2e: ## Playwright end-to-end tests
	docker run --rm --network host -v $(WEB_DIR):/app -w /app $(PLAYWRIGHT_IMAGE) sh -c "npm ci --no-audit --no-fund && npm run e2e"

clean: 
	$(COMPOSE) down -v --remove-orphans
