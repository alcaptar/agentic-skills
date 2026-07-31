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

El **por que** largo de estas reglas -que smoke la descubrio, que alternativas se descartaron, que creencias se refutaron- vive en `references/por-que.md`. **No lo cargues para ejecutar**: solo si vas a cambiar esta skill. Aqui cada regla lleva su motivo en una frase, que es lo que hace falta para no "arreglarla" hacia el lado facil.

## Principios no negociables

Enunciados; el detalle operativo esta en el paso que los aplica.

- **El que implementa no verifica.** Dos **agentes definidos** distintos: `slice-implementer` (paso 5)
  y `slice-verifier` (paso 7), adversarial y sin `Bash`.
- **Los subagentes no son un detalle de implementacion: son la garantia.** Esta skill **no puede
  ejecutarse sin ellos**, y por eso **invocarla cuenta como pedirlos**: no pidas permiso. Si el entorno
  los veta (veto global al Agent tool, politica de la organizacion, un agente sin resolver por symlink
  ausente), **dilo siempre** y decide con este criterio:
  **¿se puede declarar la degradacion en el artefacto que produces?** Si se puede, degrada y declaralo
  **ahi**, no solo en el chat; si el artefacto entero significa justo la garantia que has perdido,
  **para**. Esta skill cae del lado de
  **parar**, en el **paso 3**: su artefacto es una **PR con veredicto PASA**, donde el veredicto *es* la
  afirmacion de haberse verificado, asi que degradado seria falso de forma **invisible aguas abajo**
  -quien revise asume que paso el pipeline-, y parar no cuesta nada irreversible. (`deploy-watch` aplica
  el **mismo criterio** y cae del otro lado, porque su veredicto **si** puede declarar su procedencia:
  artefacto distinto, no incoherencia.)
- **Las convenciones del repo mandan** (pasos 1, 5 y 7), por encima de cualquier default de
  hexagonal/DDD y de `backend-best-practices`, que es vara secundaria solo en backends Python. Sin la
  vara declarada, el verificador no puede cazar violaciones reales: se para.
- **Controles de parada objetivos y deterministas.** No hay PR mergeable sin lint limpio, tipos
  limpios, tests verdes y **CI verde**, con los comandos que **el issue declara** (paso 2). Lo mecanico
  no lo juzga un agente (`offload-deterministic`): lo resuelven `scripts/controles.py` (`controles`,
  `pr-hygiene`, `diff-bundle`, `ci-status`, `verify-verdict`) y `scripts/issue_body.py` (`show`,
  `set-estado`), cuyos exit codes son autoritativos. **No improvises esas invocaciones a mano** -ni
  `gh`, ni `git`, ni python inline-: asi ninguna depende de que recuerdes el nombre de un campo, ni una
  escritura sobre el registro duradero de que un `python3 -c` este bien escrito.
- **Nadie que juzgue ve output de build** (pasos 5-7). Los controles corren antes del verificador y su
  salida va a disco: solo se reenvian rutas. Un traceback en el contexto del unico agente cuyo valor es
  el juicio es `limited-focus` autoinfligido, y un `ruff` sucio no debe gastar un reintento adversarial.
- **Los tests son ciudadanos de primera categoria.** La exigencia es que **fijen de verdad lo que la
  slice pretende construir**, no una version debilitada ni un proxy que pasa por casualidad: un test que
  pasa sin fijar su criterio es un fallo tan grave como codigo roto. Lo aplica el implementador y lo
  bloquea el verificador con severidad **alta** (paso 7).
- **TDD consciente de capa.** El ciclo lo define `superpowers:test-driven-development` (lo invoca el
  implementador); el delta es que si la convencion del repo exime una capa (p. ej. modelos ORM y
  migraciones), el control es "suite intacta + verificacion del efecto" en vez del test-first por
  criterio. Decide la convencion del repo, no este documento ni superpowers.
- **La observabilidad es parte de la slice.** Si la slice declara `SENAL:` y la senal no existe,
  instrumentarla es codigo de produccion de **esta** slice y su emision se fija con un test; el valor
  vivo lo comprueba `deploy-watch` (paso 10). Si no la trae, **avisa y sigue**: al contrario que las
  fuentes de convencion -sin las cuales verificar es imposible-, esto solo degrada la comprobacion
  post-deploy al veredicto generico, y eso `deploy-watch` **si** lo declara.
- **Alinear antes de implementar** (paso 3): mostrar el entendimiento y esperar go/no-go. Nunca
  transcribir a ciegas codigo pre-horneado de una spec. Evita `silent-misalignment` y `ai-slop`.
- **El estado del run vive en el issue de GitHub**, unica fuente de verdad, viva y duradera: no hay
  estado local (`.slice-runner/`, ledger ni panel). El agente olvida entre slices; al arrancar re-lee el
  issue. Registro duradero = issue (intencion + estado) + PRs mergeadas (codigo).
- **La PR cuenta la intencion, no el codigo**, y solo lleva el codigo de la slice (paso 8).
- **Una slice puede vivir en otro repo.** `REPO: <org>/<repo>` fija el destino; ausente = el repo del
  issue. Cuando la hay, **todo el ciclo ocurre ahi** (controles, rama, diff, PR, CI) y la vara es la de
  **ese** repo, no la del repo de la app. El issue sigue siendo uno solo.
- **El contexto desechable es el de los subagentes, no el de tu sesion.** Implementador y verificador
  nacen y mueren por invocacion: ahi si se tira, y por eso el output crudo (build, diff, convenciones)
  vive en ellos. El **orquestador** vive en la sesion de la persona y **acumula el run entero**, asi que
  cada slice paga esta skill otra vez. Lo que hace seguro el Nivel 2 no es que el contexto se limpie
  solo -`/loop` reinyecta el prompt en la **misma** conversacion, con el contexto intacto a proposito-
  sino que **todo el estado esta en el issue**: puedes tirar la sesion cuando quieras sin perder nada.
  Con varias slices por feature, **sesion nueva entre slices** en vez de compactar: compactar deja al
  orquestador decidiendo con el contexto mutilado, que es el fallo que este pipeline existe para evitar.
- **Circuit breaker.** Maximo 2 reintentos por fase, con presupuesto **propio** para los controles (2)
  separado del del verificador (2): gastar el presupuesto adversarial en un fallo mecanico es lo que
  este reparto evita. Y presupuesto de coste: si la slice supera el limite de tokens/$ configurado, para
  con estado `abortada-presupuesto`.
- **Esperas no bloqueantes.** Nada de shells bloqueantes largas para esperar (`gh pr checks --watch`,
  `sleep` largos, polls colgados 30-60 min): **ticks acotados en background + notificacion** (o
  `Monitor`), devolviendo el control entre ticks.
- **No asumir worktree.** Rama normal por defecto; worktree solo al paralelizar slices (Nivel 2) o si
  el repo ya declara config de worktrees.

## Formato de spec (cuerpo del issue)

La spec vive en el **cuerpo de un issue de GitHub** (una feature = un issue): un **checklist de
slices**, cada una con nombre, criterios embebidos y marcador de estado. Si el issue no encaja en este
formato, para y pide una spec valida (o sugiere `/slice-spec`).

```markdown
## Intencion
Hoy el ajuste de stock se hace a mano en la consola: no queda rastro de quien lo hizo
y cuando el recuento no cuadra no hay forma de reconstruir que paso.

## Fuentes de convencion
- doc: .claude/CLAUDE.md
- skill: .claude/skills/duplicate-action

### mercadona/mercadona.online.gke
- doc: templates/CLAUDE.md

## Controles
- lint: make linting
- types: make check-types
- tests: make test

### mercadona/mercadona.online.gke
- schema: make test_prometheus_rules

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
      ACEPTACION: la regla dispara con un ajuste fallido en 5m
      SENAL: prometheus ALERTS{alertname="ShopAjusteFallido"} presente y == 0 en 24h; advisory
```

Unidad de trabajo = cada item `- [ ] slice-NN ...`; una feature de una sola slice es un checklist de
una linea. El parseo y la reescritura los hace la logica pura de `scripts/issue_body.py`; la I/O contra
el issue es `gh`. **`## Fuentes de convencion` y `## Controles` son por repo**: las lineas antes de
cualquier `### <org>/<repo>` son las del repo del issue, y cada subseccion las de un repo destino. Las
declara `slice-spec`; aqui se exigen y se para si faltan (pasos 1 y 2).

- **`## Controles`** — pares `nombre: comando`, con nombres libres (`lint`, `types`, `tests`, o
  `schema` en un repo de manifiestos): el script no sabe nada de toolchains. Un repo sin controles
  reales lo declara con la linea reservada `- ninguno: <motivo>`, que sale del parser con `exento` a
  True: **vacio y eximido no son lo mismo**, igual que en `SENAL: exenta`.
- **`## Intencion` e `INTENCION:`** — el por que, a nivel de feature y de slice: que esta mal hoy y
  deja de estarlo. Es lo que va al cuerpo de la PR (paso 8). Si faltan, **avisa y sigue**: la PR
  reconstruye la intencion y declara que la infirio. La obligatoriedad vive en `slice-spec`.
- **`ACEPTACION:` (una o mas lineas)** — los criterios verificables antes de fusionar. La etiqueta
  **se llamaba `AC:`** y el parser sigue aceptando esa forma porque hay issues abiertos escritos asi;
  lo que se emite y se documenta es el nombre completo.
- **`SENAL:` (una o mas lineas)** — como se comprueba la slice **viva en produccion**; la consume
  `deploy-watch`. `SENAL: exenta - <motivo>` cuando no aplica. Si falta, **avisa y sigue**.
- **`REPO:`** — repo destino. Ausente = el repo del issue.
- **`(name)` obligatorio en specs nuevas**, kebab-case tras el id: alimenta la rama
  (`slice/01-cantidad-vo`) y el scope del commit (`feat(cantidad-vo): ...`) de forma determinista, sin
  derivar slugs de texto libre. Si falta, deriva un slug del titulo y **avisa**; no bloquea.
  **Type opcional** dentro del parentesis: `slice-03 (refactor: extraer-repo): ...`; por defecto `feat`.
- **Restricciones duras = criterio de aceptacion**: lo que la slice debe respetar (p. ej. "no toca
  infra directamente") se expresa como un criterio comprobable mas, y el verificador lo comprueba.

### Estado de cada slice (marcador en su linea)

- `pendiente` — aun no empezada.
- `en-curso` — implementando/verificando.
- `esperando-merge` — PR abierta, CI verde, esperando la decision humana de merge.
- `mergeada` — PR mergeada. **Es el unico estado que marca el checkbox `[x]`**, para que la barra de
  progreso nativa de GitHub siga siendo fiel a lo que esta en main.
- `bloqueada: <motivo>` — `sin-subagentes` (el entorno veta el Agent tool: para en el paso 3 sin
  escribir codigo), `controles` (lint/tipos/tests sin arreglar tras los reintentos), `verify` (veto del
  verificador), `ci-roja`, o `ci-indeterminada` (la CI no se pudo medir: sin checks, o respuesta de `gh`
  ilegible; no es ni verde ni rojo). En `ci-roja` y `ci-indeterminada` deja el PR abierto; en los otros
  tres no hay PR.
- `abortada: presupuesto` — supero el presupuesto de la slice.

Es a la vez memoria intra-run (al reanudar, una slice en `esperando-merge` se retoma ahi, no se
reimplementa) y registro duradero. En cada transicion macro se reescribe **solo la linea de esa slice**
con `issue_body.py set-estado`. **No lo hagas a mano**: un `gh issue view` que devuelve vacio seguido de
un `edit` **borra la spec entera del issue**, y el subcomando falla en cerrado ante eso. `deploy-watch`
comenta ahi su veredicto del deploy.

### Metricas durables (fuera del repo)

`~/.claude/slice-runner/metrics.jsonl` es un log append-only, un registro por slice cerrada, que **no
vive en el repo** (por tanto nunca entra en una PR). Existe para decidir con datos cuando subir de nivel
de autonomia; lo escribe y lo agrega `scripts/metrics.py`, o sea que la IA no estima cifras a ojo. Tu
solo escribes (`record`, paso 9); quien lee es la persona, con `metrics.py report [--repo <repo>]`
-detalle de lo que agrega, en `references/por-que.md`-.

`<repo>` debe ser un **identificador estable** (nombre del directorio raiz o slug del remoto), el mismo
en `record` y en `report`. En slices cross-repo sigue siendo el **repo del issue**, no el destino:
agrupa el run de la feature, que es la unidad que se calibra.

## Steps

### 1. Localizar el issue y seleccionar slice

- **Identifica el issue** (numero o URL). Si no se da, lista los abiertos (`gh issue list`) y pregunta
  cual; para `/loop`, el numero viaja en el input del loop.
- **Lee el issue con un solo comando (`[det]`)**, que ya elige la siguiente slice sin cerrar y emite
  todo lo que necesitan los pasos 1 y 2:

      python3 ~/.claude/skills/slice-runner/scripts/issue_body.py show --repo <org/repo> --issue <N> --json [--slice slice-NN]

  Devuelve JSON con `slice` (id, name, type, estado, pr, repo, intencion, aceptacion, senal, y la
  `rama` y el `scope` ya derivados), `fuentes` y `controles` **ya filtrados por el repo de la slice**,
  `intencion_feature`, y los dos flags de seccion presente. Exit 2 = no hay ninguna linea de slice
  valida: para y pide una spec valida (o sugiere `/slice-spec`).
- **Selecciona la slice**: la que indique el usuario, o la primera `pendiente`. No repitas las
  `mergeada`. Una slice en `esperando-merge` se retoma en el paso 10, no se reimplementa.
- **Determina el repo de trabajo**: `slice.repo` si lo trae, o el del issue. Si es otro, resuelve su
  **ruta local** y usala en todo lo que sigue (`--repo`, `git -C`, `cwd`); si no la encuentras, para y
  preguntala en vez de adivinarla.
- **Carga la vara de medir**: las `fuentes` que emitio `show`. Si la seccion **falta o esta vacia**, o
  si la slice declara `REPO:` y **su** subseccion no existe, para y pide anadirla con `slice-spec
  validate`: sin vara no se ejecuta, y **no heredes la del repo de la app** para una slice de otro repo
  -es justo la desviacion silenciosa que esto evita-. Son los punteros que cargaran implementador
  (paso 5) y verificador (paso 7).
- **Criterios de aceptacion**: si la slice no los trae, para y pidelos; sin criterios no hay control de
  verificacion.
- **Intencion**, en sus dos niveles (feature y slice). Viaja al implementador (paso 5) y al cuerpo de
  la PR (paso 8). Si falta, **avisa y sigue**, pero **anota que habra que inferirla**, porque el
  encabezado de la PR tiene que decirlo: que la ausencia la detecte el script y no tu criterio es lo
  que impide que una PR presente como declarado lo que se invento.
- **`SENAL`**: si la trae, viaja al implementador, al verificador y a `deploy-watch`. Si no, avisa
  (`slice-spec validate`) y sigue.
- **`name`** y `type` (por defecto `feat`). La rama es `slice/NN-<name>`.
- Marca la slice `en-curso` (`[det]`):

      python3 ~/.claude/skills/slice-runner/scripts/issue_body.py set-estado --repo <org/repo> \
        --issue <N> --slice <slice_id> --estado en-curso

### 2. Leer los controles declarados en el issue

**No los deduzcas: leelos.** Vienen en la salida de `show`, ya filtrados por repo. No abras el
`Makefile`, ni el `pyproject.toml`, ni los workflows: ese trabajo lo hizo `slice-spec` una vez, lo
confirmo una persona, y dejo rastro revisable. Deducirlos por slice metia el toolchain del repo en el
contexto que tiene que durar hasta el paso 10; dejarselo al implementador seria peor, porque el
**juzgado estaria definiendo la vara con la que se le juzga** y basta `compliance-bias` para acabar
midiendose con `make test-unit`.

- **Si la seccion falta o esta vacia**, o si la slice declara `REPO:` y **su** subseccion no existe,
  **para** y pide anadirla con `slice-spec validate`. Fail-closed, igual que con las fuentes: **no
  heredes los controles del repo de la app**, porque correr `make test` de la app contra un repo de
  manifiestos no valida nada.
- **Repo sin controles reales** (p. ej. paneles de Grafana, donde la CI solo publica en `master`): el
  issue lo declara con `- ninguno: <motivo>` y el parser lo devuelve `exento`. No se ejecuta ningun
  control y la slice se trata como **capa eximida**: la verificacion real es post-deploy. No inventes
  un control ni finjas que existe.
- **Si un comando declarado ya no resuelve**, fallara como cualquier control y la slice acabara
  `bloqueada: controles` con el log; no hay pre-flight, a proposito. Lo que **no** puedes hacer es
  arreglar el `Makefile` ni cambiar el comando para que pase -eso es bajar la vara, la misma patologia
  que adaptar un test preexistente-: se corrige en el issue con `slice-spec validate`.

Se pasan al script tal cual estan declarados, en los pasos 5 y 6:

    --control lint="make linting" --control types="make check-types" --control tests="make test"

### 3. Alinear antes de implementar (check-alignment)

- **Control de subagentes (fail-closed, lo primero).** Declara que vas a lanzar **dos** Agent:
  `slice-implementer` (paso 5) y `slice-verifier` (paso 7). Invocar esta skill cuenta como que el
  usuario los pide, asi que no preguntes permiso. Pero si **no puedes** lanzarlos -veto global al Agent
  tool, politica de la organizacion, **cualquiera de los dos** sin resolver por symlink ausente-: marca
  la slice `bloqueada: sin-subagentes`, explica la restriccion concreta y **para aqui**, sin escribir
  codigo. No ofrezcas hacerlo inline: la verificacion inline es el fallo que esta skill previene, y una
  PR con verificacion de teatro es peor que ninguna PR.
- Resume: slice elegida (id + `name`), **repo de trabajo** (y su ruta local si no es el del issue),
  criterios de aceptacion, **`SENAL` y que hara con ella** (serie que ya existe / hay que instrumentarla
  y como / exenta), capa(s) afectada(s), comando de validacion, `type(name)` del commit, y como piensa
  abordarla.
- Si el cambio claramente **no es un `feat`** y la spec no declaro type, confirmalo aqui: es barato y
  evita un scope de commit erroneo.
- Si la spec pre-hornea codigo, contrastalo contra las fuentes de convencion y **senala cualquier
  violacion antes de escribir**.
- Espera go/no-go del usuario.

### 4. Preparar rama de trabajo

- **En el repo de trabajo de la slice.** Si es otro, comprueba que esta limpio y actualizado antes de
  ramificar; nunca arrastres cambios sueltos de otro trabajo.
- **Rama normal por defecto**: `git switch -c slice/NN-<name>` desde la base actualizada. Worktree solo
  al paralelizar slices (Nivel 2) o si el repo ya declara config de worktrees, creado desde esa misma
  base.

### 5. Implementar (agente `slice-implementer`)

Lanza un Agent con `subagent_type: slice-implementer`, **agente definido**
(`~/.claude/agents/slice-implementer.md`, symlink a `agents/slice-implementer.md` de este repo) y no
`general-purpose`: la metodologia -ciclo TDD, los cinco deltas, auto-check de wiring, controles verdes
antes de entregar- vive en su **system prompt**, verbatim en cada invocacion, en vez de que tu la
relates y puedas parafrasearla o saltarte un delta. Conserva las tres propiedades por las que antes era
`general-purpose` (`model: inherit` mantiene el modelo fuerte, tiene `Bash`, su criterio lo escribimos
nosotros); lo que se descarta es un agente **prestado**, que arrastraria la metodologia de otro flujo.

Tu trabajo es pasarle **los datos del run**, no la metodologia:

- numero de issue, `slice_id`, `name` y `type`;
- la **intencion** de la slice, y la de la feature como encuadre;
- los **criterios de aceptacion**, tal cual estan en el issue;
- la **`SENAL`** (o que esta exenta con su motivo, o que la spec no la declara);
- las **fuentes de convencion del repo de la slice** (paso 1, ya filtradas);
- los **controles** como `nombre=comando` (paso 2), tal cual estan declarados;
- la **ruta del repo de trabajo**;
- **si es reintento**: los `hallazgos` del verificador (paso 7), o los controles en FALLA con la **ruta
  del log** de cada uno (paso 6). Reenvia rutas: no abras los logs.

Devuelve: la lista explicita de rutas creadas o modificadas **marcando cada una como produccion o
test** (es lo que se stageara en el paso 6 y lo que el verificador usa para el check de wiring), tests
anadidos, resumen del enfoque, y lo que no pudo hacer.

### 6. Stagear lo declarado y correr los controles (backstop del orquestador)

**El `git add` de la lista declarada va primero, y los controles despues** (`[det]` los dos): un control
que lee el **indice** de git -como el que comprueba que toda ruta citada en los `.md` sigue en el arbol-
no ve un fichero **nuevo** sin stagear, y el implementador **no toca `git`** por diseno, asi que medir
antes de stagear inventa un rojo que nadie en el loop puede arreglar.

1. **Stagea SOLO los ficheros que devolvio el implementador**, con la lista explicita:
   `git add <ruta1> <ruta2> ...`. **Prohibido `git add -A`, `git add .` o `git commit -a`**. En un
   reintento se rehace: la lista nueva puede traer ficheros que antes no existian.
2. **Higiene del diff staged**:
   `python3 ~/.claude/skills/slice-runner/scripts/controles.py pr-hygiene --repo <repo-de-la-slice> --allow <ruta1> --allow <ruta2> ...`
   con esa lista exacta. Exit 0 = PASA. Si FALLA (algo staged fuera de lo declarado, o un artefacto),
   **corrige el staging** (`git restore --staged`) y reintenta; no lo re-interpretes a ojo. **No sigas
   al 3 hasta PASA**: un fichero **untracked es invisible** al diff del indice, asi que esto es lo que
   garantiza que lo que se mide -aqui y en el paso 7- sea exactamente lo que el implementador declaro.
3. **Re-ejecuta tu mismo** los controles declarados, con `--out` a un directorio **fuera del repo**:

       python3 ~/.claude/skills/slice-runner/scripts/controles.py controles --repo <repo-de-la-slice> \
         --control lint="<cmd>" --control types="<cmd>" --control tests="<cmd>" \
         --out <dir-fuera-del-repo> --json

El implementador ya los corrio, pero **su auto-reporte no es fuente de verdad**: no es que su ejecucion
valga menos -mismo script, mismo exit code- es que **no ves sus tool calls, solo su mensaje final en
prosa**, y los modos de fallo son mundanos (los corrio antes de su ultima edicion, corrio un
subconjunto, resumio como "verde salvo un warning" lo que era un fallo).

- **Verde** (exit 0): pasa al paso 7.
- **Rojo**: vuelve al paso 5 con **solo los controles en FALLA y la `log` (ruta) de cada uno**. No
  invoques al verificador: un fallo mecanico no se juzga, se arregla. Presupuesto propio: 2 reintentos.
- **Si agota los reintentos**: marca la slice `bloqueada: controles`, **registra la metrica durable**
  (`veredicto=bloqueada-controles`, `ci=none`, `--reintentos-controles N`; paso 9) y **para**. No se
  abre PR con controles en rojo.

**No abras esos logs.** Con `--out` el JSON trae rutas, y tu trabajo es reenviarlas: el implementador
abre el fichero y recibe el error **entero** -mejor feedback ahi abajo y cero contexto aqui arriba-. Un
traceback en tu contexto no cambia ninguna decision tuya: la decision ya la tomo el exit code.

### 7. Verificar (agente `slice-verifier`, adversarial)

Lanza un Agent con `subagent_type: slice-verifier`, **agente definido**
(`~/.claude/agents/slice-verifier.md`, symlink a `agents/slice-verifier.md`) por dos razones: su
**rubrica va en el system prompt**, verbatim -la parte mas importante del loop no debe depender de que
tu la transcribas-, y **no tiene `Bash`** (`tools: Read, Grep, Glob, Skill`), asi que su incapacidad de
ejecutar controles es **estructural por ausencia de la tool**, no cumplimiento de una instruccion.
`model: inherit` conserva el modelo fuerte, que el juicio mas sutil requiere.

**El indice ya esta listo desde el paso 6**: staged con la lista declarada y con `pr-hygiene` en PASA.
Lo que se juzga es ese **indice**, no `HEAD`, porque el commit va **despues** (paso 8): asi un veto no
deja rastro que deshacer y la slice sigue siendo un solo commit sin `--amend`; y como el indice es
exactamente lo que sera el commit, juzga lo que ira en la PR y no una aproximacion.

**Antes de invocarlo, materializa el diff (`[det]`)**, que el verificador no puede calcular:

    python3 ~/.claude/skills/slice-runner/scripts/controles.py diff-bundle --repo <repo-de-la-slice> \
      --base <base> --out <dir-fuera-del-repo> --json

Escribe `slice.diff` y `files.txt` y devuelve sus rutas. `--out` va **fuera del repo**: un fichero de
trabajo dentro nunca debe poder acabar en la PR. El rango lo fija el script -el indice contra el
branch-point- y no tu criterio: sin anclar ahi, los commits que la base haya avanzado saldrian como
borrados y el verificador cazaria violaciones fantasma. Si devuelve FALLA (base inexistente, o nada
staged), arreglalo antes de invocar: "nada staged" suele ser el `git add` olvidado del paso 6.

**No le pases nada de los controles** (estan verdes por construccion: un resumen seria cero informacion
y solo gastaria contexto) **ni el "resumen del enfoque"** del implementador: juzga el diff, no la
narrativa. **Inputs** (lo del run; lo estable ya esta en el agente): numero de issue, `slice_id` y
`name`; los criterios de aceptacion tal cual; la `SENAL` tal cual (o exenta con motivo, o que no se
declara); las fuentes de convencion del repo de la slice, y el repo destino si no es el del issue; las
rutas de `slice.diff` y `files.txt`; la ruta del repo, para que lea el codigo alrededor del diff; y la
lista etiquetada produccion/test del paso 5.

**Veredicto.** Devuelve como mensaje final exactamente este objeto JSON (lo exige su system prompt; la
tool `Agent` no valida schemas, asi que si vuelve envuelto en prosa es un fallo del agente y se
**reinvoca**, no se parsea a mano). La reinvocacion se cuenta en `--descartes-verify` y no gasta
presupuesto: no se ha tocado el codigo. **La regla es load-bearing**: el cumplimiento del formato es
estocastico -la misma invocacion ha devuelto prosa una vez y el JSON pelado al reinvocarla sin cambiar
nada-, asi que es lo unico que sostiene el contrato.

```json
{
  "veredicto": "PASA | FALLA",
  "hallazgos": [
    {"regla": "boundaries", "path": "src/infra/x.py", "linea": 42,
     "severidad": "alta | media | baja", "evidencia": "...", "detalle": "..."}
  ]
}
```

**Valida su respuesta con el script, no a ojo (`[det]`).** Escribe su mensaje final tal cual a un
fichero **fuera del repo** y pasalo por:

    python3 ~/.claude/skills/slice-runner/scripts/controles.py verify-verdict \
      --file <dir-fuera-del-repo>/veredicto.json --json

Exit 0 = cumple su contrato, y el JSON te devuelve el `conteo` por severidad ya hecho (es lo que
alimenta la metrica del paso 9: no lo cuentes tu). Exit 1 = **descarta esa invocacion y reinvoca al
juez**, sin tocar el codigo, y suma uno a `--descartes-verify`; no arregles el JSON a mano ni
interpretes lo que "queria decir". Exit 2 = el fichero no se pudo leer, o sea que el fallo es tuyo. La
razon de que exista no es solo la prosa envolvente: es el JSON **estructuralmente plausible pero
equivocado** (`"veredicto": "PASS"`, una severidad inventada, un hallazgo sin `evidencia`, un `PASA`
que convive con un hallazgo `alta`) que leido a ojo pasa por bueno porque parsea.

- **FALLA** si hay algun hallazgo `severidad: alta` (los `media`/`baja` no bloquean por si solos, pero
  el agente puede escalar si se acumulan, explicando por que).
- Si FALLA: vuelve al paso 5 con los `hallazgos` (max 2 reintentos, presupuesto propio). Guarda el
  `conteo` y el veredicto final: alimentan las metricas del paso 9.
- **Si agota los reintentos con FALLA**: marca la slice `bloqueada: verify`, **registra la metrica
  durable** (`veredicto=FALLA`, `ci=none`) y **para**. Sin PASA no se abre PR, y sin el registro el
  rechazo del verificador -justo lo que queremos medir- no dejaria rastro.

**Divergencia deliberada de `superpowers:requesting-code-review` (no es un olvido).** Esta skill delega
en superpowers el ciclo TDD (paso 5) pero **a proposito no usa** su skill de code review, que si
re-revisa el codigo: aqui el segundo par de ojos se gasta en la vara de medir del repo. El argumento
completo esta en `agents/slice-verifier.md`.

### 8. Commitear y abrir PR

El indice ya esta staged, con `pr-hygiene` en PASA, y el verificador dio PASA sobre **ese** indice.
Aqui solo se commitea lo que ya se juzgo: **no stagees nada mas desde el `git add` del paso 6**, porque
seria codigo que entra en la PR sin haber pasado por `pr-hygiene` ni por el verificador.

- **Conventional commit.** Mensaje y titulo de PR = `type(name): resumen`, con el `name` de la slice
  como scope: `feat(cantidad-vo): add Cantidad value object`. Lo unico determinista aqui es que el
  scope viene de la spec, no de un slug inventado. Nunca commitees en `master`/`main`. Push de la rama
  `slice/NN-<name>`.
- `gh pr create --draft` **en el repo de la slice** con ese titulo y este cuerpo, en este orden:

      ## Intencion
      <la INTENCION de la slice, encuadrada en una frase de la del issue: que estaba mal
      hoy y deja de estarlo cuando esto entra>

      ## Criterios de aceptacion cumplidos
      - <un criterio por linea, con donde vive su test>

      ## Senal a comprobar tras el despliegue
      <la linea SENAL de la slice, o "exenta - <motivo>">

      Part of #<N>

  - **Nada de enumerar ficheros, clases ni modulos, ni de narrar el diff**: eso ya lo cuenta GitHub
    mejor que tu y en su sitio. Lo que un revisor no puede deducir del diff es **por que**, y ese es
    todo el trabajo de este cuerpo.
  - **Si la intencion no venia declarada en el issue**, el encabezado lo dice: `## Intencion (inferida
    del issue, no declarada)`. Nunca la presentes como declarada.
  - **`Part of #<N>`**, no `Closes`: una PR es una slice, no la feature entera. Cross-repo,
    `Part of <org>/<repo-del-issue>#<N>`, que GitHub enlaza igual.
  - **Draft siempre**: la CI corre igual, pero deja explicito que esta pendiente de tu revision.
    Sacarla de draft y mergear lo decides tu.
- Actualiza la linea de la slice con la PR (`[det]`, `set-estado ... --estado en-curso --pr <M>`); pasa
  a `esperando-merge` en el paso 9 al haber CI verde.

### 9. Esperar CI verde (control final)

Espera con **ticks acotados en background + notificacion** (o `Monitor`), **nunca**
`gh pr checks --watch` ni un `sleep` largo que bloquee la shell/sesion, con un timeout razonable.
**Cada tick es una llamada a `ci-status` (`[det]`)**, nunca un `gh pr checks` a mano:

    python3 ~/.claude/skills/slice-runner/scripts/controles.py ci-status --repo <repo-de-la-slice> \
      --pr <M> --json

Devuelve un `estado` de cinco valores y un exit code por rama (0 verde, 1 rojo, 3 pendiente, 4
indeterminado, 2 error de uso). **No inventes la invocacion de `gh`**: `gh pr checks --json` **no tiene
campo `conclusion`** -aunque `gh run list --json` si- y pedirselo devuelve un error que se lee igual que
"aun no hay checks", o sea que degrada a "nunca verde" y se come el timeout.

- **`verde`**: **registra la metrica durable** (`ci=green`), marca la slice `esperando-merge` (aun
  **no** `[x]`: el merge es humano) y **pasa al paso 10**, no pares aqui. Solo es verde un todo-pass
  explicito con al menos un check que haya corrido; lo decide el script, no tu lectura.
- **`pendiente`**: sigue tickeando.
- **`rojo`**: trae los logs del check fallido (`gh run view --log-failed`) y un reintento via paso 5 con
  esos logs. Si sigue roja: marca `bloqueada: ci-roja`, **registra la metrica durable** (`ci=red`),
  **deja el PR abierto**, resume el fallo con logs y **para**. No cierres el PR ni descartes la rama.
- **`sin-checks` o `desconocido`**: la CI **no se puede medir**. No es un fallo de la slice, asi que no
  reintentes; y no es verde, asi que no sigas al paso 10. Marca `bloqueada: ci-indeterminada` con el
  estado concreto, **registra la metrica durable** (`ci=none`), **deja el PR abierto** y **para**.
  Tratarlo como verde reportaria una PR sin CI como validada; tratarlo como rojo mandaria al
  implementador a arreglar un fallo que no existe.

Si en cualquier momento se supera el presupuesto de tokens/$ de la slice: marca `abortada:
presupuesto`, **registra la metrica durable** (`veredicto=abortada-presupuesto`) y para.

**Registro de la metrica durable (`[det]`).** Al cerrar la slice, en **cualquiera** de los caminos de
cierre (controles agotados del paso 6, verify terminal FALLA del paso 7, CI verde, CI roja terminal, o
presupuesto), anexa un registro con:

```
python3 ~/.claude/skills/slice-runner/scripts/metrics.py record --repo <repo> --slice <slice_id> --name <name> \
  --veredicto <PASA|FALLA|bloqueada-controles|abortada-presupuesto> --ci <green|red|none> \
  --hallazgos-alta N --hallazgos-media N --hallazgos-baja N \
  --reintentos-implement N --reintentos-controles N --reintentos-ci N \
  --reintentos-verify N --descartes-verify N --duracion-s N
```

- `veredicto` = el del verificador (`PASA`/`FALLA`), `bloqueada-controles` si paro en el backstop del
  paso 6, o `abortada-presupuesto`. Los conteos de `hallazgos` salen del veredicto estructurado del
  paso 7 (en `bloqueada-controles` son 0: no hubo juicio semantico). **No uses `FALLA` para un fallo de
  controles**: es mecanico, no un veto del juez, y confundirlos deja inservible su calibracion.
- **Los dos contadores del verificador tampoco se mezclan, por el mismo motivo.**
  `--reintentos-verify` son las rondas por **`FALLA`** (rechazo semantico, con vuelta al paso 5);
  `--descartes-verify`, las invocaciones **descartadas por no devolver su JSON** (fallo mecanico del
  agente, sin tocar el codigo). Sumarlos haria que su indisciplina se leyera como que el juez encuentra
  defectos, y un descarte **no** descalifica la slice como "primer intento": el codigo salio limpio.
- Coste en tokens: opcional (`--coste-tokens`); si no lo tienes de OTel, no lo inventes.

### 10. Esperar el merge y encadenar el deploy

El merge sigue siendo **humano**; lo que se automatiza es la **transicion**, para que no tengas que
decir "continua" a mano. La slice ya figura `esperando-merge` (paso 9): eso comunica **esperando una
decision tuya**, no parada. Vigila la PR con **ticks acotados en background + notificacion**
(`gh pr view --json state,mergedAt`), nunca una shell bloqueante larga, con timeout razonable.

- **Merged**: marca la slice `mergeada` (`[x]`) e invoca automaticamente la skill `deploy-watch` (sin
  pedir "continua"), **pasandole la `SENAL` de la slice** y el repo destino si no es el del issue: es lo
  que le permite comprobar *este* cambio y no solo la salud generica del servicio. Si la slice no
  declaraba senal, dilo al invocarla para que su veredicto lo declare. `deploy-watch` arranca sola e
  infiere servicio/namespace; solo pregunta si la inferencia es ambigua.
- **Timeout / cerrada sin merge**: deja la slice `esperando-merge` (o `bloqueada` si se cerro sin
  merge) y **para**, dejando el PR como este. Reanudas invocando de nuevo cuando quieras.

## Fin

Al parar (o al ceder el control a `deploy-watch`), reporta siempre: slice ejecutada (y **en que repo**,
si no es el del issue), estado (mergeada / esperando-merge / bloqueada / abortada), URL del PR,
resultado de CI, **la `SENAL` que queda por comprobar en prod** (o que la slice no declaraba ninguna),
coste de la slice, y siguiente slice pendiente. Si quedan slices, sugiere **abrir sesion nueva** para la
siguiente -tu contexto ya lleva este run entero encima- e invocar de nuevo (o envolver en `/loop` para
Nivel 2, sabiendo que `/loop` no limpia el contexto).

### Cierre del run (todas las slices mergeadas)

Cuando no quedan slices pendientes (todas `[x] mergeada`):

- Comenta en el issue que todas estan mergeadas, con el resumen.
- **Deja el cierre del issue al humano**: control humano en el hito, y ademas el issue es el registro
  duradero, asi que cerrarlo no lo borra.
- **No toques `~/.claude/slice-runner/metrics.jsonl`**: es durable, vive fuera del repo y es justo lo
  que debe sobrevivir para medir la evolucion del loop.
- No hay estado local que descartar: no existe `.slice-runner/`.
