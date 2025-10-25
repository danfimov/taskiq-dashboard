args := $(wordlist 2, 100, $(MAKECMDGOALS))

.DEFAULT:
	@echo "No such command (or you pass two or many targets to ). List of possible commands: make help"

.DEFAULT_GOAL := help

##@ Local development

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target> <arg=value>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m  %s\033[0m\n\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY: init
init:  ## Initialize development environment
	@uv venv
	@source .venv/bin/activate
	@uv sync --all-extras
	@prek install

.PHONY: run
run:  ## Run API part with hot reload
	@uv run python -m taskiq_dashboard.api

.PHONY: run_docs
run_docs: ## Run documentation server
	@uv run mkdocs serve --livereload

.PHONY: run_infra
run_infra: ## Run rabbitmq in docker for integration tests
	@docker compose -f docker-compose.yml up -d postgres

.PHONY: build
build:  ## Build docker image with tag "local"
	@docker build --progress=plain -t taskiq_dashboard:local .

##@ Testing and formatting

.PHONY: lint
lint:  ## Run linting
	@uv run ruff check .
	@uv run mypy taskiq_dashboard

.PHONY: format
format:  ## Run formatting
	@uv run ruff check . --fix --unsafe-fixes
	@uv run ruff format .

.PHONY: test
test:  ## Run all tests
	@uv run pytest

.PHONY: test_cov
test_cov:  ## Generate test coverage report
	@uv run pytest -m 'not linting' --cov='taskiq_dashboard' --cov-report=html
