.PHONY: help test coverage lint format check-format isort check-isort quality pre-commit install-dev clean

help:
	@echo "Available commands:"
	@echo "  make test           - Run tests with pytest"
	@echo "  make coverage       - Run tests with coverage report"
	@echo "  make lint           - Run flake8 linter"
	@echo "  make format         - Format code with black"
	@echo "  make check-format   - Check code formatting without changes"
	@echo "  make isort          - Sort imports with isort"
	@echo "  make check-isort    - Check import sorting without changes"
	@echo "  make quality        - Run all quality checks (lint + format check + isort check)"
	@echo "  make pre-commit     - Run all pre-commit hooks"
	@echo "  make install-dev    - Install development dependencies"
	@echo "  make clean          - Remove generated files"

test:
	pytest

coverage:
	pytest --cov=library --cov=library_system --cov-report=html --cov-report=term-missing

lint:
	flake8 library library_system

format:
	black library library_system

check-format:
	black --check library library_system

isort:
	isort library library_system

check-isort:
	isort --check-only library library_system

quality: lint check-format check-isort
	@echo "All quality checks passed!"

pre-commit:
	pre-commit run --all-files

install-dev:
	pip install -r requirements.txt
	pre-commit install

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage
	@echo "Cleaned up generated files"
