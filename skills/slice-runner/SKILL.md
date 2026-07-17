---
name: slice-runner
description: Ejecuta una slice de una spec markdown de principio a fin. Usar cuando el usuario tenga una spec en .md (checklist de slices, o un plan de una sola slice estilo superpowers) y quiera implementar la siguiente (o una concreta) de forma autonoma - implementar con TDD consciente de capa, verificar con un agente independiente que carga las convenciones del repo, abrir PR y esperar a que la CI este verde, y parar. Aplica si dice "corre la siguiente slice", "implementa la slice X de la spec", "slice-runner", o describe el flujo spec -> slice -> PR -> CI.
---

# Slice Runner

STARTER_CHARACTER = [slice-runner]

Emite `[slice-runner]` al inicio de cada respuesta mientras ejecutas este proceso, como testigo de que el contexto esta intacto y sigues estas reglas. (Marcador de texto en lugar de emoji por preferencia del usuario.)

## Description

Dada una spec en markdown con un checklist de slices, ejecuta **una** slice pendiente de principio a fin: implementa con TDD estricto, la verifica con un agente independiente, abre un PR y espera a que la CI este verde. Luego **para**. No hace merge: el merge lo aprueba el humano.

Nivel de autonomia 1: un ciclo por invocacion. Para encadenar slices, envolver esta skill en `/loop`.

## Principios no negociables

- **El que implementa no verifica.** La implementacion y la verificacion las hacen subagentes distintos (Agent tool), con instrucciones distintas. El verificador es adversarial.
- **Las convenciones del repo mandan.** Implementador y verificador cargan `docs/conventions/` + `CLAUDE.md` (si existen) como vara de medir, por encima de cualquier default generico de hexagonal/DDD. En conflicto, ganan las convenciones del repo. Sin esto, el verificador no puede cazar violaciones reales (p. ej. una migracion que siembra datos donde la convencion lo prohibe).
- **Puertas de parada objetivas.** No hay PR mergeable sin lint limpio, tipos limpios, tests verdes y **CI verde**, ejecutados con los comandos reales del repo (paso 2), no con binarios asumidos.
- **TDD consciente de capa.** Por defecto TDD estricto: test rojo por cada AC antes del codigo, y el verificador comprueba que el test precede a la implementacion. Pero si las convenciones del repo eximen una capa (p. ej. modelos ORM y migraciones que no se testean por separado), la puerta para esa slice es "suite intacta + verificacion de datos/efecto", no test-first por AC. La convencion del repo decide, no este documento.
- **Alinear antes de implementar.** Antes de escribir codigo, mostrar el entendimiento de la slice (alcance, AC, capa afectada, comando de validacion) y esperar go/no-go. Nunca transcribir a ciegas el codigo pre-horneado de una spec: validalo contra las convenciones primero.
- **Seguir `backend-best-practices`.** El implementador carga esa skill y respeta hexagonal/DDD, DI, Pydantic en boundaries, subordinada siempre a las convenciones del repo.
- **El estado vive en el repo.** El checklist de la spec y el ledger (`.slice-runner/runs.jsonl`) SON el estado. El agente olvida; el repo no.
- **Contexto fresco por slice.** Cada slice arranca sin arrastrar la conversacion de la anterior; lo que persiste entre slices es la spec + el ledger, que se re-leen al empezar. Evita la degradacion de contexto (patron Ralph) y hace seguro el Nivel 2 (`/loop`).
- **Circuit breaker.** Maximo 2 reintentos por fase. Ademas, **presupuesto de coste**: si la slice supera el limite de tokens/$ configurado, para con estado `abortada-presupuesto`. Si la CI sigue roja tras el reintento, para, deja el PR abierto y reporta con logs.

## Formatos de spec soportados

La skill autodetecta cual de estos dos formatos usa la spec. Si no encaja en ninguno, para y pregunta.

### Formato A — checklist de slices

Un fichero con varias slices; cada item del checklist es una slice, con AC embebidos.

```markdown
## Slices
- [ ] slice-01: Crear value object `Cantidad` con validacion de rango
      AC: rechaza negativos; tests en test/domain/test_cantidad.py
- [x] slice-02: Caso de uso `AjustarStock` (puerto + adaptador)
      AC: emite evento StockAjustado; no toca infra directamente
```

Unidad de trabajo = cada item `- [ ]`. `[ ]` pendiente, `[x]` hecha, `[!]` bloqueada.

### Formato B — plan de una slice (estilo superpowers)

Un fichero **es una sola slice** (titulo tipo `Slice N — ...`), con `Goal`, `Architecture`, `Global Constraints` y `### Task N` que contienen `- [ ] Step N`.

- **La unidad de trabajo es el fichero entero**, no cada Step. No trates un Step como una slice.
- Los AC se derivan de: el `Goal`, los `Interfaces`/`Expected`/verificaciones de cada Task, y las `Global Constraints`.
- Los `- [ ] Step N` son el plan de ejecucion interno; el estado de la slice se lleva a nivel de fichero (ver abajo).
- Los `Global Constraints` son restricciones duras que el verificador debe comprobar.

### Estado

- Formato A: marca el item de la slice `[ ]`/`[x]`/`[!]`.
- Formato B: como el fichero es una slice, registra el estado en su cabecera (una linea `> Estado: hecha | bloqueada (motivo)`), o marca el checklist de un indice externo si la spec vive dentro de uno.
- `[!]` / bloqueada = CI roja no resuelta; deja el PR abierto.

## Ledger y stream en vivo

Estado y observabilidad del pipeline, en `.slice-runner/` del repo objetivo.

### `.slice-runner/runs.jsonl` (versionado)

Ledger append-only: una linea JSON por slice al cerrarla. Sirve de memoria para el contexto fresco, fuente del coste y registro historico. Esquema minimo:

    {"slice_id":"slice-01","estado":"hecha","intentos":1,"tokens_in":0,"tokens_out":0,"coste_usd":0.0,"pr_url":"...","ci_result":"green","duracion_s":0,"ts":"2026-07-17T12:00:00Z"}

- Estados: `hecha` | `bloqueada` | `abortada-presupuesto`.
- **Coste por slice mergeada** = suma de `coste_usd` de las entradas `hecha` / numero de `hecha`. Es la metrica clave (no el coste por intento).
- Al arrancar una slice (paso 1), leer el ledger para no repetir lo ya `hecha`/`bloqueada`.

### `.slice-runner/stream.log` (efimero, no versionado)

Stream en vivo legible para seguir el run en directo desde otra terminal:

    tail -f .slice-runner/stream.log

La skill anexa una linea por transicion de fase, formato `HH:MM:SS  slice-NN  <fase>  <detalle>`. Transiciones a emitir: `select`, `align`, `implement start`, `implement done`, `verify PASA|FALLA`, `pr <url>`, `ci green|red`, `done`, `blocked: <motivo>`, `abort: presupuesto`. Es un stream compartido: varias terminales pueden tail-earlo a la vez (patron de deploy-monitor).

### Setup

La primera vez, crear `.slice-runner/.gitignore` con `stream.log` (versiona el ledger, no el stream efimero). `deploy-watch` anexa a estos mismos ficheros su veredicto + señales del deploy.

## Steps

### 1. Localizar spec, detectar formato y seleccionar slice

- Pide la ruta de la spec `.md` si no se ha dado.
- **Detecta el formato** (A checklist / B plan de una slice; ver "Formatos de spec soportados"). Si no encaja, para y pregunta.
- Selecciona la slice:
  - Formato A: la indicada por el usuario, o la primera `[ ]`.
  - Formato B: el fichero completo es la slice.
- Extrae titulo, alcance y AC. En Formato B derivalos del `Goal` + `Interfaces`/verificaciones de los Tasks + `Global Constraints`. Si no hay AC ni forma de derivarlos, para y pidelos: sin AC no hay puerta de verificacion.
- **Lee `.slice-runner/runs.jsonl`** (si existe) para no repetir slices ya `hecha`/`bloqueada`. Crea `.slice-runner/` y su `.gitignore` (con `stream.log`) si no existen. Abre el stream con la linea `select`.
- Deriva un slug para la rama: `slice/NN-slug`.

### 2. Autodetectar comandos del repo (Makefile primero)

Infierelos, no los asumas. Cachea lo detectado en la respuesta.

- **Prioridad 1 — Makefile**: si hay `Makefile`, usa sus targets (`make test`, `make check-types`, `make check-style`/`make linting`, `make fastapi-migrate`, `make env-start`...). En muchos repos todo corre en Docker via `make`; lanzar `pytest`/`ruff`/`mypy` directos fallaria. Lee el Makefile para saber que target cubre cada puerta.
- **Prioridad 2 — pyproject/tox**: si no hay Makefile util, cae a `ruff`, `mypy` (leyendo `[tool.mypy]`), `pytest` (rutas/opts de `pyproject.toml`/`tox.ini`).
- **Workflow de CI**: identifica el workflow de `.github/workflows/*.yml` que corre en `pull_request`.
- Si una puerta no tiene comando claro, pregunta antes de continuar.

### 3. Alinear antes de implementar (check-alignment)

- Resume: slice elegida, AC, capa(s) afectada(s), comando de validacion que aplicara, y como piensa abordarla.
- Si la spec pre-hornea codigo, contrastalo contra `docs/conventions/` + `CLAUDE.md` y **senala cualquier violacion antes de escribir** (no lo transcribas a ciegas).
- Espera go/no-go del usuario. Esto evita `silent-misalignment` y `ai-slop`.

### 4. Preparar worktree aislado

- Crea un git worktree aislado desde la rama base actualizada y una rama `slice/NN-slug`.
- Todo el trabajo de la slice ocurre en ese worktree para no colisionar con el workspace.

### 5. Implementar (subagente implementador)

Lanza un Agent (subagent_type `nw-software-crafter` o `general-purpose`) con instrucciones:

- Cargar `docs/conventions/` + `CLAUDE.md` del repo (si existen) y respetarlos como vara de medir; cargar tambien la skill `backend-best-practices`. En conflicto, ganan las convenciones del repo.
- **TDD segun la capa**:
  - Capas con test (dominio/aplicacion/API...): escribir primero el/los test(s) que codifican los AC, verlos fallar, luego el codigo minimo.
  - Capas eximidas por la convencion del repo (p. ej. modelos ORM y migraciones alembic que no se testean por separado): no forzar test-first; la validacion es "suite intacta + verificacion del efecto" (p. ej. el `SELECT` que exige el plan).
- **Refactor tras cada verde.** Una vez los tests pasan, hacer una pasada de refactor (eliminar duplicacion, mejorar nombres y estructura) manteniendo el verde, antes de entregar. La evidencia empirica senala el refactor tras verde -no el orden test-first- como el verdadero driver de calidad y mantenibilidad en agentes; no lo difieras a una pasada final.
- No sobredimensionar: lo minimo para los AC. Nada de andamiaje de slices futuras.
- Devolver: ficheros tocados, tests anadidos (si aplica) y resumen del enfoque.

### 6. Verificar (subagente verificador, distinto)

Lanza un Agent **diferente** (subagent_type `nw-software-crafter-reviewer` o `general-purpose`), adversarial.

**Su valor es la revision de convenciones y arquitectura, no re-testear.** La correccion del comportamiento la gobiernan CI + los AC; duplicar esa validacion con un segundo agente que re-deriva coberturas sale caro y no aporta (evidencia empirica sobre split authorship). Por eso el verificador **ejecuta** las puertas deterministas pero concentra su **juicio** en convenciones, boundaries y constraints.

- Cargar `docs/conventions/` + `CLAUDE.md` como vara de medir principal y **contrastar el diff contra ellos**, citando regla + path en cada hallazgo (esto es lo que caza cosas como una migracion que siembra datos donde la convencion lo prohibe). Cargar tambien `backend-best-practices` como vara secundaria para lo que las convenciones del repo no cubren. En conflicto, ganan las convenciones del repo.
- Ejecutar las puertas deterministas con los comandos del paso 2 (Makefile primero) y capturar output. Es ejecucion, no re-derivacion: no reimplementes ni reinventes coberturas de test.
- TDD consciente de capa (comprobacion barata, no re-testeo): en capas con test, que exista un test por AC y que preceda a la implementacion; en capas eximidas, "suite intacta + efecto verificado".
- **Calidad de tests (test-desiderata)**: si la slice anade o toca tests, correr la skill `test-desiderata` sobre ellos. Bloquea el gate solo ante violaciones **graves** (no determinista, no aislado, o test que no verifica comportamiento real); las menores (legibilidad, velocidad, etc.) se reportan como aviso sin bloquear. En slices sin tests (infra/migracion), se salta.
- Comprobar las `Global Constraints` de la spec (Formato B) y los boundaries de las dos-arboles (nucleo sin infra, DI correcta, DTOs en boundaries).
- Veredicto: PASA / FALLA con motivos concretos.
- Si FALLA: devolver al paso 5 con los motivos (max 2 reintentos). Si agota reintentos, para y reporta.

### 7. Abrir PR

- Commit con mensaje que referencia la slice (nunca en `master`/`main`). Push de la rama.
- `gh pr create` con cuerpo que: enlaza la spec, lista los AC cumplidos y resume los cambios.
- No marcar como ready-to-merge automaticamente mas alla de lo normal; el merge es humano.

### 8. Esperar CI verde (puerta final)

- `gh pr checks --watch` (o poll periodico) hasta verde o rojo. Respeta un timeout de espera razonable.
- **Verde**: marca la slice como hecha (Formato A: `[x]`; Formato B: cabecera de estado), **escribe la entrada en el ledger** (estado `hecha`, intentos, tokens/$, `pr_url`, `ci_result`, duracion) y emite `ci green` + `done` al stream. Resume el PR y **para**.
- **Rojo**: trae los logs del check fallido (`gh run view --log-failed`), un reintento via paso 5 con esos logs.
  - Si tras el reintento sigue roja: marca la slice como bloqueada (`[!]` / cabecera), **escribe la entrada en el ledger** (estado `bloqueada`, motivo), emite `blocked: ci rojo` al stream, **deja el PR abierto**, resume el fallo con logs y **para** (circuit breaker). No cierres el PR ni descartes el worktree.
- Si en cualquier momento se supera el presupuesto de tokens/$ de la slice: escribe la entrada `abortada-presupuesto`, emite `abort: presupuesto` y para.

## Fin

Al parar, reporta siempre: slice ejecutada, estado (hecha / bloqueada / abortada-presupuesto), URL del PR, resultado de CI, coste de la slice, y siguiente slice pendiente. Si quedan slices pendientes, sugiere volver a invocar (o envolver en `/loop` para Nivel 2).
