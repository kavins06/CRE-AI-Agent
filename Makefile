.PHONY: check lint types test

UV ?= uv

check: lint types test

lint:
	$(UV) run --locked ruff check src tests
	$(UV) run --locked ruff format --check src tests

types:
	$(UV) run --locked mypy src

test:
	$(UV) run --locked pytest tests -m "not integration" -q
