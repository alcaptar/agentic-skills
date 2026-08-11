# Controles de calidad del repo. Mismos nombres de target que exigimos a la fixture de
# smoke (`smoke/fixture/Makefile`) y que el paso 2 de `slice-runner` autodetecta: la vara
# del harness es la misma que la de lo que valida.
#
# El toolchain lo gestiona uv (`[dependency-groups] dev` en pyproject.toml); `uv run` lo
# instala solo la primera vez.

.PHONY: install install-program install-skills test check-types check-style check-format linting fix-linting check

# El entregable son dos mitades que se instalan distinto: el programa es una rueda de
# Python y las skills son ficheros que Claude Code lee de su directorio de configuracion.
# `install` monta las dos, porque instalar solo una deja un entorno que parece listo y no
# lo esta: sin `slice-spec` no hay issue que conducir, y sin `deploy-watch` la llamada que
# el programa encadena al mergear se gasta sin hacer nada.
#
# El destino sale de `CLAUDE_CONFIG_DIR` si esta puesto, igual que lo resuelve el programa
# (`src/slice_runner/infrastructure/claude_config.py`): si este target asumiera `~/.claude`,
# mentiria en cuanto alguien mueva la configuracion.
CLAUDE_HOME ?= $(if $(CLAUDE_CONFIG_DIR),$(CLAUDE_CONFIG_DIR),$(HOME)/.claude)
SKILLS := slice-spec deploy-watch

# Las dos mitades son targets propios porque solo una se puede medir: `install-skills` corre
# en un `CLAUDE_HOME` de usar y tirar (`make install-skills CLAUDE_HOME=<ruta>`) y lo cubre
# `tests/test_install.py`; `install-program` escribe en el entorno de la maquina y eso no cabe
# en la suite, asi que queda declarado sin test en vez de fingido con uno.
install: install-program install-skills

# `--reinstall` no es redundante con `--force`: `--force` pisa el ejecutable que ya hubiera, pero
# la rueda se reutiliza de cache mientras la version no cambie, y `version` es `0.0.0` fija. Sin el,
# un `git pull` seguido de `make install` deja instalado el codigo viejo sin decirlo.
install-program:
	uv tool install --force --reinstall .

# Un symlink ocupado apuntando a otro sitio **no se pisa**: el caso real es el de
# `slice-runner`, que apunta a `agentic-skills-legacy` a proposito. Se dice y se para.
install-skills:
	@mkdir -p "$(CLAUDE_HOME)/skills"
	@for skill in $(SKILLS); do \
		link="$(CLAUDE_HOME)/skills/$$skill"; \
		target="$(CURDIR)/skills/$$skill"; \
		if [ -L "$$link" ] && [ "$$(readlink "$$link")" = "$$target" ]; then \
			echo "ya estaba: $$skill"; \
		elif [ -e "$$link" ] || [ -L "$$link" ]; then \
			echo "ocupado: $$link"; \
			echo "  apunta a: $$(readlink "$$link" 2>/dev/null || echo 'un directorio real')"; \
			echo "  quitalo tu si quieres que apunte a $$target"; \
			exit 1; \
		else \
			ln -s "$$target" "$$link" && echo "instalada: $$skill"; \
		fi; \
	done

# `PYTEST_ARGS` deja pasar parametros sin tocar el target, que es lo que pide
# `backend-best-practices` para las sesiones con agente:
#   make test PYTEST_ARGS="--nf -x --tb=short --disable-warnings --color=no --no-header"
PYTEST_ARGS ?=

test:
	uv run pytest -q $(PYTEST_ARGS)

check-types:
	uv run mypy skills tests src

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
