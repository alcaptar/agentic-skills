# Smoke test de slice-runner (real, contra GitHub)

Harness para validar el loop de `slice-runner` de punta a punta **contra GitHub de verdad**: el
estado del run vive en un issue, asi que el smoke ya no es offline. Es la forma de ganar confianza en
el "self-verification loop" antes de subir al Nivel 2 (ver `../docs/maturity-map.md`).

La logica pura (parseo y reescritura del cuerpo del issue) se testea offline en `../tests/`
(`python3 -m pytest`). Este smoke cubre lo que esos unit tests no pueden: la **I/O real** contra
`gh` (issue create/view/edit/comment, pr) y el CI de GitHub Actions.

## Qué valida

El **inner loop critico** de extremo a extremo: `slice-spec` crea el issue -> `slice-runner` lee el
issue, alinea, implementa con TDD, verifica con un subagente independiente, abre PR (`Part of #N`),
espera CI verde y **refleja el estado de la slice en el issue** en cada transicion.

## Requisitos

- `gh` autenticado (`gh auth status`) con permiso para crear issues y PRs.
- Un **repo remoto propio** (p. ej. un fork/clon de la fixture) con GitHub Actions que corra las
  puertas (`make linting && make check-types && make test`) en `pull_request`.
- `uv`, `git`, `make` para el proyecto objetivo.

## Estructura

```
fixture/              proyecto uv autocontenido, en estado RESET (fizzbuzz sin implementar)
  pyproject.toml      ruff + mypy strict + pytest via uv
  Makefile            test / check-types / check-style / check-format / linting
  conventions.md      vara de convenciones (para el verificador)
  spec.md             borrador de la spec (1 slice) que se sube al issue
  fizzbuzz/core.py    vacio: la slice lo implementa
sample-output/        evidencia del codigo que produce la slice
  core.py.example     implementacion esperada de fizzbuzz
  test_core.py.example  test esperado
```

## Cómo ejecutarlo

1. **Sube la fixture a un repo remoto** con CI en `pull_request` (o usa uno ya montado):

   ```bash
   cp -r smoke/fixture /tmp/slice-smoke && cd /tmp/slice-smoke
   git init -q && git add -A && git commit -qm baseline
   gh repo create <tu-usuario>/slice-smoke --private --source=. --push
   uv run python -V   # calienta el entorno (instala ruff/mypy/pytest)
   ```

2. **Crea el issue con la spec** (via la skill o a mano):

   ```
   /slice-spec        (usa fixture/spec.md como borrador)
   ```
   o directamente `gh issue create --title "fizzbuzz" --body-file spec.md`.

3. **Corre el loop** apuntando al issue:

   ```
   /slice-runner #<N>   (o: "corre la siguiente slice del issue #<N>")
   ```

Debe: leer el issue, seleccionar `slice-01` (name `fizzbuzz-core`), marcarla `en-curso` en el issue,
alinear, escribir el test (rojo), implementar `fizzbuzz`, refactor, **dejar las puertas verdes**
(`gates.py checks`), verificar con el agente `slice-verifier`, abrir PR (`Part of #<N>`), y al llegar a
CI verde marcar la slice `esperando-merge` en el issue.

Sigue el estado en vivo **desde el propio issue en GitHub** (se actualiza en cada transicion).

## Criterio de "smoke OK"

- El commit y el titulo de PR son conventional commits con el name como scope:
  `feat(fizzbuzz-core): ...`, y el cuerpo referencia el issue con `Part of #<N>`.
- El PR tiene CI verde (`make linting && make check-types && make test`).
- El verificador devuelve `PASA` (AC cubiertos + convenciones OK).
- **El agente `slice-verifier` resuelve** (`subagent_type: slice-verifier`, symlink instalado) y su
  mensaje final es el JSON del veredicto **sin prosa alrededor**: la tool `Agent` no valida schemas, asi
  que esto solo se comprueba aqui.
- **El verificador no ejecuta puertas.** Su `allowed-tools` deja fuera `pytest`/`ruff`/`make`; si
  aparece un intento en su transcript, la restriccion no esta aplicando.
- En el issue, la linea de la slice pasa por `[en-curso]` -> `[esperando-merge] PR #<M>` y, tras el
  merge, `[x] ... [mergeada]`.
- El diff staged de la PR contiene **solo** `fizzbuzz/core.py` y `tests/test_core.py`: ni borradores
  ni artefactos (lo garantiza `gates.py pr-hygiene`).

## Evidencia de referencia

`sample-output/` guarda el codigo que la slice deberia producir (`core.py.example`,
`test_core.py.example`). El estado del run ya no deja ficheros locales: la evidencia viva es el issue
en GitHub.
