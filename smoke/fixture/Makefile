test:
	uv run pytest -q

check-types:
	uv run mypy fizzbuzz

check-style:
	uv run ruff check .

check-format:
	uv run ruff format --check .

linting: check-style check-format

fix-linting:
	uv run ruff format .
	uv run ruff check --fix .
