# Smoke test de slice-runner

Harness mínimo y autocontenido para validar el loop de `slice-runner` de punta a punta sin depender de un repo real. Es la forma barata de ganar confianza en el "self-verification loop" antes de subir al Nivel 2 (ver `../docs/maturity-map.md`).

## Qué valida

El **inner loop crítico** (lo que Cherny marca como la palanca 1->2): detectar la spec -> alinear -> implementar con TDD -> **verificador independiente** -> puertas verdes (lint/types/test) -> ledger + stream.

Qué **no** valida (necesita repo con remoto): `gh pr create` y el CI real de GitHub Actions. En local, la puerta de "CI verde" se sustituye por `make linting && make check-types && make test`.

## Estructura

```
fixture/              proyecto uv autocontenido, en estado RESET (fizzbuzz sin implementar)
  pyproject.toml      ruff + mypy strict + pytest via uv
  Makefile            test / check-types / check-style / check-format / linting
  conventions.md      vara de convenciones (para el verificador)
  spec.md             1 slice (formato A) con AC, sin marcar
  fizzbuzz/core.py    vacio: la slice lo implementa
sample-output/        artefactos de un run verde real (evidencia)
  stream.log          el stream en vivo de ese run
  runs.jsonl          la entrada de ledger resultante
  *.example           test y core generados por la slice
```

## Cómo ejecutarlo

Requisitos: `uv`, `git`, `make` (y `gh` solo para la variante con PR/CI real).

```bash
cp -r smoke/fixture /tmp/slice-smoke && cd /tmp/slice-smoke
git init -q && git add -A && git commit -qm baseline
uv run python -V   # calienta el entorno (instala ruff/mypy/pytest)
```

Luego, desde Claude Code en ese directorio:

```
/slice-runner   (o: "corre la siguiente slice de spec.md")
```

Debe: seleccionar slice-01, alinear, escribir el test (rojo), implementar `fizzbuzz`, refactor, verificar con un subagente independiente, dejar las puertas verdes, y escribir `.slice-runner/runs.jsonl` + `.slice-runner/stream.log`.

Sigue el run en vivo desde otra terminal:

```bash
tail -f .slice-runner/stream.log
```

## Criterio de "smoke OK"

- `make linting && make check-types && make test` verdes.
- El verificador devuelve `PASA` (AC cubiertos + convenciones OK).
- `spec.md` queda con `- [x] slice-01`.
- `.slice-runner/runs.jsonl` tiene una entrada `"estado":"hecha"`.

Compara tu salida con `sample-output/` para confirmar que coincide en forma.

## Resultado del último run de referencia

Ver `sample-output/`: pytest 5/5, ruff limpio, mypy strict OK, verificador PASA, slice `hecha`.
