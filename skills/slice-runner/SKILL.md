---
name: slice-runner
description: Ejecuta una slice de una spec markdown de principio a fin. Usar cuando el usuario tenga una spec en .md (checklist de slices con nombre y criterios de aceptacion) y quiera implementar la siguiente (o una concreta) de forma autonoma - implementar con TDD consciente de capa, verificar con un agente independiente que carga las convenciones del repo, abrir PR y esperar a que la CI este verde, y parar. Aplica si dice "corre la siguiente slice", "implementa la slice X de la spec", "slice-runner", o describe el flujo spec -> slice -> PR -> CI.
---

# Slice Runner

STARTER_CHARACTER = [slice-runner]

Emite `[slice-runner]` al inicio de cada respuesta mientras ejecutas este proceso, como testigo de que el contexto esta intacto y sigues estas reglas. (Marcador de texto en lugar de emoji por preferencia del usuario.)

## Description

Dada una spec en markdown con un checklist de slices, ejecuta **una** slice pendiente de principio a fin: implementa con TDD estricto, la verifica con un agente independiente, abre un PR y espera a que la CI este verde. Luego **para**. No hace merge: el merge lo aprueba el humano.

Nivel de autonomia 1: un ciclo por invocacion. Para encadenar slices, envolver esta skill en `/loop`.

## Principios no negociables

- **El que implementa no verifica.** La implementacion y la verificacion las hacen subagentes distintos (Agent tool), con instrucciones distintas. El verificador es adversarial.
- **Los subagentes no son un detalle de implementacion: son la garantia.** Esta skill **no puede ejecutarse sin ellos**, y por eso **invocarla cuenta como pedirlos**: no es iniciativa del agente, es la skill haciendo su trabajo, asi que no pidas permiso para lanzarlos. Si el entorno los veta (veto global al Agent tool, politica de la organizacion, `slice-verifier` sin resolver), **dilo siempre** y decide con este criterio: **¿se puede declarar la degradacion en el artefacto que produces?** Si se puede, degrada y declaralo **ahi**, no solo en el chat; si el artefacto entero significa justo la garantia que has perdido, **para**. Esta skill cae del lado de **parar**, y en el **paso 3**: su artefacto es una **PR con veredicto PASA**, donde el veredicto *es* la afirmacion de haberse verificado, y no hay forma de declarar esa degradacion dentro de la PR -degradado seria falso, y **falso de forma invisible aguas abajo**, porque quien revise asume que paso el pipeline-. Parar no cuesta nada irreversible: no hay nada en produccion. Fail-closed, igual que `pr-hygiene` y `diff-bundle`. (`deploy-watch` aplica el **mismo criterio** y cae del otro lado, porque su veredicto **si** puede declarar su procedencia: artefacto distinto, no incoherencia.)
- **Las convenciones del repo mandan.** Implementador y verificador cargan como vara de medir las **fuentes de convencion declaradas en el issue** (seccion `## Fuentes de convencion`: docs y skills de proyecto), por encima de cualquier default generico de hexagonal/DDD. En conflicto, ganan las convenciones del repo. No se asumen rutas fijas: las fuentes se descubren por repo y las declara `slice-spec` en el issue; `slice-runner` solo las lee. Si el issue no trae esa seccion, **para** y pide anadirla con `slice-spec` (no ejecutes con la vara vacia: fue la causa raiz de desviaciones silenciosas de convencion). Sin la vara, el verificador no puede cazar violaciones reales (p. ej. una migracion que siembra datos donde la convencion lo prohibe).
- **La observabilidad es parte de la slice.** Si la slice declara `SENAL:` y la senal **no existe
  todavia**, instrumentarla es codigo de produccion de **esta** slice (con la libreria de monitoring
  del repo, nunca ad-hoc en paralelo) y su **emision** se fija con un test, igual que cualquier
  criterio de aceptacion. El valor vivo lo comprueba `deploy-watch` despues (paso 10). La escalera
  para decidir si hay que instrumentar o la senal ya existe gratis esta en
  `~/.claude/skills/slice-spec/references/observabilidad.md`. Si la slice **no** trae `SENAL` (spec
  anterior a este mecanismo), **avisa y sigue**: no bloquea. A diferencia de las fuentes de
  convencion, cuya ausencia hace imposible verificar, la ausencia de senal solo degrada la
  comprobacion post-deploy al veredicto generico, y eso `deploy-watch` **si** lo puede declarar en
  el issue.
- **Una slice puede vivir en otro repo.** La linea `REPO: <org>/<repo>` de la slice fija el repo
  destino (alertas en el repo de manifiestos, paneles en el de Grafana); ausente = el repo del issue.
  Cuando la hay, **todo el ciclo ocurre en ese repo**: comandos autodetectados (paso 2), rama (paso 4),
  puertas y diff (pasos 5-7), PR y CI (pasos 8-9). Y la **vara de medir es la de ESE repo** (su
  subseccion `### <org>/<repo>` en las fuentes del issue), no la del repo de la app. El issue sigue
  siendo uno solo: es la fuente de verdad del run.
- **Puertas de parada objetivas.** No hay PR mergeable sin lint limpio, tipos limpios, tests verdes y **CI verde**, ejecutados con los comandos reales del repo (paso 2), no con binarios asumidos.
- **El juez no ejecuta puertas ni ve output de build.** Las puertas deterministas (lint, tipos, tests) corren **antes** del verificador: el implementador las corre en su ciclo para tener feedback incremental, y el orquestador las re-corre como backstop (paso 6) porque el auto-reporte del implementador no es fuente de verdad. Cuando se invoca al verificador (paso 7) ya estan verdes por construccion, asi que no recibe nada de ellas: su presupuesto entero se gasta en lo semantico. Meter un traceback de pytest en el contexto del unico agente cuyo valor es el juicio es `limited-focus` autoinfligido, y un `ruff` sucio no debe consumir un reintento adversarial.
- **Determinista lo que es regla exacta (`offload-deterministic`).** Lo mecanico NO se delega al juicio de un agente: lo resuelve el script `scripts/gates.py`, cuyo exit code es autoritativo. Tres subcomandos: `pr-hygiene` (higiene del diff staged, paso 8), `checks` (ejecutar lint/tipos/tests con los comandos del paso 2 y devolver exit code + salida truncada, pasos 5 y 6) y `diff-bundle` (materializar el diff de la slice para el verificador, paso 7). No se pide dos veces a la IA lo que un script decide una vez, y ningun agente ve output crudo de build.
- **Los tests son ciudadanos de primera categoria.** Valen tanto o mas que el codigo de produccion: ahi va el mayor esfuerzo de calidad, y sobre todo la exigencia de que **testeen de verdad lo que la slice pretende construir**, no una version debilitada ni un proxy que pasa por casualidad. Un test que pasa sin fijar su criterio de aceptacion es un fallo tan grave como codigo roto. Con dientes, no como declaracion: el implementador aplica `writing-good-tests.md` de `superpowers:test-driven-development` (nombrar el cambio de produccion que haria fallar el test **antes** de escribirlo; asertar comportamiento real, nunca mocks; codigo de test fuera de produccion), y el verificador lo bloquea con severidad **alta** en el paso 7 (mapeo criterio↔test, fixture/wiring theater, manipulacion de tests, test-desiderata).
- **TDD consciente de capa.** El ciclo TDD lo define `superpowers:test-driven-development` (lo invoca el implementador, paso 5); aqui vive solo el delta: si las convenciones del repo eximen una capa (p. ej. modelos ORM y migraciones que no se testean por separado), la puerta de esa slice es "suite intacta + verificacion de datos/efecto" en vez del test-first por criterio. Decide la convencion del repo, no este documento ni superpowers.
- **Alinear antes de implementar.** Antes de escribir codigo, mostrar el entendimiento de la slice (alcance, criterios de aceptacion, capa afectada, comando de validacion) y esperar go/no-go. Nunca transcribir a ciegas el codigo pre-horneado de una spec: validalo contra las convenciones primero.
- **Seguir `backend-best-practices`.** El implementador carga esa skill y respeta hexagonal/DDD, DI, Pydantic en boundaries, subordinada siempre a las convenciones del repo.
- **El estado del run vive en el issue de GitHub.** La spec y el estado de cada slice viven en el cuerpo de un issue de GitHub (una feature = un issue): es la **unica fuente de verdad**, viva y duradera. No hay estado local (`.slice-runner/`, ledger ni panel). El agente olvida entre slices; al arrancar re-lee el issue. Registro duradero = issue (intencion + estado) + PRs mergeadas (codigo).
- **La PR cuenta la intencion, no el codigo.** El cuerpo de la pull request dice **que estaba mal y
  deja de estarlo** (la `INTENCION:` de la slice, encuadrada en la del issue), los criterios de
  aceptacion cumplidos y la `SENAL` a comprobar tras el despliegue. Nunca enumera ficheros, clases
  ni modulos: eso ya lo cuenta el diff, y repetirlo en prosa ocupa el sitio de lo unico que el diff
  no puede contar. Si el issue no declaraba intencion, la PR la reconstruye y **lo dice en el
  encabezado**: afirmar como declarado lo que se ha inferido es la clase de falsedad invisible aguas
  abajo que esta skill evita en todas partes.
- **La PR solo lleva el codigo de la slice.** El commit stagea unicamente los ficheros de codigo/test que produjo el implementador (`git add` explicito, nunca `-A`/`.`). Planes y design-docs jamas entran en la PR (la spec ya no es un fichero: vive en el issue).
- **Contexto fresco por slice.** Cada slice arranca sin arrastrar la conversacion de la anterior; lo que persiste entre slices es el **issue** (spec + estado), que se re-lee al empezar. Evita la degradacion de contexto (patron Ralph) y hace seguro el Nivel 2 (`/loop`).
- **Circuit breaker.** Maximo 2 reintentos por fase, y las **puertas tienen presupuesto propio** (2), separado del del verificador (2): gastar el presupuesto adversarial en un fallo mecanico es justo lo que este reparto evita. Ademas, **presupuesto de coste**: si la slice supera el limite de tokens/$ configurado, para con estado `abortada-presupuesto`. Si la CI sigue roja tras el reintento, para, deja el PR abierto y reporta con logs.
- **Esperas no bloqueantes.** Prohibido lanzar shells bloqueantes largas para esperar (nada de `gh pr checks --watch`, `sleep` largos, ni polls que se queden colgados 30-60 min). Toda espera (CI verde, merge de la PR) se hace con **ticks acotados en background + notificacion** (o la herramienta `Monitor`), devolviendo el control entre ticks. Una espera nunca debe monopolizar una shell ni la sesion.
- **No asumir worktree.** Por defecto se trabaja en una rama normal. Solo se usa un git worktree aislado si se van a paralelizar varias slices concurrentes (Nivel 2) o si el repo ya declara config de worktrees.

## Formato de spec (cuerpo del issue)

La spec vive en el **cuerpo de un issue de GitHub** (una feature = un issue). Es un **checklist de
slices**: cada slice es una linea de task-list con **nombre**, criterios de aceptacion embebidos y
un **marcador de estado**. Si el issue no encaja en este formato, para y pide una spec valida (o
sugiere `/slice-spec` para generarla).

```markdown
## Intencion
Hoy el ajuste de stock se hace a mano en la consola: no queda rastro de quien lo hizo
y cuando el recuento no cuadra no hay forma de reconstruir que paso.

## Fuentes de convencion
- doc: .claude/CLAUDE.md
- skill: .claude/skills/duplicate-action

### mercadona/mercadona.online.gke
- doc: templates/CLAUDE.md
- doc: tests/prometheus/README.md

## Slices
- [x] slice-01 (cantidad-vo): Crear value object `Cantidad` [mergeada] PR #11
      INTENCION: hoy cada endpoint revalida la cantidad a mano y ya se olvido en dos sitios
      ACEPTACION: rechaza negativos; tests en test/domain/test_cantidad.py
      SENAL: exenta - value object interno sin efecto observable
- [ ] slice-02 (ajustar-stock): Caso de uso `AjustarStock` [esperando-merge] PR #12
      INTENCION: hoy el ajuste se hace a mano y no queda rastro de quien lo hizo
      ACEPTACION: emite evento StockAjustado; no toca infra directamente
      SENAL: prometheus rate(application_stock_ajustado_total[5m]) > 0 en 10m post-deploy; critical
- [ ] slice-03 (alerta-ajuste): Alerta de ajustes fallidos [pendiente]
      REPO: mercadona/mercadona.online.gke
      INTENCION: hoy un ajuste fallido solo se descubre cuando alguien mira el panel
      ACEPTACION: ...
      SENAL: prometheus ALERTS{alertname="ShopAjusteFallido"} presente y == 0 en 24h; advisory
```

La seccion `## Fuentes de convencion` (punteros a la vara de medir del repo) la declara
`slice-spec`; `slice-runner` la exige y para si falta (paso 1). **Es por repo**: las lineas antes de
cualquier `### <org>/<repo>` son las del repo del issue, y cada subseccion declara la vara de un repo
destino. Unidad de trabajo = cada item `- [ ] slice-NN ...`. Una feature de una sola slice es un
checklist con una unica linea. El parseo y la reescritura de estas lineas los hace la logica pura de
`scripts/issue_body.py` (`offload-deterministic`); la I/O contra el issue es `gh`.

- **`## Intencion` e `INTENCION:`** — el por que, a nivel de feature y de slice: que esta mal hoy y
  deja de estarlo. Es lo que va al cuerpo de la pull request (paso 8). Se leen con
  `issue_body.parse_intencion(body)` y `slice.intencion`. Si faltan (issue anterior a este
  mecanismo), **avisa y sigue**: la PR reconstruye la intencion y declara que la infirio. La
  obligatoriedad vive en el contrato de `slice-spec`, no aqui.
- **`ACEPTACION:` (una o mas lineas)** — los criterios verificables antes de fusionar; los lee
  `slice.aceptacion`. La etiqueta **se llamaba `AC:`** y el parser sigue aceptando esa forma, porque
  hay issues abiertos escritos con ella; lo que se emite y se documenta es el nombre completo.
- **`SENAL:` (una o mas lineas)** — como se comprueba la slice **viva en produccion**; la consume
  `deploy-watch` (paso 10). `SENAL: exenta - <motivo>` cuando no aplica. Si falta, **avisa y sigue**
  (mismo trato que un `(name)` ausente): la obligatoriedad vive en el contrato de `slice-spec`.
- **`REPO:`** — repo destino de la slice. Ausente = el repo del issue.

- **Nombre de slice (obligatorio en specs nuevas).** Entre parentesis tras el id va el `name`
  en kebab-case: `slice-01 (cantidad-vo): ...`. El name es estable y determinista: alimenta la
  rama (`slice/01-cantidad-vo`) y el scope del commit (`feat(cantidad-vo): ...`), sin derivar
  slugs de texto libre.
- **Type opcional.** Por defecto el commit es `feat`. Para otro type, prefijalo dentro del
  parentesis: `slice-03 (refactor: extraer-repo): ...` ⇒ `refactor(extraer-repo): ...`.
- **Restricciones duras = criterio de aceptacion.** Lo que la slice debe respetar (p. ej. "no toca
  infra directamente") se expresa como un criterio comprobable mas; el verificador los comprueba.
- **Compatibilidad.** Si una slice no trae `(name)`, deriva un slug del titulo y **avisa** de que la
  spec deberia declarar nombre. No bloquea el run.

### Estado de cada slice (marcador en su linea)

El estado se codifica en la linea con `[estado]` (y `PR #N` cuando aplica):

- `pendiente` — aun no empezada.
- `en-curso` — implementando/verificando.
- `esperando-merge` — PR abierta, CI verde, esperando la decision humana de merge.
- `mergeada` — PR mergeada. **Es el unico estado que marca el checkbox `[x]`.**
- `bloqueada: <motivo>` — `sin-subagentes` (el entorno veta el Agent tool: para en el paso 3 sin escribir
  codigo), `puertas` (lint/tipos/tests sin arreglar tras los reintentos), `verify` (veto del verificador)
  o `ci-roja`. En `ci-roja` deja el PR abierto; en los otros tres no hay PR.
- `abortada: presupuesto` — supero el presupuesto de la slice.

`[x]` solo al merge mantiene la barra de progreso nativa de GitHub fiel a lo que esta en main. El
estado vive en el issue: es a la vez la memoria intra-run (al reanudar, una slice en
`esperando-merge` se retoma ahi, no se reimplementa) y el registro duradero.

## Estado del run: en el issue de GitHub

El estado del run vive **en el cuerpo del issue**, no en el repo. No hay `.slice-runner/`, ni
ledger, ni `state.json`, ni stream local, ni panel. El seguimiento se hace desde el issue de
GitHub: cualquiera con acceso al repo ve el estado de cada slice en todo momento.

- **Fuente de verdad**: el marcador `[estado]` de cada linea de slice en el cuerpo del issue.
- **Actualizacion**: en cada transicion macro, `slice-runner` reescribe **solo la linea de esa
  slice** (read-modify-write: `gh issue view --json body` -> `issue_body.set_slice_estado(...)` ->
  `gh issue edit --body`). No toca las demas lineas ni los criterios.
- **Memoria intra-run**: al arrancar (o reanudar con `/loop`), lee el issue para saber que slices
  estan `mergeada` (`[x]`) y cual es la siguiente `pendiente`. Una slice en `esperando-merge` se
  retoma ahi.
- **`deploy-watch`** comenta su veredicto del deploy en el issue (no escribe estado local).

Nota: la separacion pura/I/O (parseo y reescritura en `issue_body.py`, I/O en `gh`) permite
testear la logica de estado offline sin mocks de `gh`; el smoke real valida la I/O.

### Metricas durables (fuera del repo)

`~/.claude/slice-runner/metrics.jsonl` es un log **durable** append-only, un registro por slice
cerrada, que **no vive en el repo** (por tanto nunca entra en una PR). Existe para responder con
datos "cuando subir de nivel" sin depender de la intuicion. Lo escribe y lo agrega
`scripts/metrics.py` (`offload-deterministic`): la IA no estima cifras a ojo. Es un rastro de
telemetria distinto del estado del run (que vive en el issue).

    python3 ~/.claude/skills/slice-runner/scripts/metrics.py report [--repo <repo>]

Reporta: tasa de FALLA del verificador, tasa de bloqueo por puertas, % de slices al primer intento,
media de reintentos (implement, puertas y CI por separado), tasa de CI roja, duracion media. Es el
instrumento para el "confianza en el loop" del Step 3 del mapa de madurez. Coste en tokens no se mide
aqui (sale de OTel de Claude Code).

El **veto del juez** (`FALLA`) y el **bloqueo por puertas** (`bloqueada-puertas`) se registran aparte a
proposito: uno es un rechazo semantico y el otro un fallo mecanico, y confundirlos deja inservible el
unico instrumento que hay para calibrar al juez.

`<repo>` debe ser un **identificador estable** del repo (p. ej. el nombre del directorio raiz o el
slug del remoto), el mismo en `record` y en `report --repo`, para que las cifras agrupen bien.

En slices cross-repo (`REPO:`), `--repo` sigue siendo el **repo del issue**, no el destino: agrupa el
run de la feature. Si cada slice se registrara bajo su repo de trabajo, las slices de una misma feature
caerian en cubos distintos y la calibracion del loop dejaria de agregar bien.

## Steps

### 1. Localizar el issue y seleccionar slice

- **Identifica el issue** (numero o URL). Si no se da, lista los issues abiertos del repo
  (`gh issue list`) y pregunta cual; para `/loop`, el numero viaja en el input del loop.
- Lee el cuerpo (`gh issue view <N> --json body`) y parsealo con `issue_body.parse_body`. Si no es
  un checklist de slices valido, para y pide una spec valida (o sugiere `/slice-spec`).
- **Selecciona la slice**: la indicada por el usuario, o la primera `pendiente`. No repitas las
  `mergeada`. Si una slice quedo `esperando-merge`, retomala ahi (paso 10) en vez de reimplementarla.
- **Determina el repo de trabajo**: `slice.repo` (linea `REPO:`) si lo trae, o el repo del issue.
  Si es otro repo, resuelve su **ruta local** y usala en todo lo que sigue (`--repo`, `git -C`, `cwd`);
  si no la encuentras, para y preguntala en vez de adivinarla.
- **Carga la vara de medir del repo de la slice.** Extrae las fuentes con `issue_body.parse_fuentes`
  (y `tiene_seccion_fuentes` para distinguir ausente de vacia) y **filtra con
  `issue_body.fuentes_para(fuentes, slice.repo)`**. Si la seccion **falta o esta vacia**, o si la slice
  declara `REPO:` y **su** subseccion no existe, para y pide anadirla con `slice-spec` (modo `validate`
  sobre este issue): sin vara no se ejecuta, y **no heredes la del repo de la app** para una slice de
  otro repo -es justo la desviacion silenciosa que esta seccion evita-. Estos punteros son la vara que
  cargaran implementador (paso 5) y verificador (paso 7); las skills de proyecto se leen/invocan y se
  citan igual que una regla.
- Extrae titulo, alcance y criterios de aceptacion de la slice. Si no los hay, para y pidelos: sin
  criterios no hay puerta de verificacion.
- **Toma la intencion**, en sus dos niveles: la de la feature (`issue_body.parse_intencion(body)`) y
  la de la slice (`slice.intencion`). Viaja al implementador (paso 5) y al cuerpo de la PR (paso 8).
  Si alguna falta (`None`, `""` o lista vacia), **avisa y sigue**: no bloquea, pero **anota que
  habra que inferirla**, porque el encabezado de la PR tiene que decirlo. Que la ausencia la detecte
  el script y no tu criterio es lo que impide que una PR presente como declarado lo que en realidad
  se invento.
- **Toma la `SENAL`** (`slice.senal`). Si la trae, viaja al implementador (paso 5), al verificador
  (paso 7) y a `deploy-watch` (paso 10). Si **no** la trae, **avisa** de que la spec deberia declararla
  (`slice-spec validate`) y sigue: no bloquea.
- **Toma el `name` de la slice** (entre parentesis tras el id). Si no hay name, deriva un slug del titulo y avisa. La rama es `slice/NN-<name>` (p. ej. `slice/01-cantidad-vo`). Toma tambien el `type` opcional (por defecto `feat`).
- Marca la slice `en-curso` en el issue (`set_slice_estado(..., "en-curso")` -> `gh issue edit --body`).

### 2. Autodetectar comandos del repo (Makefile primero)

Infierelos, no los asumas. Cachea lo detectado en la respuesta. **En el repo de trabajo de la slice**
(paso 1): una slice con `REPO:` se valida con las puertas de **su** repo, no con las de la app.

- **Prioridad 1 — Makefile**: si hay `Makefile`, usa sus targets (`make test`, `make check-types`, `make check-style`/`make linting`, `make fastapi-migrate`, `make env-start`...). En muchos repos todo corre en Docker via `make`; lanzar `pytest`/`ruff`/`mypy` directos fallaria. Lee el Makefile para saber que target cubre cada puerta.
- **Prioridad 2 — pyproject/tox**: si no hay Makefile util, cae a `ruff`, `mypy` (leyendo `[tool.mypy]`), `pytest` (rutas/opts de `pyproject.toml`/`tox.ini`).
- **Workflow de CI**: identifica el workflow de `.github/workflows/*.yml` que corre en `pull_request`.
- Si una puerta no tiene comando claro, pregunta antes de continuar.
- **Repo sin puertas reales** (p. ej. el de paneles de Grafana: la CI solo publica en `master`, no
  valida en PR): no inventes una puerta ni finjas que existe. Declara explicitamente que puertas hay
  (aunque sea solo "el JSON parsea") y tratala como **capa eximida** (delta 1 del paso 5): la
  verificacion real es post-deploy.

Lo detectado se expresa como los `--check nombre=comando` que consumiran `gates.py checks` en los pasos
5 y 6. El script no sabe nada del toolchain: solo ejecuta lo que se le pasa, asi que la autodeteccion
se queda aqui y no se duplica dentro del script.

    --check lint="make linting" --check types="make check-types" --check tests="make test"

### 3. Alinear antes de implementar (check-alignment)

- **Puerta de subagentes (fail-closed, lo primero).** Declara que vas a lanzar **dos** Agent: el
  implementador (paso 5) y el verificador `slice-verifier` (paso 7). Invocar esta skill cuenta como que
  el usuario los pide, asi que no preguntes permiso. Pero si **no puedes** lanzarlos -veto global al
  Agent tool, politica de la organizacion, `slice-verifier` sin resolver por symlink ausente-: marca la
  slice `bloqueada: sin-subagentes` en el issue, explica cual es la restriccion concreta y **para
  aqui**, sin escribir codigo. No ofrezcas hacerlo inline: la verificacion inline es el fallo que esta
  skill previene, y una PR con verificacion de teatro es peor que ninguna PR. Que el usuario decida si
  levanta la restriccion o renuncia al run.
- Resume: slice elegida (id + `name`), **repo de trabajo** (y su ruta local, si no es el del issue),
  los criterios de aceptacion, **`SENAL` y que hara con ella** (apunta a una serie que ya existe /
  hay que instrumentarla y como / exenta), capa(s) afectada(s), comando de validacion que aplicara,
  `type(name)` de conventional commit que usara el commit/PR, y como piensa abordarla.
- Si el cambio claramente **no es un `feat`** (p. ej. refactor o fix) y la spec no declaro type, confirma el type con el usuario aqui (barato; evita un scope de commit erroneo).
- Si la spec pre-hornea codigo, contrastalo contra las fuentes de convencion del issue (paso 1) y **senala cualquier violacion antes de escribir** (no lo transcribas a ciegas).
- Espera go/no-go del usuario. Esto evita `silent-misalignment` y `ai-slop`.

### 4. Preparar rama de trabajo

- **En el repo de trabajo de la slice** (paso 1). Si es otro repo, comprueba que esta limpio y
  actualizado antes de ramificar; nunca arrastres cambios sueltos de otro trabajo.
- **Por defecto, rama normal**: `git switch -c slice/NN-slug` desde la rama base actualizada. No asumas worktree: no todos los repos tienen config de worktrees, y una slice por invocacion no colisiona con nada.
- **Worktree solo si aplica**: usa un git worktree aislado unicamente si se van a paralelizar varias slices concurrentes (Nivel 2) o si el repo ya declara config de worktrees. En ese caso crea el worktree desde la base actualizada con la rama `slice/NN-slug`.

### 5. Implementar (subagente implementador)

Lanza un Agent (`subagent_type: general-purpose`) con instrucciones. Se usa `general-purpose` a
proposito: hereda el modelo fuerte de la sesion, tiene `Bash`, y no arrastra la metodologia de ningun
agente prestado; todo el criterio se lo da este prompt, subordinado a las convenciones del repo.

- Cargar las **fuentes de convencion del repo de la slice** (paso 1: docs y skills de proyecto, ya
  filtradas por `fuentes_para`) y respetarlas como vara de medir; cargar tambien la skill
  `backend-best-practices` cuando el repo destino sea un backend Python (en un repo de manifiestos o de
  dashboards no aplica: manda su propia convencion). En conflicto, ganan las convenciones del repo.
- Trabajar **en la ruta del repo de la slice**, no en el repo del issue si son distintos.
- **Darle la intencion de la slice** (paso 1) junto a los criterios de aceptacion: los criterios
  dicen que tiene que cumplirse, la intencion dice **para que**, y sin ella es facil entregar la
  solucion tecnicamente correcta y funcionalmente inutil. No es licencia para ampliar el alcance: si
  la intencion pide mas que los criterios, eso se reporta, no se implementa de mas.
- **El ciclo TDD: invoca `superpowers:test-driven-development`** y siguelo (RED -> verificar que
  falla por el motivo esperado -> GREEN minimo -> REFACTOR), incluida su referencia
  `writing-good-tests.md`. No se resume aqui: fuente unica, para que no se desincronice.
  **Precedencia si algo choca**: convenciones del repo > exencion de capa (delta 1) > Iron Law de
  superpowers.
- **Delta 1 - exencion de capa.** En capas que la convencion del repo no testea por separado (p. ej.
  modelos ORM y migraciones alembic), la Iron Law de superpowers **no** aplica: no fuerces
  test-first; la puerta es "suite intacta + verificacion del efecto" (p. ej. el `SELECT` que exige el
  plan). En capas con test (dominio/aplicacion/API...) aplica el ciclo completo, un test por criterio.
- **Delta 2 - integridad de tests preexistentes (regla de hierro).** Superpowers dice "test falla ->
  arregla el codigo, no el test"; aqui se concreta: nunca modifiques un test **que ya existia** para
  que pase -no debilites asserts, no lo borres, no lo marques `@skip`/`xfail`-. Si no puedes
  satisfacer un test, revierte al ultimo verde y para/escala; adaptar el test al codigo destruye la
  red de seguridad en silencio y es la peor patologia posible. (El verificador lo caza en el paso 7;
  aqui se evita en origen.)
- **Delta 3 - refactor tras cada verde**, no diferido a una pasada final: en cuanto los tests pasan,
  pasada de refactor (eliminar duplicacion, mejorar nombres y estructura) manteniendo el verde. La
  evidencia empirica senala el refactor tras verde -no el orden test-first- como el verdadero driver
  de calidad y mantenibilidad en agentes.
- **Delta 4 - el esfuerzo va al test.** Los tests son ciudadanos de primera categoria (ver
  principios): gasta el presupuesto de calidad en que cada test **fije de verdad su criterio**, no en
  ponerlo verde. Antes de escribir un test, nombra el cambio de produccion que lo haria fallar; si no
  sabes nombrarlo, el test no esta testeando lo que la slice pretende construir.
- **Delta 5 - la senal se construye aqui, si falta.** Si la slice trae `SENAL:` (no exenta), carga
  `~/.claude/skills/slice-spec/references/observabilidad.md` y **baja su escalera**: si la serie ya la
  emite la libreria de monitoring del repo, no anadas nada -la senal ya existe-; si hay que enriquecer
  (atributo de log, span, label), hazlo con la libreria; si hace falta metrica de negocio nueva,
  instrumentala **con la libreria** (puerto inyectado por DI, nunca instanciada dentro del dominio) y
  escribe su **test de emision** con el doble in-memory que la libreria provee. Si la libreria no lo
  expresa idiomaticamente, **para y reportalo como gap** en vez de montar un contador ad-hoc en
  paralelo: la duplicacion del mecanismo se hereda, el gap se arregla una vez. Cuidado con la
  cardinalidad: ids, emails y uuids van al log o al span, jamas como label de metrica.
- No sobredimensionar: lo minimo para los criterios de aceptacion. Nada de andamiaje de slices futuras.
- **No tocar el issue ni artefactos.** Solo ficheros de codigo/test de la slice. No escribas planes
  ni design-docs, ni edites el issue: el estado del issue lo gestiona el orquestador, no la PR.
- **Auto-check de wiring antes de entregar.** Corre `git diff --name-only` y confirma que los ficheros
  de **produccion** que la slice debia tocar aparecen en el diff, no solo tests: si la suite pasa a
  verde sin tocar produccion, el efecto lo esta produciendo el test/fixture y no el codigo. En slices
  sin codigo de produccion (migracion/infra) no aplica. (El verificador lo cruza en el paso 7.)
- **Puertas verdes antes de entregar (`[det]`).** No entregues con lint, tipos o tests en rojo: corre

      python3 ~/.claude/skills/slice-runner/scripts/gates.py checks --repo <repo-de-la-slice> \
        --check lint="<cmd>" --check types="<cmd>" --check tests="<cmd>" --json

  con los comandos del paso 2, y arregla hasta exit 0. Es feedback incremental mientras trabajas, no un
  informe final: el script devuelve solo exit code y salida truncada, asi que el error llega acotado y
  no te inunda el contexto. El orquestador lo re-ejecuta despues (paso 6), asi que entregar en rojo solo
  te cuesta una vuelta.
- Devolver: **la lista explicita de rutas creadas o modificadas, marcando cada una como produccion o
  test** (es lo que se stageara en el paso 8 y lo que el verificador usa para el check de wiring; nada
  mas), tests anadidos (si aplica) y resumen del enfoque.

### 6. Puertas deterministas (backstop del orquestador)

Antes de invocar al verificador, **re-ejecuta tu mismo** las puertas con los comandos del paso 2:

    python3 ~/.claude/skills/slice-runner/scripts/gates.py checks --repo <repo-de-la-slice> \
      --check lint="<cmd>" --check types="<cmd>" --check tests="<cmd>" --json

El implementador ya las corrio (paso 5), pero **su auto-reporte no es fuente de verdad**: es la misma
razon por la que el verificador no se cree su resumen del enfoque. Aqui la garantia la da el harness, no
la buena voluntad del agente. Exit 0 = puedes invocar al verificador.

- **Verde**: pasa al paso 7.
- **Rojo**: vuelve al paso 5 con **solo los checks en FALLA y su `salida`** del JSON. No invoques al
  verificador: un fallo mecanico no se juzga, se arregla. **Presupuesto propio: 2 reintentos**,
  separado del del verificador.
- **Si agota los reintentos**: marca la slice `bloqueada: puertas` en el issue, **registra la metrica
  durable** (`veredicto=bloqueada-puertas`, `ci=none`, `--reintentos-puertas N`; ver paso 9) y **para**.
  No se abre PR con puertas en rojo.

No leas ni pegues el output crudo de las puertas en ningun sitio: el script ya devuelve exit code y
salida truncada, y eso es todo lo que hay que propagar.

### 7. Verificar (agente `slice-verifier`, adversarial)

Lanza un Agent con `subagent_type: slice-verifier`. Es un **agente definido**
(`~/.claude/agents/slice-verifier.md`, symlink a `agents/slice-verifier.md` de este repo), no
`general-purpose`, por dos razones:

- **La rubrica va en su system prompt**, verbatim en cada invocacion, en vez de que tu la relates y
  puedas parafrasearla o saltarte items. La parte mas importante del loop no debe depender de una
  transcripcion.
- **No tiene `Bash`** (`tools: Read, Grep, Glob, Skill`): no puede ejecutar puertas aunque quisiera. La
  restriccion es **estructural**, por ausencia de la tool. No basta con `allowed-tools`: el smoke del
  2026-07-27 comprobo que un `allowed-tools` en el frontmatter **no bloquea** lo no listado (el agente
  ejecuto `ls`, ausente de su lista, sin friccion), asi que la unica forma de que sea enforcement y no
  cumplimiento es no darle la tool. `model: inherit` conserva el modelo fuerte de la sesion, que el
  juicio mas sutil -el patron de rollout- requiere.

**Antes de invocarlo, materializa el diff (`[det]`).** Como no tiene `Bash`, no puede calcularlo:

    python3 ~/.claude/skills/slice-runner/scripts/gates.py diff-bundle --repo <repo-de-la-slice> \
      --base <base> --out <dir-fuera-del-repo> --json

Escribe `slice.diff` (rango `<base>...HEAD`) y `files.txt`, y devuelve sus rutas. El `--out` va **fuera
del repo** (p. ej. bajo `/tmp`): un fichero de trabajo dentro nunca debe poder acabar en la PR. El rango
lo fija el script -tres puntos, desde el branch-point- y no tu criterio: con `..`, los commits que la
base haya avanzado desde entonces saldrian como borrados y el verificador cazaria violaciones fantasma.
Si devuelve FALLA (base inexistente, o cero cambios), arreglalo antes de invocar: sin diff no hay nada
que verificar.

**No le pases nada de las puertas**: cuando llega aqui estan verdes por construccion (paso 6), asi que
un resumen seria cero informacion y solo gastaria contexto. Tampoco le pases el "resumen del enfoque"
del implementador: juzga el diff, no la narrativa.

**Divergencia deliberada de `superpowers:requesting-code-review` (no es un olvido).** Esta skill delega
en superpowers el ciclo TDD (paso 5) pero **a proposito no usa** su skill de code review, que si
re-revisa el codigo: aqui el segundo par de ojos se gasta en la vara de medir del repo. El argumento
completo esta en `agents/slice-verifier.md`; no sustituyas ese agente por `requesting-code-review`.

**Inputs de la invocacion** (lo del run; lo estable ya esta en el agente):

- numero de issue, `slice_id` y `name`;
- los **criterios de aceptacion** de la slice, tal cual estan en el issue;
- la **`SENAL`** de la slice, tal cual esta en el issue (o que esta exenta, con su motivo, o que la
  spec no la declara);
- las **fuentes de convencion del repo de la slice** (paso 1, ya filtradas por `fuentes_para`), y el
  repo destino si no es el del issue;
- las **rutas de `slice.diff` y `files.txt`** que devolvio `diff-bundle`;
- la **ruta del repo**, para que lea el codigo alrededor del diff;
- la **lista etiquetada produccion/test** que devolvio el implementador (paso 5).

**Veredicto.** Devuelve como mensaje final exactamente este objeto JSON (lo exige su system prompt; la
tool `Agent` no valida schemas, asi que si vuelve envuelto en prosa, es un fallo del agente y se
reintenta la invocacion, no se parsea a mano):

```json
{
  "veredicto": "PASA | FALLA",
  "hallazgos": [
    {"regla": "boundaries", "path": "src/infra/x.py", "linea": 42,
     "severidad": "alta | media | baja", "evidencia": "...", "detalle": "..."}
  ]
}
```

- **FALLA** si hay algun hallazgo `severidad: alta` (los `media`/`baja` no bloquean por si solos, pero
  el agente puede escalar si se acumulan, explicando por que). Las puertas ya no entran en esta regla:
  se decidieron en el paso 6.
- Si FALLA: devuelve al paso 5 con los `hallazgos` (max 2 reintentos, presupuesto propio del
  verificador). Guarda el conteo de hallazgos por severidad y el veredicto final: alimentan las metricas.
- **Si agota los reintentos con FALLA**: marca la slice `bloqueada: verify` en el issue, **registra la
  metrica durable** (`veredicto=FALLA`, `ci=none`; ver paso 9) y **para**. No sigas al paso 8: sin PASA
  del verificador no se abre PR. Sin esto, el rechazo del verificador -justo lo que queremos medir- no
  dejaria rastro.

### 8. Abrir PR

- **Stagea SOLO los ficheros de codigo/test que devolvio el implementador.** Usa
  `git add <ruta1> <ruta2> ...` con la lista explicita; **prohibido `git add -A`, `git add .`
  o `git commit -a`**. Planes y design-docs NO entran en la PR (la spec vive en el issue, no como
  fichero).
- **Puerta determinista de higiene (`[det]`).** Tras stagear, corre
  `python3 ~/.claude/skills/slice-runner/scripts/gates.py pr-hygiene --repo <repo-de-la-slice> --allow <ruta1> --allow <ruta2> ...`
  con la lista exacta que devolvio el implementador. Exit 0 = PASA. Si FALLA (algo staged fuera de
  lo declarado, o un artefacto: plan, design-doc), **corrige el staging** (`git restore --staged`) y
  reintenta; no lo re-interpretes a ojo. No commitees hasta PASA.
- **Conventional commit.** Mensaje y titulo de PR = `type(name): resumen`, con el `type` (por
  defecto `feat`) y el `name` de la slice como scope: p. ej. `feat(cantidad-vo): add Cantidad value
  object`. Redactar un conventional commit lo haces bien sin puerta; lo unico determinista aqui es
  que el `name` (scope) viene de la spec (issue), no de un slug inventado. Cuerpo del commit opcional
  con detalle. Nunca commitees en `master`/`main`. Push de la rama `slice/NN-<name>`.
- `gh pr create --draft` **en el repo de la slice** (`--repo <org>/<repo>` o desde su ruta) con titulo
  `type(name): resumen` y este cuerpo, en este orden:

      ## Intencion
      <la INTENCION de la slice, encuadrada en una frase de la del issue: que estaba mal
      hoy y deja de estarlo cuando esto entra>

      ## Criterios de aceptacion cumplidos
      - <un criterio por linea, con donde vive su test>

      ## Senal a comprobar tras el despliegue
      <la linea SENAL de la slice, o "exenta - <motivo>">

      Part of #<N>

  Reglas del cuerpo:

  - **Nada de enumerar ficheros, clases ni modulos, ni de narrar el diff**: eso ya lo cuenta GitHub
    mejor que tu, y en su sitio. Lo que un revisor no puede deducir del diff es **por que**, y ese es
    todo el trabajo de este cuerpo.
  - **Si la intencion no venia declarada en el issue** (paso 1), el encabezado lo dice:
    `## Intencion (inferida del issue, no declarada)`. Nunca la presentes como declarada.
  - **`Part of #<N>`**, no `Closes`: una PR es una slice, no la feature entera. Si la slice vive en otro
    repo, la forma cross-repo `Part of <org>/<repo-del-issue>#<N>`, que GitHub enlaza igual.

  **La PR se abre siempre en draft**: la CI corre igual, pero deja explicito que esta pendiente de tu
  revision y no lista para mergear (refuerza que el merge es humano). Sacarla de draft
  (`ready for review`) y mergear lo decides tu.
- Actualiza la linea de la slice en el issue con la PR: `set_slice_estado(..., "en-curso", pr=<M>)`
  -> `gh issue edit` (el estado pasara a `esperando-merge` en el paso 9 al haber CI verde).
- No marcar como ready-to-merge automaticamente mas alla de lo normal; el merge es humano.

### 9. Esperar CI verde (puerta final)

- Espera hasta verde o rojo con **ticks acotados en background + notificacion** (o la herramienta `Monitor`), **nunca** `gh pr checks --watch` ni un `sleep` largo que bloquee la shell/sesion (principio de esperas no bloqueantes; es trabajo deterministico que hace el harness, no la IA poll-eando). Cada tick consulta `gh pr checks --json` y devuelve el control. Respeta un timeout de espera razonable.
- **Verde**: **registra la metrica durable** (ver abajo, `ci=green`), marca la slice `esperando-merge` en el issue (aun **no** `[x]`: el merge es humano; ver paso 10) y **pasa al paso 10** (no paras aqui).
- **Rojo**: trae los logs del check fallido (`gh run view --log-failed`), un reintento via paso 5 con esos logs.
  - Si tras el reintento sigue roja: marca la slice `bloqueada: ci-roja` en el issue, **registra la metrica durable** (`ci=red`), **deja el PR abierto**, resume el fallo con logs y **para** (circuit breaker). No cierres el PR ni descartes la rama/worktree.
- Si en cualquier momento se supera el presupuesto de tokens/$ de la slice: marca la slice `abortada: presupuesto` en el issue, **registra la metrica durable** (`veredicto=abortada-presupuesto`) y para.

**Registro de la metrica durable (`[det]`).** Al cerrar la slice, en **cualquiera** de los caminos de cierre (puertas agotadas del paso 6, verify terminal FALLA del paso 7, CI verde, CI roja terminal, o presupuesto), anexa un registro con:

```
python3 ~/.claude/skills/slice-runner/scripts/metrics.py record --repo <repo> --slice <slice_id> --name <name> \
  --veredicto <PASA|FALLA|bloqueada-puertas|abortada-presupuesto> --ci <green|red|none> \
  --hallazgos-alta N --hallazgos-media N --hallazgos-baja N \
  --reintentos-implement N --reintentos-puertas N --reintentos-ci N --duracion-s N
```

- `veredicto` = el del verificador del paso 7 (`PASA`/`FALLA`), `bloqueada-puertas` si paro en el backstop del paso 6, o `abortada-presupuesto` si paro el presupuesto. Los conteos de `hallazgos` salen del veredicto estructurado del paso 7 (en `bloqueada-puertas` son 0: no hubo juicio semantico). **No uses `FALLA` para un fallo de puertas**: es un fallo mecanico, no un veto del juez, y confundirlos deja inservible la calibracion del verificador.
- Este log vive **fuera del repo** (`~/.claude/slice-runner/metrics.jsonl`) y **nunca entra en una PR**. Coste en tokens: opcional (`--coste-tokens`); si no lo tienes de OTel, no lo inventes (se omite).

### 10. Esperar el merge y encadenar el deploy

El merge sigue siendo **humano** (lo haces tu en GitHub); lo que se automatiza es la **transicion**, para que no tengas que decir "continua" a mano.

- La slice ya figura `esperando-merge` en el issue (paso 9): eso comunica **esperando una decision tuya**, no parada.
- Vigila el estado de la PR con **ticks acotados en background + notificacion** (`gh pr view --json state,mergedAt`), nunca una shell bloqueante larga. Respeta un timeout razonable de espera de merge.
  - **Merged**: marca la slice `mergeada` (`[x]`) en el issue e invoca automaticamente la skill
    `deploy-watch` (sin pedir "continua"), **pasandole la `SENAL` de la slice** (y el repo destino si no
    es el del issue): es lo que le permite comprobar *este* cambio y no solo la salud generica del
    servicio. Si la slice no declaraba senal, dilo al invocarla, para que su veredicto lo declare.
    `deploy-watch` arranca sola e infiere servicio/namespace; solo te preguntara si la inferencia es
    ambigua (`check-alignment` solo cuando hay duda real).
  - **Timeout / cerrada sin merge**: deja la slice `esperando-merge` (o `bloqueada` si se cerro sin merge) en el issue y **para**, dejando el PR como este. Reanudas invocando de nuevo cuando quieras.

## Fin

Al parar (o al ceder el control a `deploy-watch`), reporta siempre: slice ejecutada (y **en que repo**,
si no es el del issue), estado (mergeada / esperando-merge / bloqueada / abortada), URL del PR,
resultado de CI, **la `SENAL` que queda por comprobar en prod** (o que la slice no declaraba ninguna),
coste de la slice, y siguiente slice pendiente (del issue). Si quedan slices pendientes, sugiere volver a invocar (o
envolver en `/loop` para Nivel 2).

### Cierre del run (todas las slices mergeadas)

Cuando **no quedan slices pendientes** (todas `[x] mergeada` en el issue), el run ha terminado:

- Comenta en el issue que todas las slices estan mergeadas, con el resumen.
- **Deja el cierre del issue al humano** (control humano en el hito; ademas el issue es el registro
  duradero, cerrarlo no lo borra).
- **No toques `~/.claude/slice-runner/metrics.jsonl`**: es durable, vive fuera del repo y es justo
  lo que debe sobrevivir para medir la evolucion del loop.
- No hay estado local que descartar: no existe `.slice-runner/`.
