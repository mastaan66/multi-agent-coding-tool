.PHONY: install install-dev test lint typecheck quality demo build media

install:
	python -m pip install -e .

install-dev:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .

typecheck:
	mypy

quality: lint typecheck test

demo:
	./ai-factory.sh --demo "Build a todo API"

build:
	./scripts/build_binary.sh

media:
	./scripts/render_demo.sh
