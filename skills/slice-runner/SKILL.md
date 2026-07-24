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
- **Las convenciones del repo mandan.** Implementador y verificador cargan como vara de medir las **fuentes de convencion declaradas en el issue** (seccion `## Fuentes de convencion`: docs y skills de proyecto), por encima de cualquier default generico de hexagonal/DDD. En conflicto, ganan las convenciones del repo. No se asumen rutas fijas: las fuentes se descubren por repo y las declara `slice-spec` en el issue; `slice-runner` solo las lee. Si el issue no trae esa seccion, **para** y pide anadirla con `slice-spec` (no ejecutes con la vara vacia: fue la causa raiz de desviaciones silenciosas de convencion). Sin la vara, el verificador no puede cazar violaciones reales (p. ej. una migracion que siembra datos donde la convencion lo prohibe).
- **Puertas de parada objetivas.** No hay PR mergeable sin lint limpio, tipos limpios, tests verdes y **CI verde**, ejecutados con los comandos reales del repo (paso 2), no con binarios asumidos.
- **Determinista lo que es regla exacta (`offload-deterministic`).** Lo que se puede comprobar con una regla mecanica (higiene del diff staged) NO se delega al juicio del verificador: lo resuelve el script `scripts/gates.py`, cuyo exit code es autoritativo. El verificador gasta su presupuesto solo en lo semantico: convenciones y arquitectura del repo. No se pide dos veces a la IA lo que un script decide una vez.
- **TDD consciente de capa.** Por defecto TDD estricto: test rojo por cada AC antes del codigo, y el verificador comprueba que el test precede a la implementacion. Pero si las convenciones del repo eximen una capa (p. ej. modelos ORM y migraciones que no se testean por separado), la puerta para esa slice es "suite intacta + verificacion de datos/efecto", no test-first por AC. La convencion del repo decide, no este documento.
- **Alinear antes de implementar.** Antes de escribir codigo, mostrar el entendimiento de la slice (alcance, AC, capa afectada, comando de validacion) y esperar go/no-go. Nunca transcribir a ciegas el codigo pre-horneado de una spec: validalo contra las convenciones primero.
- **Seguir `backend-best-practices`.** El implementador carga esa skill y respeta hexagonal/DDD, DI, Pydantic en boundaries, subordinada siempre a las convenciones del repo.
- **El estado del run vive en el issue de GitHub.** La spec y el estado de cada slice viven en el cuerpo de un issue de GitHub (una feature = un issue): es la **unica fuente de verdad**, viva y duradera. No hay estado local (`.slice-runner/`, ledger ni panel). El agente olvida entre slices; al arrancar re-lee el issue. Registro duradero = issue (intencion + estado) + PRs mergeadas (codigo).
- **La PR solo lleva el codigo de la slice.** El commit stagea unicamente los ficheros de codigo/test que produjo el implementador (`git add` explicito, nunca `-A`/`.`). Planes y design-docs jamas entran en la PR (la spec ya no es un fichero: vive en el issue).
- **Contexto fresco por slice.** Cada slice arranca sin arrastrar la conversacion de la anterior; lo que persiste entre slices es el **issue** (spec + estado), que se re-lee al empezar. Evita la degradacion de contexto (patron Ralph) y hace seguro el Nivel 2 (`/loop`).
- **Circuit breaker.** Maximo 2 reintentos por fase. Ademas, **presupuesto de coste**: si la slice supera el limite de tokens/$ configurado, para con estado `abortada-presupuesto`. Si la CI sigue roja tras el reintento, para, deja el PR abierto y reporta con logs.
- **Esperas no bloqueantes.** Prohibido lanzar shells bloqueantes largas para esperar (nada de `gh pr checks --watch`, `sleep` largos, ni polls que se queden colgados 30-60 min). Toda espera (CI verde, merge de la PR) se hace con **ticks acotados en background + notificacion** (o la herramienta `Monitor`), devolviendo el control entre ticks. Una espera nunca debe monopolizar una shell ni la sesion.
- **No asumir worktree.** Por defecto se trabaja en una rama normal. Solo se usa un git worktree aislado si se van a paralelizar varias slices concurrentes (Nivel 2) o si el repo ya declara config de worktrees.

## Formato de spec (cuerpo del issue)

La spec vive en el **cuerpo de un issue de GitHub** (una feature = un issue). Es un **checklist de
slices**: cada slice es una linea de task-list con **nombre**, AC embebidos y un **marcador de
estado**. Si el issue no encaja en este formato, para y pide una spec valida (o sugiere
`/slice-spec` para generarla).

```markdown
## Fuentes de convencion
- doc: .claude/CLAUDE.md
- skill: .claude/skills/duplicate-action

## Slices
- [x] slice-01 (cantidad-vo): Crear value object `Cantidad` [mergeada] PR #11
      AC: rechaza negativos; tests en test/domain/test_cantidad.py
- [ ] slice-02 (ajustar-stock): Caso de uso `AjustarStock` [esperando-merge] PR #12
      AC: emite evento StockAjustado; no toca infra directamente
- [ ] slice-03 (extraer-repo): Extraer repositorio [pendiente]
      AC: ...
```

La seccion `## Fuentes de convencion` (punteros a la vara de medir del repo) la declara
`slice-spec`; `slice-runner` la exige y para si falta (paso 1). Unidad de trabajo = cada item
`- [ ] slice-NN ...`. Una feature de una sola slice es un checklist
con una unica linea. El parseo y la reescritura de estas lineas los hace la logica pura de
`scripts/issue_body.py` (`offload-deterministic`); la I/O contra el issue es `gh`.

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

### Estado de cada slice (marcador en su linea)

El estado se codifica en la linea con `[estado]` (y `PR #N` cuando aplica):

- `pendiente` — aun no empezada.
- `en-curso` — implementando/verificando.
- `esperando-merge` — PR abierta, CI verde, esperando la decision humana de merge.
- `mergeada` — PR mergeada. **Es el unico estado que marca el checkbox `[x]`.**
- `bloqueada: <motivo>` — CI roja no resuelta o verify terminal; deja el PR abierto.
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
  `gh issue edit --body`). No toca las demas lineas ni los AC.
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

Reporta: tasa de FALLA del verificador, % de slices al primer intento, media de reintentos,
tasa de CI roja, duracion media. Es el instrumento para el "confianza en el loop" del Step 3 del
mapa de madurez. Coste en tokens no se mide aqui (sale de OTel de Claude Code).

`<repo>` debe ser un **identificador estable** del repo (p. ej. el nombre del directorio raiz o el
slug del remoto), el mismo en `record` y en `report --repo`, para que las cifras agrupen bien.

## Steps

### 1. Localizar el issue y seleccionar slice

- **Identifica el issue** (numero o URL). Si no se da, lista los issues abiertos del repo
  (`gh issue list`) y pregunta cual; para `/loop`, el numero viaja en el input del loop.
- Lee el cuerpo (`gh issue view <N> --json body`) y parsealo con `issue_body.parse_body`. Si no es
  un checklist de slices valido, para y pide una spec valida (o sugiere `/slice-spec`).
- **Carga la vara de medir del issue.** Extrae las fuentes de convencion con
  `issue_body.parse_fuentes` (y `issue_body.tiene_seccion_fuentes` para distinguir ausente de vacia).
  Si la seccion `## Fuentes de convencion` **falta o esta vacia**, para y pide anadirla con
  `slice-spec` (modo `validate` sobre este issue): sin vara no se ejecuta. Con la seccion presente,
  estos punteros (docs y skills de proyecto) son la vara que cargaran implementador (paso 5) y
  verificador (paso 6); las skills de proyecto se leen/invocan y se citan igual que una regla.
- **Selecciona la slice**: la indicada por el usuario, o la primera `pendiente`. No repitas las
  `mergeada`. Si una slice quedo `esperando-merge`, retomala ahi (paso 9) en vez de reimplementarla.
- Extrae titulo, alcance y AC de la slice. Si no hay AC, para y pidelos: sin AC no hay puerta de verificacion.
- **Toma el `name` de la slice** (entre parentesis tras el id). Si no hay name, deriva un slug del titulo y avisa. La rama es `slice/NN-<name>` (p. ej. `slice/01-cantidad-vo`). Toma tambien el `type` opcional (por defecto `feat`).
- Marca la slice `en-curso` en el issue (`set_slice_estado(..., "en-curso")` -> `gh issue edit --body`).

### 2. Autodetectar comandos del repo (Makefile primero)

Infierelos, no los asumas. Cachea lo detectado en la respuesta.

- **Prioridad 1 — Makefile**: si hay `Makefile`, usa sus targets (`make test`, `make check-types`, `make check-style`/`make linting`, `make fastapi-migrate`, `make env-start`...). En muchos repos todo corre en Docker via `make`; lanzar `pytest`/`ruff`/`mypy` directos fallaria. Lee el Makefile para saber que target cubre cada puerta.
- **Prioridad 2 — pyproject/tox**: si no hay Makefile util, cae a `ruff`, `mypy` (leyendo `[tool.mypy]`), `pytest` (rutas/opts de `pyproject.toml`/`tox.ini`).
- **Workflow de CI**: identifica el workflow de `.github/workflows/*.yml` que corre en `pull_request`.
- Si una puerta no tiene comando claro, pregunta antes de continuar.

### 3. Alinear antes de implementar (check-alignment)

- Resume: slice elegida (id + `name`), AC, capa(s) afectada(s), comando de validacion que aplicara, `type(name)` de conventional commit que usara el commit/PR, y como piensa abordarla.
- Si el cambio claramente **no es un `feat`** (p. ej. refactor o fix) y la spec no declaro type, confirma el type con el usuario aqui (barato; evita un scope de commit erroneo).
- Si la spec pre-hornea codigo, contrastalo contra las fuentes de convencion del issue (paso 1) y **senala cualquier violacion antes de escribir** (no lo transcribas a ciegas).
- Espera go/no-go del usuario. Esto evita `silent-misalignment` y `ai-slop`.

### 4. Preparar rama de trabajo

- **Por defecto, rama normal**: `git switch -c slice/NN-slug` desde la rama base actualizada. No asumas worktree: no todos los repos tienen config de worktrees, y una slice por invocacion no colisiona con nada.
- **Worktree solo si aplica**: usa un git worktree aislado unicamente si se van a paralelizar varias slices concurrentes (Nivel 2) o si el repo ya declara config de worktrees. En ese caso crea el worktree desde la base actualizada con la rama `slice/NN-slug`.

### 5. Implementar (subagente implementador)

Lanza un Agent (`subagent_type: general-purpose`) con instrucciones. Se usa `general-purpose` a
proposito: hereda el modelo fuerte de la sesion, tiene `Bash`, y no arrastra la metodologia de ningun
agente prestado; todo el criterio se lo da este prompt, subordinado a las convenciones del repo.

- Cargar las **fuentes de convencion declaradas en el issue** (paso 1: docs y skills de proyecto) y respetarlas como vara de medir; cargar tambien la skill `backend-best-practices`. En conflicto, ganan las convenciones del repo.
- **TDD segun la capa**:
  - Capas con test (dominio/aplicacion/API...): escribir primero el/los test(s) que codifican los AC, verlos fallar, luego el codigo minimo.
  - Capas eximidas por la convencion del repo (p. ej. modelos ORM y migraciones alembic que no se testean por separado): no forzar test-first; la validacion es "suite intacta + verificacion del efecto" (p. ej. el `SELECT` que exige el plan).
- **Integridad de tests (regla de hierro).** Nunca modifiques un test existente para que pase: no
  debilites asserts, no lo borres, no lo marques `@skip`/`xfail`. Si no puedes satisfacer un test,
  revierte al ultimo verde y para/escala; adaptar el test al codigo destruye la red de seguridad en
  silencio y es la peor patologia posible. (El verificador lo caza en el paso 6, V1; aqui se evita en origen.)
- **Refactor tras cada verde.** Una vez los tests pasan, hacer una pasada de refactor (eliminar duplicacion, mejorar nombres y estructura) manteniendo el verde, antes de entregar. La evidencia empirica senala el refactor tras verde -no el orden test-first- como el verdadero driver de calidad y mantenibilidad en agentes; no lo difieras a una pasada final.
- No sobredimensionar: lo minimo para los AC. Nada de andamiaje de slices futuras.
- **No tocar el issue ni artefactos.** Solo ficheros de codigo/test de la slice. No escribas planes
  ni design-docs, ni edites el issue: el estado del issue lo gestiona el orquestador, no la PR.
- **Auto-check de wiring antes de entregar.** Corre `git diff --name-only` y confirma que los ficheros
  de **produccion** que la slice debia tocar aparecen en el diff, no solo tests: si la suite pasa a
  verde sin tocar produccion, el efecto lo esta produciendo el test/fixture y no el codigo. En slices
  sin codigo de produccion (migracion/infra) no aplica. (El verificador lo cruza en el paso 6, V2.)
- Devolver: **la lista explicita de rutas creadas o modificadas, marcando cada una como produccion o
  test** (es lo que se stageara en el paso 7 y lo que el verificador usa para el check de wiring; nada
  mas), tests anadidos (si aplica) y resumen del enfoque.

### 6. Verificar (subagente verificador, distinto)

Lanza un Agent **diferente** (`subagent_type: general-purpose`), adversarial. Se usa `general-purpose`
a proposito: hereda el modelo fuerte de la sesion (el juicio semantico mas sutil -el patron de rollout-
lo requiere) y tiene `Bash`, asi que ejecuta el mismo las puertas `[det]`. No recibe el "resumen del
enfoque" del implementador como verdad: juzga el diff, no la narrativa.

**Su valor es la revision de convenciones y arquitectura, no re-testear.** La correccion del comportamiento la gobiernan CI + los AC; duplicar esa validacion con un segundo agente que **re-deriva coberturas** sale caro y no aporta (evidencia empirica sobre split authorship). Por eso el verificador **ejecuta** las puertas deterministas pero concentra su **juicio** en convenciones, boundaries y constraints. Matiz importante: "no re-testear" = no re-derivar ni reimplementar cobertura; **si** entra comprobar, por lectura, que los tests que codifican los AC realmente los fijan (que no sean un proxy debil). Eso es barato y es justo donde el segundo par de ojos aporta -cazar un AC mal traducido, no re-verificar comportamiento ya correcto-.

Recorre esta **rubrica cerrada** entera y reporta item a item. Cada item esta marcado `[det]` (lo resuelve un script y solo consumes su resultado) o `[sem]` (lo juzgas tu):

- `[det]` **Puertas objetivas**: ejecutar lint, tipos y tests con los comandos del paso 2 (Makefile primero) y capturar output. Es ejecucion, no re-derivacion: no reimplementes ni reinventes coberturas de test. El exit code manda.
- `[sem]` **Convenciones y arquitectura**: cargar las **fuentes de convencion declaradas en el issue** (paso 1: docs y skills de proyecto) como vara de medir principal y **contrastar el diff contra ellas**, citando regla/skill + path en cada hallazgo (esto es lo que caza cosas como una migracion que siembra datos donde la convencion lo prohibe). Cargar tambien `backend-best-practices` como vara secundaria para lo que las convenciones no cubren. En conflicto, ganan las convenciones del repo.
- `[sem]` **Patron de rollout/entrega correcto (no solo bien implementado).** Caso concreto del check de convenciones anterior, resaltado aparte por ser un fallo recurrente. No basta con que el patron elegido este bien ejecutado y sea coherente consigo mismo: comprueba que **es el patron que la convencion del repo prescribe para este tipo de cambio**. Disparador general: si el cambio toca la **firma/constructor/contrato publico** de una accion o caso de uso, la convencion suele exigir un patron distinto (duplicar la accion / expand-contract) que si solo cambia logica interna (gatear en el metodo). Deriva el criterio de las fuentes de convencion del issue (paso 1: docs y skills de proyecto, p. ej. una skill `duplicate-action`/`deprecate-*` o reglas de delivery/testing), **no** de como quedo una slice anterior: el codigo ya mergeado es circunstancia, no regla. Si el patron elegido no encaja con lo que pide la convencion para este cambio, es **FALLA (severidad alta)**, citando regla + path. Este es el check que un verificador que solo mira la implementacion deja pasar.
- `[sem]` **Boundaries**: nucleo sin infra, DI correcta, DTOs (Pydantic) en boundaries.
- `[sem]` **TDD consciente de capa** (comprobacion barata, no re-testeo): en capas con test, que exista un test por AC y que preceda a la implementacion; en capas eximidas, "suite intacta + efecto verificado".
- `[sem]` **Conformidad con los AC (no solo que existan tests).** Distinto del punto anterior (que comprueba que *hay* un test por AC) y de test-desiderata (que juzga la calidad *generica* del test); este comprueba que se **cumple el cometido del AC**. Para cada AC: (1) **mapeo AC↔test**: que el test asserte lo que *ese* AC exige, no una version debilitada -la calidad generica del test (verifica comportamiento real, aislamiento...) es de test-desiderata, no la repitas aqui-; (2) que el **codigo cumpla la intencion** del AC, no solo que pase su propio test (pregunta adversarial: "¿podria pasar este test y aun asi violar lo que el AC pedia?") -lectura acotada, no re-derivar cobertura-; (3) codigo que implementa **comportamiento que ningun AC pidio** (feature especulativa, andamiaje de slices futuras). El refactor tras verde que permite el paso 5 (extraer helpers, mejorar estructura) **traza al AC** y no es hallazgo. FALLA (severidad alta) si un AC no queda pineado, si el codigo no cumple su intencion, o si hay comportamiento sin AC que lo justifique.
- `[sem]` **Manipulacion de tests (regla de hierro; siempre alta).** Con `git diff <base>...HEAD` sobre los ficheros de test, comprueba que ningun test **preexistente** se haya debilitado para acomodar la implementacion: assert relajado (`== x` -> `is not None`/truthy), numero de asserts que baja, test borrado, `@skip`/`xfail` anadido, o comentarios tipo "TODO/temporal" en tests. Debilitar un test que ya existia es **FALLA (severidad alta)**, citando path + linea. Cambios puramente aditivos (nuevos asserts, nuevos tests) o refactor de test que preserva los asserts **no** son hallazgo. Este check no necesita ningun artefacto: sale del propio diff de la rama.
- `[sem]` **Fixture/wiring theater (siempre alta).** Cruza la lista etiquetada produccion/test que devolvio el implementador (paso 5) con `git diff --name-only`: si la suite pasa a verde pero el diff **no toca ningun fichero de produccion** (solo tests/fixtures), el efecto puede estarlo produciendo el fixture y no el codigo. Prueba de borrado (juicio por lectura): "¿pasaria la suite revirtiendo solo los cambios de test, con el codigo de produccion?". Si el efecto lo da el fixture y no el codigo, es **FALLA (severidad alta)**. Excepcion legitima: slices sin codigo de produccion (migracion/infra) cuyo efecto se verifica de otro modo.
- `[sem]` **Calidad de tests (test-desiderata)**: si la slice anade o toca tests, correr la skill `test-desiderata` sobre ellos. Bloquea solo ante violaciones **graves** (no determinista, no aislado, o test que no verifica comportamiento real); las menores (legibilidad, velocidad...) se reportan como aviso sin bloquear. En slices sin tests (infra/migracion), se salta.

La higiene del diff staged y el formato del commit **no** se comprueban aqui: son `[det]` puros y los ejecuta `scripts/gates.py` en el paso 7, cuando el staging ya existe. No los re-juzgues por lectura.

**Veredicto estructurado (no prosa).** Lanza este Agent con `schema` para que devuelva exactamente:

```json
{
  "veredicto": "PASA | FALLA",
  "hallazgos": [
    {"regla": "boundaries", "path": "src/infra/x.py", "linea": 42,
     "severidad": "alta | media | baja", "evidencia": "...", "detalle": "..."}
  ]
}
```

- Reglas del veredicto: **FALLA** si alguna puerta objetiva `[det]` falla o si hay algun hallazgo `severidad: alta`. Los `media`/`baja` se reportan pero no bloquean por si solos (juicio: si se acumulan, el verificador puede subir a FALLA explicando por que).
- **Evidencia antes de bloquear (calibracion).** Un hallazgo `severidad: alta` **exige evidencia citable**: regla + path + linea + por que, en el campo `evidencia`. Si no puedes citarla concretamente, **degrada la severidad** en vez de bloquear. Contiene el over-reporting: a un verificador al que se le pide encontrar fallos siempre encuentra alguno; obligar a citar evidencia hace que el bloqueo sea real, no defensivo.
- El schema se valida en la capa de tool: no parsees texto libre.
- Si FALLA: devolver al paso 5 con los `hallazgos` (max 2 reintentos). Guarda el conteo de hallazgos por severidad y el veredicto final: alimentan las metricas.
- **Si agota los reintentos con FALLA**: marca la slice `bloqueada: verify` en el issue, **registra la metrica durable** (`veredicto=FALLA`, `ci=none`; ver paso 8) y **para**. No sigas al paso 7: sin PASA del verificador no se abre PR. Sin esto, el rechazo del verificador -justo lo que queremos medir- no dejaria rastro.

### 7. Abrir PR

- **Stagea SOLO los ficheros de codigo/test que devolvio el implementador.** Usa
  `git add <ruta1> <ruta2> ...` con la lista explicita; **prohibido `git add -A`, `git add .`
  o `git commit -a`**. Planes y design-docs NO entran en la PR (la spec vive en el issue, no como
  fichero).
- **Puerta determinista de higiene (`[det]`).** Tras stagear, corre
  `python3 ~/.claude/skills/slice-runner/scripts/gates.py pr-hygiene --repo . --allow <ruta1> --allow <ruta2> ...`
  con la lista exacta que devolvio el implementador. Exit 0 = PASA. Si FALLA (algo staged fuera de
  lo declarado, o un artefacto: plan, design-doc), **corrige el staging** (`git restore --staged`) y
  reintenta; no lo re-interpretes a ojo. No commitees hasta PASA.
- **Conventional commit.** Mensaje y titulo de PR = `type(name): resumen`, con el `type` (por
  defecto `feat`) y el `name` de la slice como scope: p. ej. `feat(cantidad-vo): add Cantidad value
  object`. Redactar un conventional commit lo haces bien sin puerta; lo unico determinista aqui es
  que el `name` (scope) viene de la spec (issue), no de un slug inventado. Cuerpo del commit opcional
  con detalle. Nunca commitees en `master`/`main`. Push de la rama `slice/NN-<name>`.
- `gh pr create --draft` con titulo `type(name): resumen` y cuerpo que: **referencia el issue con
  `Part of #<N>`** (no `Closes`: una PR es una slice, no la feature entera), lista los AC cumplidos y
  resume los cambios. **La PR se abre siempre en draft**: la CI corre igual, pero deja explicito que
  esta pendiente de tu revision y no lista para mergear (refuerza que el merge es humano). Sacarla de
  draft (`ready for review`) y mergear lo decides tu.
- Actualiza la linea de la slice en el issue con la PR: `set_slice_estado(..., "en-curso", pr=<M>)`
  -> `gh issue edit` (el estado pasara a `esperando-merge` en el paso 8 al haber CI verde).
- No marcar como ready-to-merge automaticamente mas alla de lo normal; el merge es humano.

### 8. Esperar CI verde (puerta final)

- Espera hasta verde o rojo con **ticks acotados en background + notificacion** (o la herramienta `Monitor`), **nunca** `gh pr checks --watch` ni un `sleep` largo que bloquee la shell/sesion (principio de esperas no bloqueantes; es trabajo deterministico que hace el harness, no la IA poll-eando). Cada tick consulta `gh pr checks --json` y devuelve el control. Respeta un timeout de espera razonable.
- **Verde**: **registra la metrica durable** (ver abajo, `ci=green`), marca la slice `esperando-merge` en el issue (aun **no** `[x]`: el merge es humano; ver paso 9) y **pasa al paso 9** (no paras aqui).
- **Rojo**: trae los logs del check fallido (`gh run view --log-failed`), un reintento via paso 5 con esos logs.
  - Si tras el reintento sigue roja: marca la slice `bloqueada: ci-roja` en el issue, **registra la metrica durable** (`ci=red`), **deja el PR abierto**, resume el fallo con logs y **para** (circuit breaker). No cierres el PR ni descartes la rama/worktree.
- Si en cualquier momento se supera el presupuesto de tokens/$ de la slice: marca la slice `abortada: presupuesto` en el issue, **registra la metrica durable** (`veredicto=abortada-presupuesto`) y para.

**Registro de la metrica durable (`[det]`).** Al cerrar la slice, en **cualquiera** de los caminos de cierre (verify terminal FALLA del paso 6, CI verde, CI roja terminal, o presupuesto), anexa un registro con:

```
python3 ~/.claude/skills/slice-runner/scripts/metrics.py record --repo <repo> --slice <slice_id> --name <name> \
  --veredicto <PASA|FALLA|abortada-presupuesto> --ci <green|red|none> \
  --hallazgos-alta N --hallazgos-media N --hallazgos-baja N \
  --reintentos-implement N --reintentos-ci N --duracion-s N
```

- `veredicto` = el del verificador del paso 6 (`PASA`/`FALLA`), o `abortada-presupuesto` si paro el presupuesto. Los conteos de `hallazgos` salen del veredicto estructurado del paso 6.
- Este log vive **fuera del repo** (`~/.claude/slice-runner/metrics.jsonl`) y **nunca entra en una PR**. Coste en tokens: opcional (`--coste-tokens`); si no lo tienes de OTel, no lo inventes (se omite).

### 9. Esperar el merge y encadenar el deploy

El merge sigue siendo **humano** (lo haces tu en GitHub); lo que se automatiza es la **transicion**, para que no tengas que decir "continua" a mano.

- La slice ya figura `esperando-merge` en el issue (paso 8): eso comunica **esperando una decision tuya**, no parada.
- Vigila el estado de la PR con **ticks acotados en background + notificacion** (`gh pr view --json state,mergedAt`), nunca una shell bloqueante larga. Respeta un timeout razonable de espera de merge.
  - **Merged**: marca la slice `mergeada` (`[x]`) en el issue e invoca automaticamente la skill `deploy-watch` (sin pedir "continua"). `deploy-watch` arranca sola e infiere servicio/namespace; solo te preguntara si la inferencia es ambigua (`check-alignment` solo cuando hay duda real).
  - **Timeout / cerrada sin merge**: deja la slice `esperando-merge` (o `bloqueada` si se cerro sin merge) en el issue y **para**, dejando el PR como este. Reanudas invocando de nuevo cuando quieras.

## Fin

Al parar (o al ceder el control a `deploy-watch`), reporta siempre: slice ejecutada, estado
(mergeada / esperando-merge / bloqueada / abortada), URL del PR, resultado de CI, coste de la slice,
y siguiente slice pendiente (del issue). Si quedan slices pendientes, sugiere volver a invocar (o
envolver en `/loop` para Nivel 2).

### Cierre del run (todas las slices mergeadas)

Cuando **no quedan slices pendientes** (todas `[x] mergeada` en el issue), el run ha terminado:

- Comenta en el issue que todas las slices estan mergeadas, con el resumen.
- **Deja el cierre del issue al humano** (control humano en el hito; ademas el issue es el registro
  duradero, cerrarlo no lo borra).
- **No toques `~/.claude/slice-runner/metrics.jsonl`**: es durable, vive fuera del repo y es justo
  lo que debe sobrevivir para medir la evolucion del loop.
- No hay estado local que descartar: no existe `.slice-runner/`.
