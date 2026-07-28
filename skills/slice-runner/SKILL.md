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
- **Los subagentes no son un detalle de implementacion: son la garantia.** Esta skill **no puede ejecutarse sin ellos**, y por eso **invocarla cuenta como pedirlos**: no es iniciativa del agente, es la skill haciendo su trabajo. Si el entorno los veta (instruccion global de no usar el Agent tool, politica de la organizacion, o cualquier otra restriccion), **para en el paso 3 y dilo**; no continues en modo degradado. Verificar inline es que quien escribio el codigo se apruebe a si mismo, que es justo el fallo que esta skill existe para prevenir: la PR saldria con un PASA que no significa nada, y eso es peor que no producir PR. Fail-closed, igual que `pr-hygiene` y `diff-bundle`: si la garantia no se sostiene, no se produce el artefacto. (`deploy-watch` decide distinto a proposito: ver su skill.)
- **Las convenciones del repo mandan.** Implementador y verificador cargan como vara de medir las **fuentes de convencion declaradas en el issue** (seccion `## Fuentes de convencion`: docs y skills de proyecto), por encima de cualquier default generico de hexagonal/DDD. En conflicto, ganan las convenciones del repo. No se asumen rutas fijas: las fuentes se descubren por repo y las declara `slice-spec` en el issue; `slice-runner` solo las lee. Si el issue no trae esa seccion, **para** y pide anadirla con `slice-spec` (no ejecutes con la vara vacia: fue la causa raiz de desviaciones silenciosas de convencion). Sin la vara, el verificador no puede cazar violaciones reales (p. ej. una migracion que siembra datos donde la convencion lo prohibe).
- **Puertas de parada objetivas.** No hay PR mergeable sin lint limpio, tipos limpios, tests verdes y **CI verde**, ejecutados con los comandos reales del repo (paso 2), no con binarios asumidos.
- **El juez no ejecuta puertas ni ve output de build.** Las puertas deterministas (lint, tipos, tests) corren **antes** del verificador: el implementador las corre en su ciclo para tener feedback incremental, y el orquestador las re-corre como backstop (paso 6) porque el auto-reporte del implementador no es fuente de verdad. Cuando se invoca al verificador (paso 7) ya estan verdes por construccion, asi que no recibe nada de ellas: su presupuesto entero se gasta en lo semantico. Meter un traceback de pytest en el contexto del unico agente cuyo valor es el juicio es `limited-focus` autoinfligido, y un `ruff` sucio no debe consumir un reintento adversarial.
- **Determinista lo que es regla exacta (`offload-deterministic`).** Lo mecanico NO se delega al juicio de un agente: lo resuelve el script `scripts/gates.py`, cuyo exit code es autoritativo. Tres subcomandos: `pr-hygiene` (higiene del diff staged, paso 8), `checks` (ejecutar lint/tipos/tests con los comandos del paso 2 y devolver exit code + salida truncada, pasos 5 y 6) y `diff-bundle` (materializar el diff de la slice para el verificador, paso 7). No se pide dos veces a la IA lo que un script decide una vez, y ningun agente ve output crudo de build.
- **Los tests son ciudadanos de primera categoria.** Valen tanto o mas que el codigo de produccion: ahi va el mayor esfuerzo de calidad, y sobre todo la exigencia de que **testeen de verdad lo que la slice pretende construir**, no una version debilitada ni un proxy que pasa por casualidad. Un test que pasa sin fijar su AC es un fallo tan grave como codigo roto. Con dientes, no como declaracion: el implementador aplica `writing-good-tests.md` de `superpowers:test-driven-development` (nombrar el cambio de produccion que haria fallar el test **antes** de escribirlo; asertar comportamiento real, nunca mocks; codigo de test fuera de produccion), y el verificador lo bloquea con severidad **alta** en el paso 7 (mapeo AC↔test, fixture/wiring theater, manipulacion de tests, test-desiderata).
- **TDD consciente de capa.** El ciclo TDD lo define `superpowers:test-driven-development` (lo invoca el implementador, paso 5); aqui vive solo el delta: si las convenciones del repo eximen una capa (p. ej. modelos ORM y migraciones que no se testean por separado), la puerta de esa slice es "suite intacta + verificacion de datos/efecto" en vez del test-first por AC. Decide la convencion del repo, no este documento ni superpowers.
- **Alinear antes de implementar.** Antes de escribir codigo, mostrar el entendimiento de la slice (alcance, AC, capa afectada, comando de validacion) y esperar go/no-go. Nunca transcribir a ciegas el codigo pre-horneado de una spec: validalo contra las convenciones primero.
- **Seguir `backend-best-practices`.** El implementador carga esa skill y respeta hexagonal/DDD, DI, Pydantic en boundaries, subordinada siempre a las convenciones del repo.
- **El estado del run vive en el issue de GitHub.** La spec y el estado de cada slice viven en el cuerpo de un issue de GitHub (una feature = un issue): es la **unica fuente de verdad**, viva y duradera. No hay estado local (`.slice-runner/`, ledger ni panel). El agente olvida entre slices; al arrancar re-lee el issue. Registro duradero = issue (intencion + estado) + PRs mergeadas (codigo).
- **La PR solo lleva el codigo de la slice.** El commit stagea unicamente los ficheros de codigo/test que produjo el implementador (`git add` explicito, nunca `-A`/`.`). Planes y design-docs jamas entran en la PR (la spec ya no es un fichero: vive en el issue).
- **Contexto fresco por slice.** Cada slice arranca sin arrastrar la conversacion de la anterior; lo que persiste entre slices es el **issue** (spec + estado), que se re-lee al empezar. Evita la degradacion de contexto (patron Ralph) y hace seguro el Nivel 2 (`/loop`).
- **Circuit breaker.** Maximo 2 reintentos por fase, y las **puertas tienen presupuesto propio** (2), separado del del verificador (2): gastar el presupuesto adversarial en un fallo mecanico es justo lo que este reparto evita. Ademas, **presupuesto de coste**: si la slice supera el limite de tokens/$ configurado, para con estado `abortada-presupuesto`. Si la CI sigue roja tras el reintento, para, deja el PR abierto y reporta con logs.
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

Reporta: tasa de FALLA del verificador, tasa de bloqueo por puertas, % de slices al primer intento,
media de reintentos (implement, puertas y CI por separado), tasa de CI roja, duracion media. Es el
instrumento para el "confianza en el loop" del Step 3 del mapa de madurez. Coste en tokens no se mide
aqui (sale de OTel de Claude Code).

El **veto del juez** (`FALLA`) y el **bloqueo por puertas** (`bloqueada-puertas`) se registran aparte a
proposito: uno es un rechazo semantico y el otro un fallo mecanico, y confundirlos deja inservible el
unico instrumento que hay para calibrar al juez.

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
  verificador (paso 7); las skills de proyecto se leen/invocan y se citan igual que una regla.
- **Selecciona la slice**: la indicada por el usuario, o la primera `pendiente`. No repitas las
  `mergeada`. Si una slice quedo `esperando-merge`, retomala ahi (paso 10) en vez de reimplementarla.
- Extrae titulo, alcance y AC de la slice. Si no hay AC, para y pidelos: sin AC no hay puerta de verificacion.
- **Toma el `name` de la slice** (entre parentesis tras el id). Si no hay name, deriva un slug del titulo y avisa. La rama es `slice/NN-<name>` (p. ej. `slice/01-cantidad-vo`). Toma tambien el `type` opcional (por defecto `feat`).
- Marca la slice `en-curso` en el issue (`set_slice_estado(..., "en-curso")` -> `gh issue edit --body`).

### 2. Autodetectar comandos del repo (Makefile primero)

Infierelos, no los asumas. Cachea lo detectado en la respuesta.

- **Prioridad 1 — Makefile**: si hay `Makefile`, usa sus targets (`make test`, `make check-types`, `make check-style`/`make linting`, `make fastapi-migrate`, `make env-start`...). En muchos repos todo corre en Docker via `make`; lanzar `pytest`/`ruff`/`mypy` directos fallaria. Lee el Makefile para saber que target cubre cada puerta.
- **Prioridad 2 — pyproject/tox**: si no hay Makefile util, cae a `ruff`, `mypy` (leyendo `[tool.mypy]`), `pytest` (rutas/opts de `pyproject.toml`/`tox.ini`).
- **Workflow de CI**: identifica el workflow de `.github/workflows/*.yml` que corre en `pull_request`.
- Si una puerta no tiene comando claro, pregunta antes de continuar.

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
- **El ciclo TDD: invoca `superpowers:test-driven-development`** y siguelo (RED -> verificar que
  falla por el motivo esperado -> GREEN minimo -> REFACTOR), incluida su referencia
  `writing-good-tests.md`. No se resume aqui: fuente unica, para que no se desincronice.
  **Precedencia si algo choca**: convenciones del repo > exencion de capa (delta 1) > Iron Law de
  superpowers.
- **Delta 1 - exencion de capa.** En capas que la convencion del repo no testea por separado (p. ej.
  modelos ORM y migraciones alembic), la Iron Law de superpowers **no** aplica: no fuerces
  test-first; la puerta es "suite intacta + verificacion del efecto" (p. ej. el `SELECT` que exige el
  plan). En capas con test (dominio/aplicacion/API...) aplica el ciclo completo, un test por AC.
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
  principios): gasta el presupuesto de calidad en que cada test **fije de verdad su AC**, no en
  ponerlo verde. Antes de escribir un test, nombra el cambio de produccion que lo haria fallar; si no
  sabes nombrarlo, el test no esta testeando lo que la slice pretende construir.
- No sobredimensionar: lo minimo para los AC. Nada de andamiaje de slices futuras.
- **No tocar el issue ni artefactos.** Solo ficheros de codigo/test de la slice. No escribas planes
  ni design-docs, ni edites el issue: el estado del issue lo gestiona el orquestador, no la PR.
- **Auto-check de wiring antes de entregar.** Corre `git diff --name-only` y confirma que los ficheros
  de **produccion** que la slice debia tocar aparecen en el diff, no solo tests: si la suite pasa a
  verde sin tocar produccion, el efecto lo esta produciendo el test/fixture y no el codigo. En slices
  sin codigo de produccion (migracion/infra) no aplica. (El verificador lo cruza en el paso 7.)
- **Puertas verdes antes de entregar (`[det]`).** No entregues con lint, tipos o tests en rojo: corre

      python3 ~/.claude/skills/slice-runner/scripts/gates.py checks --repo . \
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

    python3 ~/.claude/skills/slice-runner/scripts/gates.py checks --repo . \
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

    python3 ~/.claude/skills/slice-runner/scripts/gates.py diff-bundle --repo . \
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
- los **AC** de la slice, tal cual estan en el issue;
- las **fuentes de convencion** declaradas en el issue (paso 1);
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
