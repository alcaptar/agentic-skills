---
name: slice-runner
description: Ejecuta una slice de una spec markdown de principio a fin. Usar cuando el usuario tenga una spec en .md (checklist de slices con nombre y AC) y quiera implementar la siguiente (o una concreta) de forma autonoma - implementar con TDD consciente de capa, verificar con un agente independiente que carga las convenciones del repo, abrir PR y esperar a que la CI este verde, y parar. Aplica si dice "corre la siguiente slice", "implementa la slice X de la spec", "slice-runner", o describe el flujo spec -> slice -> PR -> CI.
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
- **Determinista lo que es regla exacta (`offload-deterministic`).** Lo que se puede comprobar con una regla (higiene del diff staged, formato del conventional commit) NO se delega al juicio del verificador: lo resuelve el script `scripts/gates.py`, cuyo exit code es autoritativo. El verificador gasta su presupuesto solo en lo semantico: convenciones y arquitectura del repo. No se pide dos veces a la IA lo que un script decide una vez.
- **TDD consciente de capa.** Por defecto TDD estricto: test rojo por cada AC antes del codigo, y el verificador comprueba que el test precede a la implementacion. Pero si las convenciones del repo eximen una capa (p. ej. modelos ORM y migraciones que no se testean por separado), la puerta para esa slice es "suite intacta + verificacion de datos/efecto", no test-first por AC. La convencion del repo decide, no este documento.
- **Alinear antes de implementar.** Antes de escribir codigo, mostrar el entendimiento de la slice (alcance, AC, capa afectada, comando de validacion) y esperar go/no-go. Nunca transcribir a ciegas el codigo pre-horneado de una spec: validalo contra las convenciones primero.
- **Seguir `backend-best-practices`.** El implementador carga esa skill y respeta hexagonal/DDD, DI, Pydantic en boundaries, subordinada siempre a las convenciones del repo.
- **El estado del run es efimero.** La spec y `.slice-runner/` (checklist + ledger) SON el estado durante el run, pero viven **gitignored** y se **descartan al terminar** (fin del run). El agente olvida entre slices; el estado efimero es su memoria intra-run, y el registro duradero son las PRs mergeadas, no ficheros en el repo.
- **La PR solo lleva el codigo de la slice.** El commit stagea unicamente los ficheros de codigo/test que produjo el implementador (`git add` explicito, nunca `-A`/`.`). Spec, ledger, planes y design-docs jamas entran en la PR.
- **Contexto fresco por slice.** Cada slice arranca sin arrastrar la conversacion de la anterior; lo que persiste entre slices es la spec + el ledger, que se re-leen al empezar. Evita la degradacion de contexto (patron Ralph) y hace seguro el Nivel 2 (`/loop`).
- **Circuit breaker.** Maximo 2 reintentos por fase. Ademas, **presupuesto de coste**: si la slice supera el limite de tokens/$ configurado, para con estado `abortada-presupuesto`. Si la CI sigue roja tras el reintento, para, deja el PR abierto y reporta con logs.
- **Esperas no bloqueantes.** Prohibido lanzar shells bloqueantes largas para esperar (nada de `gh pr checks --watch`, `sleep` largos, ni polls que se queden colgados 30-60 min). Toda espera (CI verde, merge de la PR) se hace con **ticks acotados en background + notificacion** (o la herramienta `Monitor`), devolviendo el control entre ticks. Una espera nunca debe monopolizar una shell ni la sesion.
- **No asumir worktree.** Por defecto se trabaja en una rama normal. Solo se usa un git worktree aislado si se van a paralelizar varias slices concurrentes (Nivel 2) o si el repo ya declara config de worktrees.

## Formato de spec

La spec es un **checklist de slices**. Un fichero con una o varias slices; cada item del checklist
es una slice, con **nombre** y AC embebidos. Si el `.md` no encaja en este formato, para y pide una
spec valida (o sugiere `/slice-spec` para generarla).

```markdown
## Slices
- [ ] slice-01 (cantidad-vo): Crear value object `Cantidad` con validacion de rango
      AC: rechaza negativos; tests en test/domain/test_cantidad.py
- [x] slice-02 (ajustar-stock): Caso de uso `AjustarStock` (puerto + adaptador)
      AC: emite evento StockAjustado; no toca infra directamente
```

Unidad de trabajo = cada item `- [ ]`. `[ ]` pendiente, `[x]` hecha, `[!]` bloqueada. Una feature de
una sola slice es simplemente un checklist con una unica linea.

- **Nombre de slice (obligatorio en specs nuevas).** Entre parentesis tras el id va el `name`
  en kebab-case: `slice-01 (cantidad-vo): ...`. El name es estable y determinista: alimenta la
  rama (`slice/01-cantidad-vo`) y el scope del commit (`feat(cantidad-vo): ...`), sin derivar
  slugs de texto libre.
- **Type opcional.** Por defecto el commit es `feat`. Para otro type, prefijalo dentro del
  parentesis: `slice-03 (refactor: extraer-repo): ...` ⇒ `refactor(extraer-repo): ...`.
- **Restricciones duras = AC.** Lo que la slice debe respetar (p. ej. "no toca infra directamente")
  se expresa como un AC comprobable mas; el verificador comprueba los AC.
- **Compatibilidad.** Si una slice no trae `(name)`, deriva un slug del titulo y **avisa** de que la
  spec deberia declarar nombre. No bloquea el run.

### Estado

- Marca el item de la slice `[ ]`/`[x]`/`[!]`.
- `[!]` / bloqueada = CI roja no resuelta; deja el PR abierto.
- **Recuerda: el marcado de estado es efimero.** Como la spec no se comitea (ver abajo), este
  marcado solo persiste durante el run y se descarta al terminar. Sirve de memoria intra-run.

## Estado del run: efimero y gitignored

Todo el estado del run (spec + `.slice-runner/`) es **efimero**: vive gitignored durante el run
y se **descarta al terminar** (ver "Fin"). Nunca se comitea. Durante el run es la memoria del
contexto-fresco; el registro duradero son las PRs mergeadas, no ficheros en el repo.

Esto responde al feedback "la PR solo debe llevar los ficheros de la slice": si la spec y el
ledger estan gitignored, no pueden colarse en un commit. La otra mitad la asegura la regla de
staging del paso 7 (`git add` solo de los ficheros de codigo).

### `.slice-runner/runs.jsonl` (efimero, no versionado)

Ledger append-only: una linea JSON por slice al cerrarla. Sirve de memoria intra-run para el
contexto fresco: que slices ya estan cerradas en este run. Esquema minimo:

    {"slice_id":"slice-01","name":"cantidad-vo","estado":"hecha","pr_url":"...","duracion_s":0,"ts":"2026-07-17T12:00:00Z"}

- Estados: `hecha` | `bloqueada` | `abortada-presupuesto`.
- Al arrancar una slice (paso 1), leer el ledger para no repetir lo ya `hecha`/`bloqueada` en este run.

### `.slice-runner/stream.log` (efimero, no versionado)

Stream en vivo legible para seguir el run en directo desde otra terminal:

    tail -f .slice-runner/stream.log

La skill anexa una linea por transicion de fase, formato `YYYY-MM-DD HH:MM:SS  slice-NN  <fase>  <detalle>` (fecha completa, no solo la hora). Transiciones a emitir: `select`, `align`, `implement start`, `implement done`, `verify PASA|FALLA`, `pr <url>`, `ci green|red`, `waiting: merge`, `done`, `blocked: <motivo>`, `abort: presupuesto`. `waiting: merge` significa **esperando una decision tuya** (el merge), no parado; `done`/`blocked`/`abort` son parada real. Es un stream compartido: varias terminales pueden tail-earlo a la vez (patron de deploy-monitor).

### `.slice-runner/state.json` (efimero, no versionado)

Estado vivo del run para que el panel muestre **todas** las slices (no solo las cerradas) y sepa que spec leer. Se reescribe en cada transicion:

    {"spec_path":"spec.md","slice_actual":"slice-02","fase":"waiting: merge","ts":"2026-07-17T12:00:00Z"}

- `spec_path` deja que el panel lea el checklist de la spec y liste las slices `pendiente`.
- `fase` refleja la fase en curso (incluido `waiting: merge`) para distinguir "esperandote" de "parado".

### Setup

La primera vez, crear `.slice-runner/.gitignore` con una sola linea `*` (y otra `!.gitignore`
para conservar el propio ignore). **Todo `.slice-runner/` es efimero y no versionado**: ledger,
stream y estado. Si la spec vive fuera de `.slice-runner/`, aseguratela tambien fuera de la PR:
`.slice-runner/spec.md` es la ubicacion por defecto (gitignored); si el usuario apunta a una
spec en otra ruta, **nunca la stagees** (la regla de staging del paso 7 ya lo garantiza).
`deploy-watch` anexa a estos mismos ficheros su veredicto + señales del deploy.

### Metricas durables (fuera del repo, sobreviven al run)

Distinto del estado efimero: `~/.claude/slice-runner/metrics.jsonl` es un log **durable**
append-only, un registro por slice cerrada, que **no vive en el repo** (por tanto nunca entra en
una PR) y **no se borra** al descartar `.slice-runner/`. Existe para responder con datos "cuando
subir de nivel" sin depender de la intuicion. Lo escribe y lo agrega `scripts/metrics.py`
(`offload-deterministic`): la IA no estima cifras a ojo.

    python3 ~/.claude/skills/slice-runner/scripts/metrics.py report [--repo <repo>]

Reporta: tasa de FALLA del verificador, % de slices al primer intento, media de reintentos,
tasa de CI roja, duracion media. Es el instrumento para el "confianza en el loop" del Step 3 del
mapa de madurez. Coste en tokens no se mide aqui (sale de OTel de Claude Code).

`<repo>` debe ser un **identificador estable** del repo (p. ej. el nombre del directorio raiz o el
slug del remoto), el mismo en `record` y en `report --repo`, para que las cifras agrupen bien.

## Steps

### 1. Localizar spec y seleccionar slice

- Pide la ruta de la spec `.md` si no se ha dado.
- **Comprueba que es un checklist de slices** (ver "Formato de spec"). Si no encaja, para y pide una
  spec valida (o sugiere `/slice-spec`).
- Selecciona la slice: la indicada por el usuario, o la primera `[ ]`.
- Extrae titulo, alcance y AC de la slice. Si no hay AC, para y pidelos: sin AC no hay puerta de verificacion.
- **Lee `.slice-runner/runs.jsonl`** (si existe) para no repetir slices ya `hecha`/`bloqueada`. Crea `.slice-runner/` y su `.gitignore` (una linea `*` + `!.gitignore`; todo efimero) si no existen. Escribe `state.json` con `spec_path` y la slice seleccionada, y abre el stream con la linea `select`.
- **Toma el `name` de la slice** (entre parentesis tras el id). Si no hay name, deriva un slug del titulo y avisa. La rama es `slice/NN-<name>` (p. ej. `slice/01-cantidad-vo`). Toma tambien el `type` opcional (por defecto `feat`).

### 2. Autodetectar comandos del repo (Makefile primero)

Infierelos, no los asumas. Cachea lo detectado en la respuesta.

- **Prioridad 1 — Makefile**: si hay `Makefile`, usa sus targets (`make test`, `make check-types`, `make check-style`/`make linting`, `make fastapi-migrate`, `make env-start`...). En muchos repos todo corre en Docker via `make`; lanzar `pytest`/`ruff`/`mypy` directos fallaria. Lee el Makefile para saber que target cubre cada puerta.
- **Prioridad 2 — pyproject/tox**: si no hay Makefile util, cae a `ruff`, `mypy` (leyendo `[tool.mypy]`), `pytest` (rutas/opts de `pyproject.toml`/`tox.ini`).
- **Workflow de CI**: identifica el workflow de `.github/workflows/*.yml` que corre en `pull_request`.
- Si una puerta no tiene comando claro, pregunta antes de continuar.

### 3. Alinear antes de implementar (check-alignment)

- Resume: slice elegida (id + `name`), AC, capa(s) afectada(s), comando de validacion que aplicara, `type(name)` de conventional commit que usara el commit/PR, y como piensa abordarla.
- Si el cambio claramente **no es un `feat`** (p. ej. refactor o fix) y la spec no declaro type, confirma el type con el usuario aqui (barato; evita un scope de commit erroneo).
- Si la spec pre-hornea codigo, contrastalo contra `docs/conventions/` + `CLAUDE.md` y **senala cualquier violacion antes de escribir** (no lo transcribas a ciegas).
- Espera go/no-go del usuario. Esto evita `silent-misalignment` y `ai-slop`.

### 4. Preparar rama de trabajo

- **Por defecto, rama normal**: `git switch -c slice/NN-slug` desde la rama base actualizada. No asumas worktree: no todos los repos tienen config de worktrees, y una slice por invocacion no colisiona con nada.
- **Worktree solo si aplica**: usa un git worktree aislado unicamente si se van a paralelizar varias slices concurrentes (Nivel 2) o si el repo ya declara config de worktrees. En ese caso crea el worktree desde la base actualizada con la rama `slice/NN-slug`.

### 5. Implementar (subagente implementador)

Lanza un Agent (subagent_type `nw-software-crafter` o `general-purpose`) con instrucciones:

- Cargar `docs/conventions/` + `CLAUDE.md` del repo (si existen) y respetarlos como vara de medir; cargar tambien la skill `backend-best-practices`. En conflicto, ganan las convenciones del repo.
- **TDD segun la capa**:
  - Capas con test (dominio/aplicacion/API...): escribir primero el/los test(s) que codifican los AC, verlos fallar, luego el codigo minimo.
  - Capas eximidas por la convencion del repo (p. ej. modelos ORM y migraciones alembic que no se testean por separado): no forzar test-first; la validacion es "suite intacta + verificacion del efecto" (p. ej. el `SELECT` que exige el plan).
- **Refactor tras cada verde.** Una vez los tests pasan, hacer una pasada de refactor (eliminar duplicacion, mejorar nombres y estructura) manteniendo el verde, antes de entregar. La evidencia empirica senala el refactor tras verde -no el orden test-first- como el verdadero driver de calidad y mantenibilidad en agentes; no lo difieras a una pasada final.
- No sobredimensionar: lo minimo para los AC. Nada de andamiaje de slices futuras.
- **No tocar spec, ledger ni artefactos.** Solo ficheros de codigo/test de la slice. No escribas
  planes, design-docs ni marques la spec: eso es trabajo del orquestador y no va a la PR.
- Devolver: **la lista explicita de rutas de codigo/test creadas o modificadas** (es lo que se
  stageara en el paso 7, nada mas), tests anadidos (si aplica) y resumen del enfoque.

### 6. Verificar (subagente verificador, distinto)

Lanza un Agent **diferente** (subagent_type `nw-software-crafter-reviewer` o `general-purpose`), adversarial.

**Su valor es la revision de convenciones y arquitectura, no re-testear.** La correccion del comportamiento la gobiernan CI + los AC; duplicar esa validacion con un segundo agente que **re-deriva coberturas** sale caro y no aporta (evidencia empirica sobre split authorship). Por eso el verificador **ejecuta** las puertas deterministas pero concentra su **juicio** en convenciones, boundaries y constraints. Matiz importante: "no re-testear" = no re-derivar ni reimplementar cobertura; **si** entra comprobar, por lectura, que los tests que codifican los AC realmente los fijan (que no sean un proxy debil). Eso es barato y es justo donde el segundo par de ojos aporta -cazar un AC mal traducido, no re-verificar comportamiento ya correcto-.

Recorre esta **rubrica cerrada** entera y reporta item a item. Cada item esta marcado `[det]` (lo resuelve un script y solo consumes su resultado) o `[sem]` (lo juzgas tu):

- `[det]` **Puertas objetivas**: ejecutar lint, tipos y tests con los comandos del paso 2 (Makefile primero) y capturar output. Es ejecucion, no re-derivacion: no reimplementes ni reinventes coberturas de test. El exit code manda.
- `[sem]` **Convenciones y arquitectura**: cargar `docs/conventions/` + `CLAUDE.md` como vara de medir principal y **contrastar el diff contra ellos**, citando regla + path en cada hallazgo (esto es lo que caza cosas como una migracion que siembra datos donde la convencion lo prohibe). Cargar tambien `backend-best-practices` como vara secundaria para lo que las convenciones no cubren. En conflicto, ganan las convenciones del repo.
- `[sem]` **Patron de rollout/entrega correcto (no solo bien implementado).** Caso concreto del check de convenciones anterior, resaltado aparte por ser un fallo recurrente. No basta con que el patron elegido este bien ejecutado y sea coherente consigo mismo: comprueba que **es el patron que la convencion del repo prescribe para este tipo de cambio**. Disparador general: si el cambio toca la **firma/constructor/contrato publico** de una accion o caso de uso, la convencion suele exigir un patron distinto (duplicar la accion / expand-contract) que si solo cambia logica interna (gatear en el metodo). Deriva el criterio de `docs/conventions/` (p. ej. delivery/testing), **no** de como quedo una slice anterior: el codigo ya mergeado es circunstancia, no regla. Si el patron elegido no encaja con lo que pide la convencion para este cambio, es **FALLA (severidad alta)**, citando regla + path. Este es el check que un verificador que solo mira la implementacion deja pasar.
- `[sem]` **Boundaries**: nucleo sin infra, DI correcta, DTOs (Pydantic) en boundaries.
- `[sem]` **TDD consciente de capa** (comprobacion barata, no re-testeo): en capas con test, que exista un test por AC y que preceda a la implementacion; en capas eximidas, "suite intacta + efecto verificado".
- `[sem]` **Conformidad con los AC (no solo que existan tests).** Distinto del punto anterior (que comprueba que *hay* un test por AC) y de test-desiderata (que juzga la calidad *generica* del test); este comprueba que se **cumple el cometido del AC**. Para cada AC: (1) **mapeo AC↔test**: que el test asserte lo que *ese* AC exige, no una version debilitada -la calidad generica del test (verifica comportamiento real, aislamiento...) es de test-desiderata, no la repitas aqui-; (2) que el **codigo cumpla la intencion** del AC, no solo que pase su propio test (pregunta adversarial: "¿podria pasar este test y aun asi violar lo que el AC pedia?") -lectura acotada, no re-derivar cobertura-; (3) codigo que implementa **comportamiento que ningun AC pidio** (feature especulativa, andamiaje de slices futuras). El refactor tras verde que permite el paso 5 (extraer helpers, mejorar estructura) **traza al AC** y no es hallazgo. FALLA (severidad alta) si un AC no queda pineado, si el codigo no cumple su intencion, o si hay comportamiento sin AC que lo justifique.
- `[sem]` **Calidad de tests (test-desiderata)**: si la slice anade o toca tests, correr la skill `test-desiderata` sobre ellos. Bloquea solo ante violaciones **graves** (no determinista, no aislado, o test que no verifica comportamiento real); las menores (legibilidad, velocidad...) se reportan como aviso sin bloquear. En slices sin tests (infra/migracion), se salta.

La higiene del diff staged y el formato del commit **no** se comprueban aqui: son `[det]` puros y los ejecuta `scripts/gates.py` en el paso 7, cuando el staging ya existe. No los re-juzgues por lectura.

**Veredicto estructurado (no prosa).** Lanza este Agent con `schema` para que devuelva exactamente:

```json
{
  "veredicto": "PASA | FALLA",
  "hallazgos": [
    {"regla": "boundaries", "path": "src/infra/x.py", "severidad": "alta | media | baja", "detalle": "..."}
  ]
}
```

- Reglas del veredicto: **FALLA** si alguna puerta objetiva `[det]` falla o si hay algun hallazgo `severidad: alta`. Los `media`/`baja` se reportan pero no bloquean por si solos (juicio: si se acumulan, el verificador puede subir a FALLA explicando por que).
- El schema se valida en la capa de tool: no parsees texto libre.
- Si FALLA: devolver al paso 5 con los `hallazgos` (max 2 reintentos). Guarda el conteo de hallazgos por severidad y el veredicto final: alimentan las metricas.
- **Si agota los reintentos con FALLA**: marca la slice como bloqueada (`[!]`), **escribe la entrada en el ledger** (estado `bloqueada`, motivo `verify`), emite `blocked: verify` al stream, **registra la metrica durable** (`veredicto=FALLA`, `ci=none`; ver paso 8) y **para**. No sigas al paso 7: sin PASA del verificador no se abre PR. Sin esto, el rechazo del verificador -justo lo que queremos medir- no dejaria rastro.

### 7. Abrir PR

- **Stagea SOLO los ficheros de codigo/test que devolvio el implementador (feedback 3).** Usa
  `git add <ruta1> <ruta2> ...` con la lista explicita; **prohibido `git add -A`, `git add .`
  o `git commit -a`**. La spec, `.slice-runner/`, planes y design-docs NO entran en la PR (ya
  estan gitignored o simplemente no se stagean).
- **Puerta determinista de higiene (`[det]`).** Tras stagear, corre
  `python3 ~/.claude/skills/slice-runner/scripts/gates.py pr-hygiene --repo . --spec <ruta-spec> --allow <ruta1> --allow <ruta2> ...`
  con la lista exacta que devolvio el implementador. Exit 0 = PASA. Si FALLA (algo staged fuera de
  lo declarado, o un artefacto: spec, `.slice-runner/`, plan, design-doc), **corrige el staging**
  (`git restore --staged`) y reintenta; no lo re-interpretes a ojo. No commitees hasta PASA.
- **Conventional commit.** Mensaje y titulo de PR = `type(name): resumen`, con el `type` (por
  defecto `feat`) y el `name` de la slice como scope: p. ej. `feat(cantidad-vo): add Cantidad value
  object`. Redactar un conventional commit lo haces bien sin puerta; lo unico determinista aqui es
  que el `name` (scope) viene de la spec, no de un slug inventado. Cuerpo del commit opcional con
  detalle. Nunca commitees en `master`/`main`. Push de la rama `slice/NN-<name>`.
- `gh pr create` con titulo `type(name): resumen` y cuerpo que: lista los AC cumplidos y resume
  los cambios. **No enlaces la spec por ruta** (es efimera y no vive en el repo); resume su
  contenido si hace falta.
- No marcar como ready-to-merge automaticamente mas alla de lo normal; el merge es humano.

### 8. Esperar CI verde (puerta final)

- Espera hasta verde o rojo con **ticks acotados en background + notificacion** (o la herramienta `Monitor`), **nunca** `gh pr checks --watch` ni un `sleep` largo que bloquee la shell/sesion (principio de esperas no bloqueantes; es trabajo deterministico que hace el harness, no la IA poll-eando). Cada tick consulta `gh pr checks --json` y devuelve el control. Respeta un timeout de espera razonable.
- **Verde**: marca la slice como hecha (`[x]`), **escribe la entrada en el ledger** (estado `hecha`, `pr_url`, duracion), emite `ci green` al stream, **registra la metrica durable** (ver abajo, `ci=green`) y **pasa al paso 9** (no paras aqui).
- **Rojo**: trae los logs del check fallido (`gh run view --log-failed`), un reintento via paso 5 con esos logs.
  - Si tras el reintento sigue roja: marca la slice como bloqueada (`[!]`), **escribe la entrada en el ledger** (estado `bloqueada`, motivo), emite `blocked: ci rojo` al stream, **registra la metrica durable** (`ci=red`), **deja el PR abierto**, resume el fallo con logs y **para** (circuit breaker). No cierres el PR ni descartes la rama/worktree.
- Si en cualquier momento se supera el presupuesto de tokens/$ de la slice: escribe la entrada `abortada-presupuesto`, emite `abort: presupuesto`, **registra la metrica durable** (`veredicto=abortada-presupuesto`) y para.

**Registro de la metrica durable (`[det]`).** Al cerrar la slice, en **cualquiera** de los caminos de cierre (verify terminal FALLA del paso 6, CI verde, CI roja terminal, o presupuesto), anexa un registro con:

```
python3 ~/.claude/skills/slice-runner/scripts/metrics.py record --repo <repo> --slice <slice_id> --name <name> \
  --veredicto <PASA|FALLA|abortada-presupuesto> --ci <green|red|none> \
  --hallazgos-alta N --hallazgos-media N --hallazgos-baja N \
  --reintentos-implement N --reintentos-ci N --duracion-s N
```

- `veredicto` = el del verificador del paso 6 (`PASA`/`FALLA`), o `abortada-presupuesto` si paro el presupuesto. Los conteos de `hallazgos` salen del veredicto estructurado del paso 6.
- Este log vive **fuera del repo** (`~/.claude/slice-runner/metrics.jsonl`), sobrevive al descarte del estado efimero y **nunca entra en una PR**. Coste en tokens: opcional (`--coste-tokens`); si no lo tienes de OTel, no lo inventes (se omite).

### 9. Esperar el merge y encadenar el deploy

El merge sigue siendo **humano** (lo haces tu en GitHub); lo que se automatiza es la **transicion**, para que no tengas que decir "continua" a mano.

- Actualiza `state.json` a `fase: "waiting: merge"` y emite `waiting: merge` al stream. Esto es **espera de una decision tuya**, no parada: el panel lo destaca asi.
- Vigila el estado de la PR con **ticks acotados en background + notificacion** (`gh pr view --json state,mergedAt`), nunca una shell bloqueante larga. Respeta un timeout razonable de espera de merge.
  - **Merged**: invoca automaticamente la skill `deploy-watch` (sin pedir "continua"). `deploy-watch` arranca sola e infiere servicio/namespace; solo te preguntara si la inferencia es ambigua (`check-alignment` solo cuando hay duda real).
  - **Timeout / cerrada sin merge**: emite el estado correspondiente al stream y **para**, dejando el PR como este. Reanudas invocando de nuevo cuando quieras.

## Fin

Al parar (o al ceder el control a `deploy-watch`), reporta siempre: slice ejecutada, estado (hecha / bloqueada / abortada-presupuesto / esperando-merge), URL del PR, resultado de CI, coste de la slice, y siguiente slice pendiente. Si quedan slices pendientes, sugiere volver a invocar (o envolver en `/loop` para Nivel 2).

### Descarte del estado efimero (fin del run)

Cuando **no quedan slices pendientes** (todas las de la spec estan `hecha`/`bloqueada`), el run
ha terminado: descarta el estado efimero.

- Borra `.slice-runner/` (`rm -rf .slice-runner/`) y la spec (`.slice-runner/spec.md`, o la ruta
  externa que se uso). No se comitea nada de esto: el registro duradero son las PRs mergeadas.
- **No toques `~/.claude/slice-runner/metrics.jsonl`**: es durable, vive fuera del repo y es
  justo lo que debe sobrevivir al run para medir la evolucion del loop.
- Hazlo solo al final del run completo, **no por slice**: durante el run el ledger y la spec son
  la memoria del contexto-fresco y del encadenado con `/loop`.
- Si el run se para con slices aun pendientes (bloqueo, presupuesto, o una sola invocacion de
  Nivel 1 con mas slices por delante), **no borres nada**: el estado debe sobrevivir para el
  siguiente ciclo. El descarte es exclusivamente el cierre del run entero.
