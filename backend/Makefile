.PHONY: install dev test lint format docker-up docker-down clean keys

# Development
install:
	pip install -e ".[dev]" || poetry install

dev:
	uvicorn app.main:app --reload --port 8001

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	ruff check app tests

format:
	ruff check --fix app tests
	ruff format app tests

# Docker
docker-up:
	docker-compose up -d
	@echo "Waiting for Cosmos DB emulator to start..."
	@sleep 30
	@echo "Cosmos DB emulator should be ready at https://localhost:8081"

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

# Keys generation (for JWT)
keys:
	mkdir -p keys
	python scripts/generate_keys.py

# Cleanup
clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Help
help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make dev        - Run development server"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Run linter"
	@echo "  make format     - Format code"
	@echo "  make docker-up  - Start Cosmos DB emulator"
	@echo "  make docker-down- Stop Cosmos DB emulator"
	@echo "  make keys       - Generate RSA keys for JWT"
	@echo "  make clean      - Clean cache files"
