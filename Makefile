.PHONY: setup test lint fmt qa clean

setup:
	python -m pip install -e ".[dev,pdf,almacen]"

test:
	python -m pytest

lint:
	ruff check src tests
	mypy src || true

fmt:
	ruff format src tests
	ruff check --fix src tests

qa:
	python -m obsm.cli qa

clean:
	rm -rf data/raw/* data/bronze/* data/silver/* data/gold/* .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
