PYTEST_FLAGS=-q
PYTHON := $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python)

.PHONY: test test-integration test-all

test:
	$(PYTHON) -m pytest -m "not integration" $(PYTEST_FLAGS)

test-integration:
	# Start services and run integration tests that require external services
	docker compose up -d --build
	# give services a moment to initialize (start.sh includes waits if present)
	if [ -x ./start.sh ]; then ./start.sh || true; fi
	$(PYTHON) -m pytest -m integration $(PYTEST_FLAGS)
	docker compose down

test-all: test test-integration
