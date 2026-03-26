.PHONY: install test test-unit test-integration test-e2e test-all coverage lint format clean

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install pytest pytest-asyncio pytest-cov pytest-mock httpx

# Testing
test:
	pytest tests/unit -v

test-unit:
	pytest tests/unit -v -m unit

test-integration:
	pytest tests/integration -v -m integration

test-e2e:
	pytest tests/integration/test_e2e.py -v -m e2e

test-all:
	pytest tests/ -v

# Coverage
coverage:
	pytest tests/ --cov=src --cov-report=html --cov-report=term

coverage-report:
	open htmlcov/index.html

# Linting and formatting
lint:
	ruff check src tests
	mypy src

format:
	black src tests
	ruff check --fix src tests

# Cleanup
clean:
	rm -rf htmlcov
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Run dashboard
dashboard:
	python -m src.api.dashboard

# Development server
dev:
	BRAIN_GUARD_ENABLED=true \
	BRAIN_GUARD_LOG_LEVEL=debug \
	python -c "from src import BrainGuardPlugin; import asyncio; \
	p = BrainGuardPlugin(); \
	p.config.testing.mock_embeddings=True; \
	p.config.dashboard.enabled=True; \
	asyncio.run(p.initialize()); \
	import asyncio; asyncio.Event().wait()"
