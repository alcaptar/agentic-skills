# 12-factor-agents: donde encaja este repo, y que implica

Referencia: [humanlayer/12-factor-agents](https://github.com/humanlayer/12-factor-agents). Los doce
factores se leyeron enteros el 2026-07-31, no de memoria; las citas salen de esa lectura.

Este documento tiene dos mitades que se necesitan: una **auditoria** del repo contra los doce factores,
y el **spike medido** que responde a la pregunta que la auditoria abre. Sin la primera, el spike no se
sabe por que existe; sin el segundo, la auditoria seria una opinion.

## TL;DR

1. **Los factores 1, 4 y 9 ya se cumplen**, y en el 9 el repo va mas alla de lo que el texto pide.
2. **El factor 2 es la tesis del repo** (prompts como codigo versionado), con un hueco: no hay evals.
3. **Los factores 2, 3, 5, 6, 8 y 12 presuponen que el loop es tuyo.** Aqui no lo es: el loop es de
   Claude Code y el orquestador son las ~600 lineas de `skills/slice-runner/SKILL.md`, prosa que un
   modelo interpreta dentro de la sesion de la persona. **Esa es la causa raiz** del problema de
   contexto y de casi todos los defectos de abajo.
4. **Los huecos no son doce, son tres**: los factores 5, 6, 8 y 12 apuntan todos al mismo sitio.
5. El spike valida que `claude -p` es la funcion sin estado que hace falta, **y anade un requisito que
   no estaba previsto**: el aislamiento del implementador hay que decidirlo antes de escribir el
   orquestador, no despues.

## Mapeo factor por factor

| Factor | Estado | Evidencia |
|---|---|---|
| 1. Lenguaje natural a llamadas de herramienta | **Cumple** | `skills/slice-runner/scripts/controles.py`, `issue_body.py` y `skills/deploy-watch/scripts/deploy_core.py` son "el codigo determinista tiene la soberania". El modelo propone, el exit code decide |
| 2. Duena de tus prompts | **Cumple, con hueco** | Skills y agentes versionados aqui, con `~/.claude/` por symlink; `tests/test_skill_contracts.py` valida contratos escritos en `.md`. Falta lo que el factor pide ademas: *"testing y evaluaciones como codigo regular"* |
| 3. Duena de tu ventana de contexto | **Parcial, conocido** | Muy trabajado (salida de build a disco, relato largo fuera del `SKILL.md`, subagentes desechables). Residual: el orquestador vive en la sesion del harness, que no es del repo. Declarado como fase 2 en `docs/design-notes.md` |
| 4. Las herramientas son salida estructurada | **Cumple** | El veredicto del verificador es un objeto validado por `controles.py verify-verdict`. Frontera mas debil: la lista de rutas del implementador vuelve en prosa, con `pr-hygiene` como red |
| 5. Unificar estado de ejecucion y de negocio | **Incumple** | Cluster A, abajo |
| 6. Lanzar / pausar / reanudar | **Parcial** | Pausa y reanuda bien **entre** slices (el issue es el estado). **Dentro** de una slice no hay reanudacion: cluster A |
| 7. Contactar humanos con llamadas de herramienta | **Incumple** | Cluster B, abajo |
| 8. Duena de tu control de flujo | **Incumple** | Los diez pasos y los presupuestos son prosa interpretada. Contradice el principio propio del repo, "lo que es regla exacta pasa a script, sin excepciones" |
| 9. Compactar errores en la ventana de contexto | **Cumple, y va mas alla** | `controles.py controles --out` manda el log a disco y devuelve ruta; el error entero llega al implementador y **nada** llega al que juzga. El factor pide compactar; el repo ademas aisla |
| 10. Agentes pequenos y enfocados | **Parcial, conocido** | Tres skills y dos agentes bien acotados, pero el orquestador tiene diez pasos con reintentos, por encima del rango de 3-10 que el factor recomienda |
| 11. Disparar desde cualquier sitio | **Incumple** | El estado ya vive en un issue de GitHub, pero el disparador solo existe en la linea de comandos. Compone con el cluster B |
| 12. El agente como reductor sin estado | **Parcial** | Los nucleos puros existen (`deploy_core.py`, el nucleo de `issue_body.py`). El orquestador no es un reductor: su estado es implicito en su contexto. El propio autor marca este factor como didactico |

## Los tres clusters

### Cluster A — el estado de ejecucion no esta unificado con el de negocio (factores 5, 6, 8, 12)

El issue tiene el estado de **negocio** (que slice, en que fase macro) pero no el de **ejecucion**: en
que paso va, cuanto presupuesto queda, que hallazgos no bloqueantes estan abiertos. Cuatro defectos que
salen de leer el codigo, no de suponer:

- **Una slice `en-curso` al reanudar no tiene guion.** `_elige_slice` en
  `skills/slice-runner/scripts/issue_body.py` devuelve la primera slice con estado distinto de
  `mergeada`, lo que incluye `en-curso`, `bloqueada: *` y `abortada: *`. El paso 1 del `SKILL.md` solo
  da procedimiento para `pendiente` y `esperando-merge`. Con una slice `en-curso` se re-elige, el
  `git switch -c` del paso 4 choca con la rama existente, y el paso 5 reimplementa desde cero sin saber
  que se hizo.
- **Los presupuestos se resetean en silencio.** Los 2 reintentos de controles, los 2 del verificador y
  los 3 ticks de la ventana de gracia de la integracion continua viven **solo** en el contexto del
  orquestador. Al reanudar o compactar vuelven a cero sin que nada avise.
- **Bajo `/loop`, una slice bloqueada se re-elige indefinidamente.** El `max_consecutive_failures`
  figura en `docs/design-notes.md` como guardrail pendiente, no construido.
- **`metrics.py record` solo escribe al cerrar**, asi que una slice que muere a mitad no deja rastro ni
  de haber existido.

Y hay una confesion en el propio repo que este cluster resuelve: la ventana de gracia de la integracion
continua se declaro **excepcion** a "lo que es regla exacta pasa a script", y el motivo escrito es
exactamente *"la ventana es una cuenta entre invocaciones, y `ci-status` es de un tiro y sin estado a
proposito"*. Con estado de ejecucion durable, ese motivo desaparece.

### Cluster B — el contacto humano no es una accion durable (factores 7, 11)

El go/no-go del paso 3 es "espera respuesta del usuario" en el chat. `docs/design-notes.md` ya lo
admite: *"bajo `/loop` ese control humano ya es ficcion"*. El factor 7 da el arreglo con nombre:
contactar al humano es una **accion estructurada con estado persistido** (pausa, notifica, reanuda por
disparador), no una pregunta en una conversacion que nadie mira. El factor 11 anade que el disparador
deberia vivir donde ya vive el estado.

### Cluster C — los prompts son codigo de primera categoria pero no tienen evals (factor 2)

La pieza de mas valor del repo, el verificador, se calibra con impresiones: smoke manual y metricas
terminales por slice. `docs/maturity-map.md` pone como siguiente paso *"validar el verificador en runs
reales hasta ganarle confianza"*, que es precisamente lo que un eval convierte en medible. Hoy no se
puede: el verificador es un subagente invocado desde una conversacion, no una funcion
`diff -> veredicto`.

## Que NO aplica, dicho a proposito

Estampar los doce factores seria `ai-slop`. Lo que queda fuera y por que:

- **Factores 3 y 10 en su parte residual**: el orquestador vive en un harness ajeno. No es un defecto
  de diseno que se arregle escribiendo prosa; es la consecuencia de no ser dueno del loop, y solo se
  arregla cambiando eso.
- **Factor 12 como reductor literal**: el propio documento lo marca como *"mostly just for fun"*. Su
  parte util es el cluster A.
- **Factor 11 como canales multiples** (Slack, correo, mensajeria): fuera de alcance para uso personal.
  Lo que si aplica es que el disparador viva donde vive el estado.

## Los dos loops, y solo uno merece ser propio

La conclusion de la auditoria no es "anadir una seccion de estado al issue". Es que **el orquestador
esta en el sitio equivocado**. Pero hay dos loops distintos:

- **El loop de orquestacion** (elegir slice, implementar, controlar, verificar, abrir pull request,
  esperar la integracion continua, presupuestos, reintentos): **debe ser propio**. Es determinista, es
  donde vive el estado, y hoy lo ejecuta un modelo leyendo prosa.
- **El loop de codificar** (leer, editar, ejecutar, iterar): **no**. Reconstruirlo es un proyecto grande
  y saldria peor que Claude Code. Ahi el modelo es el intermediario del factor 1: recibe un prompt,
  devuelve estructura, muere.

El criterio de corte por skill es **si el valor esta en la conversacion o en el loop**:

| Skill | Donde esta su valor | Destino |
|---|---|---|
| `skills/slice-spec/SKILL.md` | La conversacion con una persona | Sigue siendo skill. Ser dueno del loop aqui no compra nada y cuesta justo lo que la hace buena |
| `skills/slice-runner/SKILL.md` | El loop | Programa |
| `skills/deploy-watch/SKILL.md` | El loop de ticks, con nucleo puro ya escrito | Programa, o skill fina sobre uno |

Y el coste de la transicion es menor de lo que parece: `controles.py`, `issue_body.py`,
`deploy_core.py`, `metrics.py`, `discover_controles.py` y `discover_conventions.py` **ya son** el nucleo
determinista y los puertos, con sus tests. Lo que se escribe nuevo es el aggregate del run, el puerto
del agente de codigo y el entrypoint. Lo que se **borra** es la mayor parte del `SKILL.md` del runner:
la prosa de control de flujo pasa a codigo con tests.

## Spike: `claude -p` como llamada sin estado (2026-07-31)

**Por que existe.** Todo lo anterior depende de una afirmacion que no se puede dar por buena leyendo
documentacion: que `claude -p` sirve como funcion sin estado y con salida estructurada. Se midio en un
playground aislado, fuera del repo. **15 llamadas, 1,07 dolares, todo con haiku** -el modelo mas debil
a proposito: lo que cumpla ahi lo cumple un modelo mejor-.

### Lo que se confirmo

**`--json-schema` hace cumplir el contrato del veredicto.** Cuatro ejecuciones con el system prompt
real de `agents/slice-verifier.md` (2.223 palabras, transferido tal cual con `--append-system-prompt`)
sobre un diff con una violacion de convencion plantada:

| Ejecucion | Contrato (`verify-verdict`) | Veredicto del juez | alta/media/baja | Coste | Duracion |
|---|---|---|---|---|---|
| 1 | exit 0, PASA | FALLA | 4/0/0 | 0,109 $ | 51 s |
| 2 | exit 0, PASA | FALLA | 2/0/0 | 0,096 $ | 77 s |
| 3 | exit 0, PASA | FALLA | 2/0/0 | 0,109 $ | 86 s |
| 4 | exit 0, PASA | FALLA | 3/0/0 | 0,070 $ | 56 s |

Cuatro de cuatro pasan **el validador que ya existe en el repo**, sin desenvolver prosa ni reinvocar.
`result` es una cadena con el objeto, consumible tal cual por `controles.py verify-verdict`. Esto ataca
directamente lo que hoy declara `skills/slice-runner/SKILL.md`: *"el cumplimiento del formato es
estocastico"*. Con el esquema desaparece, y con el probablemente el contador `--descartes-verify`
entero. Varia el **numero** de hallazgos, no el veredicto, que es la varianza que se espera de un juez.

**`--disallowedTools` bloquea de verdad, pero la intuicion lleva al flag equivocado.** Los dos flags no
son simetricos y confundirlos es peor que no usar ninguno:

- `--disallowedTools Bash` deja la herramienta **fuera del juego**: el agente responde que no tiene
  ninguna herramienta de shell disponible y `permission_denials` queda **vacio**, porque nunca lo
  intento. Ausencia estructural, que es justo lo que el `allowed-tools` del frontmatter no daba (lo
  refuto el smoke del 2026-07-27, en `docs/design-notes.md`).
- Adversarialmente, el agente **intento escapar delegando en un subagente**. Fallo porque la denegacion
  **se hereda al subagente**. Verificado, y es load-bearing: sin esa herencia, delegar seria la puerta
  de atras del control entero.
- `--allowedTools 'Read,Grep,Glob'` **no restringe: pre-aprueba.** Con eso puesto, `Bash` seguia
  disponible, el agente lo invoco, quedo registrado en `permission_denials`, y la llamada **acabo
  pidiendo aprobacion humana** en vez de devolver un veredicto. En un proceso no interactivo eso es una
  llamada perdida, no un fallo seguro.

**Coste y latencia, con un matiz que cambia la lectura.** Unos **30.000 tokens de preambulo por
llamada**, irreducibles: reemplazar el prompt de sistema con `--system-prompt` no baja nada frente a
anadirlo con `--append-system-prompt` (105.873 contra 99.090 acumulados), y acotar herramientas baja un
14%. Lo que pesa son las definiciones de herramientas, no el prompt. El verificador con haiku sale a
0,07-0,11 dolares y 50-86 segundos por llamada.

El matiz: **eso no es coste nuevo**. Los subagentes de hoy ya pagan su propio preambulo. Lo que la
arquitectura propia elimina es el coste del orquestador, que pasa a ser Python y cuesta **cero tokens**.
Esta ultima frase es **razonamiento, no medicion**: no se puede instrumentar el consumo de un subagente
desde dentro de la sesion que lo lanza.

### Lo que obliga a cambiar el diseno

**Los permisos del implementador son el problema difícil, y hay que resolverlo antes de escribir el
orquestador.**

- Modo de permisos por defecto: **entra en barrena**. Diez turnos, 0,11 dolares, seis denegaciones y
  cero ficheros escritos.
- `--permission-mode acceptEdits` **si escribe ficheros** sin `--dangerously-skip-permissions`. Pero
  `Bash` sigue denegado, asi que no puede correr los tests, y el implementador los necesita: el ciclo
  de desarrollo guiado por tests es su metodologia entera.
- **Pre-aprobar comandos por patron no es viable.** Tres ejecuciones del mismo prompt produjeron tres
  cadenas distintas (`python -m pytest test_mod.py -v`, `pytest test_mod.py -v`, y la variante con
  `python3`). No se controla lo que teclea el agente, asi que un `--allowedTools 'Bash(...)'` derivado
  de los controles declarados falla de forma intermitente, que es el peor modo de fallo posible.

De ahi que la unica combinacion que funciona sea **permisos amplios con aislamiento en el proceso**
(contenedor o worktree), que es exactamente lo que ya recomienda `docs/research-agent-loops.md`
-"contenedores como control principal de blast radius", y "los worktrees aislan estado de codigo, no de
ejecucion"-. El aislamiento deja de ser una mejora del Nivel 3 y pasa a ser **requisito de la primera
version**.

**`--bare` no sirve con autenticacion de suscripcion.** Devuelve `Not logged in` y exit 1: exige
`ANTHROPIC_API_KEY` estricta y nunca lee OAuth ni el llavero. La via de minimizar contexto con ese flag
implica una facturacion aparte.

### Dos hallazgos que no se buscaban

- **El JSON de salida trae la telemetria que faltaba**: `total_cost_usd`, `usage` con desglose de cache,
  `num_turns` y `duration_ms`. `metrics.py` deja de necesitar OpenTelemetry para el coste, y
  `--coste-tokens` deja de ser opcional.
- **`permission_denials` es una senal determinista** de que el agente intento algo que no debia. Hoy el
  repo no tiene forma de saberlo.

### Un footgun operativo

Los flags variadicos (`--disallowedTools A B C`) **se tragan el prompt posicional** y la invocacion
muere con `Input must be provided either through stdin or as a prompt argument`. Hay que usar la forma
con comas y pasar el prompt por entrada estandar.

## Fuentes

- [humanlayer/12-factor-agents](https://github.com/humanlayer/12-factor-agents) — los doce factores,
  leidos completos el 2026-07-31.
- `docs/research-agent-loops.md` — aislamiento, circuit breakers y el coste impredecible; es lo que
  sostiene que el aislamiento sea requisito y no mejora.
- `docs/design-notes.md` — la fase 2 pendiente ya nombraba *"un proceso `claude -p` por slice lanzado
  desde un script"*. La lectura de los doce factores no lo inventa: lo asciende de opcion a
  arquitectura.
- `docs/maturity-map.md` — donde encaja el pipeline y por que el cluster C es el siguiente escalon.
