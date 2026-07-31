# Controles de calidad del repo. Mismos nombres de target que exigimos a la fixture de
# smoke (`smoke/fixture/Makefile`) y que el paso 2 de `slice-runner` autodetecta: la vara
# del harness es la misma que la de lo que valida.
#
# El toolchain lo gestiona uv (`[dependency-groups] dev` en pyproject.toml); `uv run` lo
# instala solo la primera vez.

.PHONY: test check-types check-style check-format linting fix-linting check

# `PYTEST_ARGS` deja pasar parametros sin tocar el target, que es lo que pide
# `backend-best-practices` para las sesiones con agente:
#   make test PYTEST_ARGS="--nf -x --tb=short --disable-warnings --color=no --no-header"
PYTEST_ARGS ?=

test:
	uv run pytest -q $(PYTEST_ARGS)

check-types:
	uv run mypy skills tests

check-style:
	uv run ruff check .

check-format:
	uv run ruff format --check .

linting: check-style check-format

fix-linting:
	uv run ruff format .
	uv run ruff check --fix .

# Todo lo que debe estar verde antes de dar un cambio por terminado.
check: linting check-types test
