PYTEST_FLAGS=-q
PYTHON := $(shell command -v python 2>/dev/null || command -v python3 2>/dev/null || echo python)

.PHONY: test test-integration test-e2e test-all

test:
	$(PYTHON) -m pytest -m "not integration and not e2e" $(PYTEST_FLAGS)

test-integration:
	# Start services and run integration tests that require external services
	docker compose up -d --build
	# give services a moment to initialize (start.sh includes waits if present)
	if [ -x ./start.sh ]; then ./start.sh || true; fi
	$(PYTHON) -m pytest -m integration $(PYTEST_FLAGS)
	docker compose down

test-e2e:
	# Run E2E tests (requires docker-compose and working services)
	bash scripts/e2e_setup.sh
	$(PYTHON) -m pytest tests/e2e -m e2e $(PYTEST_FLAGS) || true
	bash scripts/e2e_teardown.sh

test-all: test test-integration
