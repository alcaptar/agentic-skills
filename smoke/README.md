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

## Antes de smokear el verificador: sesion nueva

Si has tocado `agents/slice-verifier.md`, **abre una sesion nueva de Claude Code antes de probarlo**. El
registro de agentes se cachea al primer load y no relee ediciones (a diferencia de las skills, que si se
releen). Si no, el smoke valida la definicion vieja y no avisa de nada.

Comprobacion rapida de que estas smokeando la version que crees: pon en el prompt de invocacion algo
que solo la version nueva pueda saber, o al reves, mira si el agente cita campos o nombres de regla que
ya borraste. En el smoke del 2026-07-27 se detecto asi: el agente reclamaba un campo `Base ref` que la
version en disco ya no declaraba, y usaba `Bash`, que ya no estaba en su `tools`.

## Criterio de "smoke OK"

- El commit y el titulo de PR son conventional commits con el name como scope:
  `feat(fizzbuzz-core): ...`, y el cuerpo referencia el issue con `Part of #<N>`.
- **El cuerpo del PR cuenta la intencion, no el codigo.** Abre con `## Intencion` (la linea
  `INTENCION:` de la slice, que la fixture declara), sigue con los criterios de aceptacion cumplidos
  y la senal, y **no enumera ficheros ni narra el diff**. Si aparece un parrafo del tipo "se anade
  `fizzbuzz/core.py` con una funcion que...", la regla del paso 8 no esta llegando. Comprueba
  tambien que no dice "inferida": la fixture **si** declara intencion, asi que ese encabezado seria
  falso.
- El PR tiene CI verde (`make linting && make check-types && make test`).
- El verificador devuelve `PASA` (criterios de aceptacion cubiertos + convenciones OK).
- **El agente `slice-verifier` resuelve** (`subagent_type: slice-verifier`, symlink instalado) y su
  mensaje final es el JSON del veredicto **sin prosa alrededor**: la tool `Agent` no valida schemas, asi
  que esto solo se comprueba aqui.
- **El verificador no ejecuta puertas**, y ahora es estructural: no tiene `Bash`. Ojo con "arreglarlo"
  devolviendoselo -el smoke del 2026-07-27 comprobo que un `allowed-tools` restringido **no bloquea** lo
  no listado (ejecuto `ls`, ausente de su lista), asi que `Bash` con allowlist no es una alternativa
  valida a no tener `Bash`-.
- **El verificador recibe el diff en disco** (`gates.py diff-bundle`), no lo calcula. Comprueba que
  `--out` apunta **fuera del repo**: un fichero de trabajo dentro no debe poder acabar en la PR.
- **Sin hallazgos de ruido.** Dos que el smoke ya cazo y no deben reaparecer: un hallazgo sobre "no
  puedo constatar que el test precediera a la implementacion" (inverificable con un solo commit, prohibido
  reportarlo) y el mismo assert debilitado contado dos veces como `alta` (`manipulacion-tests` +
  `test-desiderata`). Si vuelven, la rubrica ha regresado.
- En el issue, la linea de la slice pasa por `[en-curso]` -> `[esperando-merge] PR #<M>` y, tras el
  merge, `[x] ... [mergeada]`.
- El diff staged de la PR contiene **solo** `fizzbuzz/core.py` y `tests/test_core.py`: ni borradores
  ni artefactos (lo garantiza `gates.py pr-hygiene`).
- **La `SENAL` viaja y no genera ruido.** La spec de la fixture declara `SENAL: exenta - <motivo>`
  (libreria pura, sin runtime que observar). El verificador debe **aceptarla** sin hallazgos de
  `observabilidad`: exigir instrumentacion a una libreria sin despliegue seria un falso positivo, y es
  justo el modo de fallo del item 9 recien anadido. Comprueba tambien que el resumen del paso 3 y el
  cuerpo del PR mencionan la senal (o su exencion): si no aparecen, la linea se esta perdiendo entre
  paso 1 y el implementador.

## Pendiente de smokear (I/O aun no validada)

Lo que los unit tests no pueden cubrir y este smoke **todavia no ejecuta**:

- **Slice cross-repo** (`REPO: <org>/<repo>`): rama, puertas, `gh pr create` y CI **en el repo
  destino**, con `Part of <org>/<repo-del-issue>#<N>` como referencia cross-repo, y las fuentes de
  convencion leidas de su subseccion `### <org>/<repo>`. Necesita un segundo repo remoto de pruebas.
  Hasta que se smokee, esa ruta esta validada solo por la logica pura (`fuentes_para`, parseo de
  `REPO:`) y por que `gates.py` ya aceptaba `--repo`.
- **`deploy-watch` con senal declarada**: que una senal `declarada: true` sin muestras devuelva
  `inconclusive` esta cubierto offline (`tests/test_deploy_core.py`, y el CLI), pero la recogida real
  de una serie de negocio recien creada no.

## Evidencia de referencia

`sample-output/` guarda el codigo que la slice deberia producir (`core.py.example`,
`test_core.py.example`). El estado del run ya no deja ficheros locales: la evidencia viva es el issue
en GitHub.
