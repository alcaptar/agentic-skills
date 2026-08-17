# Capa de infraestructura

Adaptadores de los puertos, modelos de frontera y entrypoints. Es la unica capa que sabe que hay un
subproceso, un `git` o un sistema de ficheros al otro lado.

## Lo que llega de fuera se valida al entrar

Sin excepcion, y sin `cast`: un `cast` no comprueba, solo calla a `mypy`.

- **En la frontera del programa, el esquema es Pydantic.** Los payloads que cruzan la frontera son
  `BaseModel`, uno por concepto: `verdict_payload.py` (el contrato con el juez), `harness_output.py`
  (el sobre del harness) y `contract_model.py` (la base comun: `extra="forbid"`, la traduccion del
  `ValidationError` y el volcado al contrato).
- **En los scripts de `skills/`, dataclass con `from_dict`/`from_row` a mano**, que rechaza clave
  desconocida y tipo equivocado. Son stdlib puro (ver `docs/conventions/architecture.md`), asi que no
  hay Pydantic que usar.

## Modelos de frontera

- `extra="forbid"`: una clave que no conocemos es un **rechazo**, no un campo ignorado. Significa que
  el otro lado cambio de forma y nuestras suposiciones pueden estar viejas.
- `frozen=True` y `populate_by_name=False`: se entra por el `alias`, que es el nombre del contrato, y
  no por el nombre del campo.
- **Un `alias` por campo, y de ahi sale todo lo que ve el otro lado**: el esquema que se le manda, la
  validacion de lo que devuelve y el JSON que emite la interfaz de linea de comandos. Un contrato que
  se escribe mas de una vez necesita un test solo para que sus copias no divergan.
- La conversion al dominio vive en el modelo: `from_domain(cls, entity) -> Self` para entrar,
  `to_domain(self)` para salir. **Nunca un helper de mapeo en el caso de uso.**
- Un `ValidationError` de Pydantic no sale de la capa: se traduce a la excepcion del dominio que el
  entrypoint sabe mapear.

### `strict=True` por campo, no a nivel de modelo

A nivel de modelo rompe el parseo: en modo estricto un `StrEnum` deja de aceptar su propia cadena y un
modelo anidado deja de aceptar un `dict`, con lo que el JSON del juez no valida.

Por campo, donde la coercion es peligrosa:

- **`is_error`**: sin estricto, Pydantic convierte la cadena `"no"` en `False`. O sea, el harness
  declarando que la llamada fallo y el programa leyendo que no hubo fallo.
- **`linea`**: sin estricto acepta `"11"`, `1.5` y `True`.

La vara para decidir: **¿que valor equivocado pasaria por bueno, y que decision tomariamos con el?**
Si la respuesta es "ninguna que importe", laxo vale.

### El esquema se emite plano

`JsonSchema.flat` resuelve los `$ref` y borra los `title`. Dos motivos: la **forma plana es la unica
medida de verdad** contra un `claude -p` real, y los `title` solo gastan tokens del prompt. Hay un test
que falla si vuelve a colarse una referencia.

### Un esquema que viaja en un prompt declara **un solo campo**

El harness pierde la frontera entre parametros cuando el modelo emite la llamada a `StructuredOutput`:
el primero se traga su propio cierre y todo lo que venga detras, asi que el segundo llega como texto
dentro del primero y el validador lo reporta como **campo requerido que falta**. Medido sobre 749
transcripciones: de los 31 rechazos por ese motivo, **20 traian el campo ausente pegado dentro de otro**,
con su etiqueta `<parameter name="...">` incluida -15 veces `steps` dentro de `summary`, 5 veces `plan`
dentro de `summary`-. El corte historico dice lo mismo desde el otro lado: el esquema de **un** campo de
texto no fallo ninguna de sus 25 sesiones, y el de tres fallo 5 de 6.

Y el dano no acaba en el rechazo. Tras dos o tres, el modelo minimiza para aislar el fallo -que es lo que
hace cualquiera-, el informe minimo si valida, y **se publica relleno con la firma del programa**. Por eso
la regla es la forma del esquema y no una instruccion mas en el prompt: un brief que pida el campo que
falta no puede arreglar una frontera que se pierde en el transporte, y ya se intento.

Consecuencia: `UnderstandingReportPayload` declara un unico `report`, y `ClaudeUnderstanding` **publica lo
que llega en vez de componerlo**. Se pierde que el programa garantice las secciones del comentario; se gana
que no haya forma de fallar la forma. La contrapartida se acepta porque el fallo que evita se pagaba en
llamadas enteras descartadas y en entendimientos falsos aprobados por una persona.

**Deuda declarada:** `verdict_payload.py` (`ruling` + `findings`) y `report_payload.py` (`paths` +
`left_out`) siguen con dos campos y tienen el mismo fallo medido -5 y 3 rechazos-. No se migran aqui
porque cada uno arrastra su rubrica o su brief, y media migracion se lee peor que ninguna.

**El `description` no es un `title` y por eso se queda.** Un `title` repite el nombre del campo, asi que
solo gasta; un `description` dice **que se pone ahi**, y es lo unico que el agente tiene delante en el
momento de emitir -el brief queda cientos de lineas mas arriba, y `--json-schema` no restringe la
generacion, solo valida despues-. **Consecuencia: donde el esquema describe un campo, el prompt no lo
vuelve a describir** -es la misma regla de "cada una tiene un solo sitio donde vive" de la seccion de
adaptadores-, y lo mide `test_understanding_brief.py::TestWhereTheFieldsAreSpecified`. Solo lo llevan los
payloads cuyo esquema viaja en un prompt (`understanding_report_payload.py`, y son candidatos
`verdict_payload.py` y `report_payload.py`); los que declaran esquema para un almacen durable no lo
necesitan, porque ahi nadie emite contra el esquema.

**Lo que la descripcion no arregla, y conviene no volver a creerselo:** los rechazos por campo que falta
**no** los causaba que el agente no entendiera el campo -esa fue la primera lectura, y la refuto la
medicion del apartado anterior-. Se describe el campo porque un esquema mudo es peor que uno que habla,
no porque eso evite perder un parametro.

### El `alias` traduce; cuando no hay nada que traducir, no se escribe

El contrato de `explain` (`RunPayload`, `TransitionPayload`), el de `run` (`ConductedSlicePayload`) y,
desde que el contrato del juez se tradujo a ingles, tambien `VerdictPayload`/`FindingPayload`, **los
fijamos nosotros y estan en ingles**, asi que la clave del contrato ya es el nombre del campo y un
`alias` identico solo seria ruido que hay que mantener en dos sitios. `by_alias=True` cae en el nombre
del campo cuando no hay alias, con lo que el esquema, la validacion y la salida siguen saliendo de un
solo sitio, que es lo que la regla protege.

### Un campo que se llama como un builtin rompe las anotaciones de la clase

Pydantic evalua las anotaciones **con el namespace de la clase**, asi que en un modelo con un campo
`type: object = None` -y `HarnessOutput` tiene uno, porque el sobre del harness trae esa clave- una
anotacion `ClassVar[type[ValueError]]` explota al importar el modulo con `'NoneType' object is not
subscriptable`: el `type` que resuelve es el campo, no el builtin. Por eso la excepcion con la que cada
modelo rechaza lo que no valida **entra como argumento de `_validated`** y no como `ClassVar` de la clase.
Ni el `strict` ni el `from __future__ import annotations` cambian nada aqui.

### Cuidado con `TC002` y las anotaciones de Pydantic

Pydantic resuelve las anotaciones de campo **en runtime** al crear el modelo. Un tipo que `ruff` mueva
a `if TYPE_CHECKING:` deja el modelo *not fully defined* y **revienta en la primera validacion, no al
importar**: un smoke que solo importe el modulo lo da por bueno. Lo evita
`runtime-evaluated-base-classes` en `pyproject.toml`, no la disciplina de quien escribe.

## Adaptadores

- Implementan un puerto y nada mas. **El modulo se llama como la implementacion**, no como el puerto:
  `git_diff_reader.py`, `claude_verifier.py`, `local_process.py`. Asi el par puerto/adaptador se lee
  en el nombre y caben dos implementaciones sin renombrar nada.
- **El programa no importa nada de `skills/`.** Es autocontenido: lanza `git` el mismo por el puerto
  `Process` y valida lo que recibe con sus propios modelos. **Acoplar el flujo nuevo al viejo para
  ahorrar duplicacion sale mas caro que la duplicacion** -el porque, medido, en
  `docs/design-notes.md`-, asi que las copias que eso genera se declaran y se miden con un contrato en
  vez de eliminarse.
- **Lo que define a un agente invocado viaja junto, en un objeto.** La rubrica, sus herramientas y los
  directorios que puede leer son un value object que construye la frontera y el entrypoint inyecta, no
  tres cosas repartidas por capas: repartidas, nada obliga a que cuadren, y una rubrica puede acabar
  ordenando cargar lo que el agente no puede leer sin que el veredicto lo delate. **Un puerto para un
  valor constante es indireccion; un invariante entre varios valores pide un objeto.**
- **El texto de la rubrica del juez y la metodologia del implementador se quedan en infraestructura**, no
  en una factoria de aplicacion: el prompt es lo que se le manda a **un ejecutable concreto** por su
  entrada estandar, con su esquema y sus flags, y cambia con la receta medida contra ese ejecutable. Que
  la capa que conoce el harness sea la misma que redacta lo que el harness recibe es lo que evita que
  aplicacion tenga opinion sobre el transporte.

  **Y cada una tiene un solo sitio donde vive.** Un `.md` que repita la rubrica o la metodologia es una
  segunda copia que nadie compara, y el programa **no lee `.md` de agente**: si hay que cambiar lo que se
  le pide al juez o al implementador, se cambia aqui y no hay nada mas que sincronizar.
- **Lo que no cambia entre invocaciones es constante; los datos de la slice los compone la invocacion.**
  `SliceImplementerBrief.TEXT` y la rubrica de `SliceVerifierJudge` son texto fijo, y `## Datos de la
  slice` y `## Datos del run` los redactan `ImplementerInvocation` y `JudgeInvocation` a partir del
  `Assignment` y del `SliceUnderReview` que reciben. **Aplicacion no compone texto de prompt**: pasa
  objetos del dominio y es la frontera la que decide como se escriben, por el mismo motivo por el que el
  texto fijo vive aqui. Y un prompt **cierra con el dato**, nunca con la metodologia: lo variable
  al final es lo que evita que un delimitador tenga que sobrevivir a su propio contenido -en el juez, el
  diff es literalmente lo ultimo del prompt-.

  **La forma de una lista se extrae cuando deja de ser un parecido y pasa a ser invariante.** Cada prompt
  es un contrato con un agente distinto y nada exige que se parezcan, asi que compartir la forma entre dos
  puede ser coincidencia; cuando la repite un consumidor mas, ya no lo es. **Y una condicion asi, escrita,
  se ejecuta cuando se cumple**: la que nadie ejecuta ensena que este fichero es opinion.

  **Un invocador que no tiene issue delante no llena los mismos campos que el conductor.** Juzgar un diff
  a mano, sin montar un run, es un camino vivo: por el `argv` solo llegan repo, base e identificador, asi
  que la senal y las tuplas de la slice entran vacias. La
  consecuencia es que un `verify` suelto emite `- criterios de aceptacion (0):`, y **eso no es un
  transitorio que caduque**: es lo que significa juzgar sin issue. Por eso la rubrica **describe la
  carga en vez de prometerla llena**: dice que los campos viajan siempre, que pueden venir vacios y que
  un campo vacio es un insumo que no ha llegado -que el juez reporta como falta de dato, no como item
  conforme-. Lo que **no** se hace es volver a escribir que esos insumos no existen: la afirmacion falsa
  no es "puede venir vacio", es "nunca llega". Y los campos entran **sin default** en
  `VerifySliceParams` a proposito, que es lo que obligo al conductor a llenarlos en vez de heredar el
  vacio en silencio.
- **Una fuente declarada viaja con su contenido citado por su ruta, y quien lo lee es un adaptador
  compartido, no cada invocacion por su cuenta.** `CitedSources.of` (`infrastructure/cited_sources.py`)
  resuelve `tuple[Source, ...]` a las lineas que citan cada ruta seguida de su contenido, y los tres
  invocadores (`ImplementerInvocation`, `JudgeInvocation`, `UnderstandingInvocation`) lo llaman igual: es
  la misma "forma de una lista que deja de ser parecido y pasa a ser invariante" de mas arriba, aplicada
  a lo que citan en vez de a como se estructura el prompt. El contenido lo trae el puerto
  `SourceReader` (`domain/source_reader.py`), y su unico adaptador hoy, `ProcessSourceReader`
  (`infrastructure/process_source_reader.py`), lo lee con `cat` por el puerto `Process` en vez de con
  `pathlib.Path.read_text()` como hacen los adaptadores que leen `~/.claude`
  (`LocalCallTrace`, `LocalConversationLog`, `LocalMetricsLog`, `LocalSkillLibrary`,
  `LocalPluginRegistry`). **No es la misma familia**: esos leen una raiz real de la maquina que ejecuta
  el programa, mientras que `ProcessSourceReader` lee bajo `worktree`, que es el mismo directorio que
  `GitBranches`, `GitDiffReader` y `GitWorkspace` tratan siempre como el destino de un comando de `git`
  por el puerto `Process` -nunca como una ruta que el programa abre por su cuenta-. Pasar a `pathlib` ahi
  romperia la unica costura documentada en `Cli.run` ("un solo `Process`... basta para conducir un run
  sin `gh`, sin `git` y sin harness"): un `worktree` de test no es un directorio real en disco, y toda la
  suite que lo dobla asume que leerlo pasa siempre por ese puerto.
- **La raiz de configuracion de la herramienta la resuelve `ClaudeConfig`** (`CLAUDE_CONFIG_DIR`, o
  `~/.claude` expandido, con la variable vacia tratada como ausente). La comparte todo adaptador que
  necesite saber donde vive esa configuracion, porque lo que comparten no es una regla del programa sino
  **la convencion de Claude Code**: de ahi que viva en un objeto propio y no colgada de uno de los
  adaptadores. `LocalCorpus` tenia su propia copia de esa resolucion -deuda declarada mientras ningun otro
  motivo tocaba ese adaptador-; se cerro migrandolo a `ClaudeConfig.root()` a la vez que se le daba
  ubicacion propia (ver el bullet de los cuatro almacenes durables, mas abajo), que era el motivo que
  faltaba.
- **Un adaptador que escribe a disco fuera del camino de error no captura su `OSError`.** Sale del
  programa sin mapear, aunque eso colapse con un codigo de salida que significa otra cosa. Se acepta
  porque la alternativa es peor: **decidir aqui que hacer con el fallo de escritura seria inventar una
  politica que ningun criterio pidio**, y un adaptador que decide politica es antipatron declarado de esta
  misma capa. Cuando se cierre, se cierra **decidiendo la politica** -si esa escritura es best-effort, si
  su fallo es un cierre propio del run, y con que codigo de salida se distingue-, no capturando el
  `OSError` a escondidas dentro del adaptador.
- **Los tres adaptadores que invocan el harness agrupan su telemetria en un objeto, por el mismo motivo
  declarado para `ConductSlice` en `docs/conventions/application.md`.** `ClaudeImplementer`,
  `ClaudeUnderstanding` y `ClaudeVerifier` (`infrastructure/{claude_implementer,claude_understanding,
  claude_verifier}.py`) reciben `process`, `reader` y cuatro puertos de telemetria (`trace`, `turns`,
  `spend_log`, `tool_uses`); listados sueltos, la firma salta `PLR0913` igual que le pasaba al
  conductor, y las mismas dos salidas no valen aqui: relajar el linter, o partir cada adaptador en dos
  clases que no existen por diseno sino por contar argumentos. `HarnessTelemetry`
  (`infrastructure/harness_telemetry.py`) agrupa los cuatro puertos de telemetria -nunca `process` ni
  `reader`, que cada adaptador usa por su cuenta y no comparten con este agrupamiento- y los tres
  adaptadores lo reciben ya construido desde `Cli._conductor`/`Cli._action`. **La linea, para que no se
  amplie por precedente:** esto es solo de los adaptadores que invocan `claude -p` y dejan constancia de
  la llamada; un adaptador nuevo que no escriba trace/turnos/gasto/uso de herramientas sigue listando sus
  dependencias sueltas.
- **El rastro de una llamada lo escribe el adaptador que la hace, no el caso de uso.** Se anexa en cuanto
  el sobre parsea y **antes** de entrar en el bloque que mide, por dos motivos, y el segundo es el que
  cierra la decision:

  1. **El unico sitio que ve el sobre de todas las llamadas es el adaptador.** Una llamada que muere
     dentro del bloque que mide -veredicto incoherente, permiso denegado, informe invalido- es justo la
     conversacion que se quiere leer, y en aplicacion no queda nada de ella. Grabar en la frontera cubre
     todas las llamadas del run, el `verify` suelto y tambien los descartes.
  2. **Al caso de uso ya no le cabe, y eso dice lo mismo.** Con un puerto mas suelto la firma salta
     `PLR0913`, y las salidas que **no** valen son relajar el linter y empaquetarle los argumentos, que es
     del conductor y solo de el (ver `docs/conventions/application.md`). Que el linter lo cace ahi es la
     senal de que escribir el rastro es de la capa que ve el sobre, no de la que orquesta.

  Consecuencia aceptada, y es la misma frontera que tiene el gasto: un sobre que **no** parsea no deja
  rastro -no hay identificador que escribir-, y una llamada que el harness marca fallida tampoco. Por eso
  el identificador de sesion es campo **obligatorio** del sobre y no opcional: una llamada sin
  identificador no se puede volver a encontrar, que es exactamente el fallo que este rastro existe para
  cerrar.
- **`LocalConversationLog` valida proyecciones de la transcripcion, no la linea entera, y es una
  desviacion declarada de "en la frontera el esquema es Pydantic".** La transcripcion de una sesion
  (`~/.claude/projects/<repo>/<session>.jsonl`) no es un contrato que este programa defina o del que
  dependa una version fija, al contrario que el sobre de `HarnessOutput` -la salida documentada de
  `claude -p --output-format json`- o el propio `calls.jsonl` de `LocalCallTrace` -un fichero que este
  programa escribe entero-: cada `type` de linea (`assistant`, `user`, `last-prompt`, `summary`...) trae
  decenas de claves que este lector no consume, y el vocabulario de un bloque de contenido es abierto
  (`text`, `tool_use`, `tool_result`, `thinking`, `redacted_thinking`, `image`...) y crece con cada
  version del harness sin aviso. Exigir `extra="forbid"` sobre la linea o el bloque entero rompería la
  lectura de una transcripcion real con cada campo o bloque nuevo que Anthropic anada -justo el fallo
  silencioso que "sin excepcion" evita en el resto de esta capa, pero aqui se lo haria a la funcion misma
  de este lector, que es sobrevivir a transcripciones ya grabadas-. Por eso cada modelo de
  `conversation_transcript.py` (`TranscriptUsage`, `TranscriptTextBlock`, `TranscriptToolUseBlock`,
  `TranscriptToolResultBlock`, `TranscriptMessage`) valida una proyeccion construida a mano con
  exactamente las claves de las que depende, nunca el diccionario externo completo, y sigue
  siendo `extra="forbid"` sobre esa proyeccion: una clave que si declaramos conocer y que falta o llega
  con el tipo equivocado sigue rompiendo, con `UnreadableConversationError`. Con esa misma vara,
  `LocalConversationLog._decoded_lines` deja de tragar `json.JSONDecodeError` en silencio y lanza la
  misma excepcion, igual que `LocalCallTrace._decoded`: una linea que no es JSON es corrupcion, no una
  variante mas de un vocabulario abierto.
- **`GhCommentPayload` recibe el mismo tratamiento que `LocalConversationLog`, por el mismo motivo.**
  El objeto `Comment` que devuelve `gh issue view --json comments` no es un contrato que fije este
  programa: trae mas campos de los que `read_alignment_response` consume (`author`,
  `authorAssociation`, `createdAt`, `id`, `includesCreatedEdit`, `isMinimized`, `minimizedReason`,
  `reactionGroups`, `url`, `viewerDidAuthor`), al contrario que `GhLabelPayload`, cuyo export real trae
  exactamente los campos que declara. `GhCommentsPayload.comments` se queda en
  `tuple[dict[str, object], ...]` sin tipar cada elemento contra un `BaseModel`, y
  `GhCommentPayload.from_dict` proyecta a mano solo `body` antes de validar, igual que
  `TranscriptMessage.content`.
- **`GhPullRequestReviewPayload` y `GhPullRequestReviewCommentPayload` reciben el mismo tratamiento, por el
  mismo motivo.** Los objetos que devuelven `gh api repos/{repo}/pulls/{n}/reviews` y
  `gh api repos/{repo}/pulls/{n}/comments` tampoco son un contrato que fije este programa: traen mas campos
  de los que `GhForum.reviews` consume (`user`, `html_url`, `submitted_at`, `commit_id`... en la review;
  `path`, `line`, `diff_hunk`, `created_at`... en el comentario). `GhPullRequestReviewPayload.from_dict`
  proyecta a mano `id`/`state`/`body`, y `GhPullRequestReviewCommentPayload.from_dict` proyecta
  `body`/`pull_request_review_id`, los dos antes de validar, igual que `GhCommentPayload.from_dict`.
- **Los cuatro almacenes durables viven bajo un mismo directorio y un mismo patron de nombre.**
  `LocalMetricsLog.LEDGER`, `LocalCallTrace.LEDGER`, `LocalCallSpendLog.LEDGER` y las dos rutas de
  `LocalCorpus` (`LEDGER` para los veredictos, `DIFF_LEDGER` para el diff que juzgo cada uno) resuelven
  todas bajo `ClaudeConfig.root() / "slice-runner" / "log" / "<concepto>.jsonl"`. Antes no compartian ni
  el directorio (`metrics.jsonl` colgaba de la raiz de `slice-runner/`, `calls.jsonl`/`spend.jsonl` de
  `trace/`, `verdicts.jsonl` de `corpus/`) ni la forma de resolver esa raiz (`LocalCorpus` tenia su propia
  copia de `ClaudeConfig`, ver el bullet de arriba); ahora un solo criterio contesta "donde vive esto" para
  los cuatro, documentado tambien en la tabla de `README.md`.

  **El corpus se parte en dos ficheros hermanos porque lo que pesa y lo que se consulta a menudo no son lo
  mismo.** `CorpusEntryPayload` cargaba el diff entero de cada verificacion en la misma fila que su
  veredicto, asi que contar hallazgos obligaba a leer megas de codigo que nadie iba a mirar.
  `LocalCorpus.record` ahora escribe dos lineas por verificacion, con el mismo `slice_id` y el mismo `ts`
  para poder unirlas: `CorpusVerdictPayload` (`slice_id`, `verdict`, `severity_counts`, `repo`, `issue`,
  `ts`) en `verdicts.jsonl`, y `CorpusDiffPayload` (`slice_id`, `diff`, `repo`, `issue`, `ts`) en
  `diffs.jsonl`. `test_corpus.py` mide que `verdicts.jsonl` nunca trae la clave `diff`.

  **Los cinco payloads de estos almacenes declaran su esquema con `json_schema()`**, reusando
  `JsonSchema.flat` igual que `VerdictPayload`: `HarnessCallPayload`, `CallSpendPayload`,
  `MetricsEntryPayload`, `CorpusVerdictPayload` y `CorpusDiffPayload`. Es lo que deja preguntar que campos
  trae una fila sin abrir el fichero.
- **El registro durable lo escribe el programa el mismo, igual que el rastro, el gasto y el corpus, y su
  vocabulario sigue duplicado a proposito, pero solo donde `metrics.py` lo necesita.** `LocalMetricsLog`
  implementa el puerto `MetricsLog` con el mismo patron que `LocalCallTrace`/`LocalCallSpendLog`/
  `LocalCorpus`: sin proceso externo, con `ClaudeConfig.root()` para resolver la raiz y un payload de
  frontera (`MetricsEntryPayload`, en `infrastructure/metrics_entry_payload.py`) que traduce el dominio a
  las claves del log. **El programa no delega esa escritura en un
  script fuera de su paquete**: hacerlo seria una dependencia fisica con codigo que no es referencia (ver
  `CLAUDE.md`). Consecuencia aceptada, y no
  cambia con el transporte: los vocabularios del cierre existen dos veces -en ingles dentro del programa
  (`RunState`, `DiscardCause`) y con las palabras del log en la frontera (`DurableVerdict`, `DurableCi`,
  `DurableDiscardCause`, en `metrics_entry_payload.py`)-, con un `match`
  exhaustivo entre las dos, como `IssueLabel.of`: un cierre nuevo rompe en `mypy` en vez de caer en una
  rama generica, y un run que **no** ha cerrado lanza `RunNotClosedError` en vez de escribir una fila. La
  duplicacion la **mide** `test_metrics_bridge_contract.py`, que compara los conjuntos de ambos lados y
  ademas pasa la fila que construye el payload por el lector real del script (`Fila.from_row`): una clave
  renombrada solo se veria al cerrar una slice, que es justo el momento en que un fallo pierde la fila.

  **Solo lo que `metrics.py` lee por clave literal se queda en castellano; el resto habla el idioma del
  codigo.** `Fila.from_row` fija ese contrato: `veredicto`, `ci`, `reintentos_implement`,
  `reintentos_controles` (con `reintentos_puertas` como forma retirada), `reintentos_ci`,
  `reintentos_verify`, `descartes_verify`, el grupo `harness` completo (`coste_usd`, `turnos`,
  `duracion_ms`, `tokens_cache`), `descartes_verify_causa`, `ci_indeterminada_causa`, `modelos` y
  `variante` son contrato del flujo viejo -sus alias se quedan como estaban, y tocarlos rompe
  `test_metrics_bridge_contract.py`-. `findings`, `findings_of_the_last_round`, `correction_retries`,
  `debt`, el grupo `diff` (`files_changed`/`lines_added`/`lines_deleted`), `budgets`, `models_by_role`,
  `understand_discards` e `implement_discards` no los lee ese script, asi que ya no llevan `alias`: el
  campo se sirve con su propio nombre, que ya es ingles. `MetricsLedgerRowPayload` -el lado que **relee**
  el log, en `metrics_ledger_entry.py`- tolera las
  dos formas con `validation_alias=AliasChoices(nombre_ingles, alias_castellano_viejo)`, para que una fila
  ya escrita con la forma vieja se siga agregando: `test_metrics_ledger_entry.py::TestToleratingHistory` lo
  mide fila a fila. `SeverityCountPayload` (`infrastructure/corpus_verdict_payload.py`, compartida por
  `findings`/`findings_of_the_last_round` de este payload y por `severity_counts` del corpus) sigue la
  misma regla: escribe `high`/`medium`/`low` y tolera `alta`/`media`/`baja` en la lectura, porque
  `metrics.py` tampoco mira dentro de ese grupo.
- **`budgets` y `models_by_role` no llevan un `BaseModel` propio ni un `alias` por campo interno, y el
  motivo es el criterio que los trajo.** `MetricsEntryPayload.budgets`/`models_by_role`
  (`infrastructure/metrics_entry_payload.py`) vuelcan `dataclasses.asdict(closed.budgets)`/
  `asdict(closed.models)` en `dict[str, object]`. La regla general existe para que un contrato que cambia
  de forma rompa donde se declara; aqui se invierte a proposito, porque el criterio que trajo esta fila
  pide justo lo contrario: que anadir un campo a `Budgets` o a `RoleModels` (`docs/conventions/domain.md`)
  no obligue a tocar el registro. Nombrar cada campo aqui volveria a acoplar la fila durable a la forma
  exacta de esos dos value objects, que es la dependencia que el criterio prohibe. Las claves que llegan
  son las del dataclass en ingles (`control_retries`, `slice_cost_usd`, `understand`...), sin traducir: es
  la misma lectura generica que `metrics.py._grupo` ya hace con `harness`, que agrega cualquier `dict`
  anidado sin conocer sus claves.
- **El programa no escribe ningun numero que no venga del harness.** Del sobre salen coste en dolares,
  turnos y duracion, sumados por slice; `--duracion-s` (reloj de pared) y `--coste-tokens` **no se pasan**,
  porque no son dato del harness: hay puerto de reloj (`Clock.now`, que sella cada evento del run), pero lo
  que ese reloj lee es del programa y no de lo que la llamada costo. De ahi que el gasto sea un value object que
  distingue "todavia no se ha medido nada" de "cero medido" (`HarnessSpend.measured`): con nada medido, los
  esos flags no viajan y el script no escribe la clave. Y **todas** las llamadas cuentan, tambien las que
  acaban en excepcion -si no, una fila con varios descartes escribiria un coste sistematicamente por debajo-:
  una vez parseado el sobre, `HarnessOutput.measuring()` cuelga el gasto de la llamada de cualquier
  `MeasuredCallError` que salga del bloque (veredicto incoherente, `is_error`, permiso denegado, informe
  invalido), y solo esa capa puede hacerlo porque es la unica que ve el sobre. Si el sobre **no** llego a
  parsearse no hay nada que colgar y la excepcion sale con `spend` en `None`: eso es "no medido", no un cero.

  **El gasto sobrevive a la invocacion.** Se acumula por invocacion, pero se siembra con lo que trae el
  `Run` persistido y se escribe de vuelta en cada paso que cambia algo del `Run`. Asi una slice reinvocada
  sigue viendo su presupuesto entero y la fila que cierra el run suma el coste de **todas** las
  invocaciones, no solo la ultima.

  **Los hallazgos de las vueltas todavia no, y es deuda declarada y abierta.** La fila durable cuenta los
  de **todas** las vueltas del juez -un hallazgo cazado y corregido a mitad tambien ocurrio, y por eso se
  distinguen de los de la ronda que de verdad cerro la slice-, pero se acumulan por invocacion sin
  sembrarse: una slice reinvocada escribe la fila con las vueltas de la **ultima** invocacion solamente.
  Cerrarlo es la misma cirugia que el gasto y toca el mismo formato durable: se hace entero y con su
  slice, no a medias. Mientras tanto, el presupuesto de coste acota **la invocacion**, que es donde el
  gasto si esta completo.

  **Una subissue que GitHub cerro con un `Run` todavia abierto se resuelve antes de conducir la
  siguiente.** Si su pull request esta mergeada, se escribe la fila durable y se retira la etiqueta; si no,
  se deja intacta. Sin eso, un merge hecho entre invocaciones deja el trabajo hecho y sin registrar,
  porque el precheck de subissue cerrada corta antes de llegar a ningun cierre.
- **Una pieza del flujo se apaga por el cableado, con un adaptador que no hace nada, y quien lo decide
  es el entrypoint.** Un adaptador mudo implementa el puerto y no lanza nada; el entrypoint lo inyecta
  en lugar del real. **Lo que se apaga es el cableado, no el flujo**: el caso de uso sigue llamando al
  puerto en el mismo sitio y con los mismos datos, asi que reencender es cambiar la linea que lo
  inyecta, y no hay puerto sin consumidor ni codigo que reescribir para volver. Consecuencia aceptada:
  el adaptador real se queda vivo y sin cablear, sostenido solo por su test de frontera.

  **Lo que se mide es que el proceso no se lanza, no que el adaptador mudo no haga nada** -un test
  suyo mediria el lenguaje, ver `docs/conventions/testing.md`-: el doble del puerto `Process` revienta
  con el `argv` delante si alguien vuelve a cablear el real.
- Un codigo de salida distinto de cero **es un dato**, no una excepcion: se lanza el proceso con
  `check=False` y el adaptador interpreta, porque el motivo esta en `stderr` y una excepcion lo borra.
- **Ninguna llamada a un proceso externo se lanza sin tope, y el tope no lo elige el adaptador.**
  `LocalProcess` recibe los `Budgets` por constructor y pasa `process_timeout_seconds` como `timeout` de
  `subprocess.run`; el numero y su motivo viven en `docs/conventions/domain.md`, que es lo que separa
  "aplicar un tope" -trabajo de esta capa- de "decidir cual" -politica, y por eso el constructor **no
  tiene default**: un `LocalProcess` sin presupuesto no compila-. Como el programa entero lanza procesos
  por este puerto y **solo** por el, el tope se aplica en un sitio y no hay adaptador que se lo salte.

  Al agotarse se **falla en cerrado**: `subprocess` mata al hijo y el adaptador traduce el
  `TimeoutExpired` a `ProcessTimedOutError` -que vive con el puerto, junto a `ProcessNotRunnableError`, por
  el motivo de `docs/conventions/architecture.md`-. Lo que el proceso hubiera escrito ya **se descarta**:
  media respuesta no es una respuesta, y devolver un `ProcessOutput` con un `stdout` truncado es
  exactamente como un veredicto a medias pasaria por veredicto. No hay reintento aqui: reintentar es
  politica, y esta capa no la decide (ver antipatrones).
- **`GhCi` clasifica la respuesta de `gh pr checks`.** Dos decisiones suyas que no son deriva, y estan
  escritas aqui para que no se "arreglen" hacia el lado facil mas adelante:

  1. **El codigo de salida de `gh pr checks` no se usa para clasificar: se clasifica el `stdout`.** `gh` sale
     distinto de cero con checks en rojo, con checks pendientes y con una pull request que no existe, asi que
     el codigo no distingue "rojo" de "todavia no" de "no consta" **por si solo**. El bullet de arriba dice
     que un codigo distinto de cero es un dato; aqui, sin mas, es un dato que no dice nada, y el unico que
     decide la clasificacion es la salida. La unica lectura que si usa el codigo es la siguiente, y solo
     cuando viene acompanado de `stderr`.
  2. **Un codigo distinto de cero con `stderr` no vacio es el propio comando fallando, y se distingue de una
     respuesta que si llego pero no se pudo interpretar.** Antes de tocar `stdout`, `GhCi.status` comprueba
     `code != 0 and stderr`: eso es lo unico que un `gh pr checks` que muere de verdad -credenciales, red, una
     pull request que no resuelve- deja distinto de un rojo o un pendiente legitimos, que tambien salen con
     codigo distinto de cero pero **sin** nada en `stderr` porque no son un fallo. Detectado, `GhCi` lanza
     `CiCommandFailedError` con ese `stderr` como motivo, en vez de intentar interpretar un `stdout` que en
     ese camino esta vacio. Si el `stdout` no se puede leer -no es JSON, no es un array, un item no es un
     objeto, o trae una clave que no pedimos-, `GhCheckPayload`/`GhCi` lanzan `UnreadableCiError` con el
     motivo en el mensaje.

     Las dos son excepciones del **dominio** (no de esta capa: `ConductSlice._asking_the_ci` las captura, asi
     que tienen que vivir donde aplicacion pueda importarlas), y las dos las traduce
     `CiIndeterminateCause.of_the_failure` al miembro que dice cual de las dos fue -`COMMAND_FAILED` o
     `UNREADABLE_RESPONSE`-, que viaja hasta `ClosedSlice` exactamente como `DiscardCause` viaja desde un
     `MeasuredCallError` (ver `docs/conventions/domain.md`). **Este no es permiso general para propagar
     cualquier fallo de lectura**: el vocabulario de `CiStatus` sigue teniendo `NO_CHECKS` y `UNKNOWN` para lo
     que se clasifica sin ambiguedad y sin excepcion -un bucket que el programa no conoce, o ningun check
     reportado todavia-, y esos dos siguen sin motivo porque no son un fallo, son una lectura valida. Solo las
     dos causas de arriba -el comando no corrio, la respuesta no se entendio- se convirtieron de un `UNKNOWN`
     mudo a una excepcion con motivo, y `ConductSlice` las captura para seguir produciendo
     `Outcome.INDETERMINATE`: la clasificacion que ve `StateMachine` **no cambia**, solo gana un porque que
     un `except` generico que devolviera `CiStatus.UNKNOWN` fundiria en un valor mudo.
- **`GhForum` reutiliza `GhCommandFailedError` de `gh_run_repository.py`** para un exit distinto de cero de
  `gh pr list`, en vez de declarar su propia excepcion: es el mismo fallo -un comando de `gh` que sale
  mal- y vive donde lo necesito el primer adaptador que lo tuvo. Su casa natural es un modulo de
  frontera de `gh` compartido, y se hara cuando exista un tercer adaptador de `gh`; hasta entonces, el
  acoplamiento declarado sale mas barato que una tercera copia de la misma excepcion.
- **`GitWorkspace` reutiliza `GitCommandFailedError` de `git_branches.py`** por el mismo argumento y con
  la misma fecha de caducidad: es el mismo fallo -un comando de `git` que sale mal, con el motivo en su
  `stderr`- y vive donde lo necesito el primer adaptador de `git` que lo tuvo. La unica diferencia es que
  `GitWorkspace` cae al `stdout` cuando el `stderr` viene vacio, porque `git commit` sin nada staged
  explica el motivo por `stdout` y una excepcion sin motivo obliga a reproducirlo a mano.
- **La revision `CHANGES_REQUESTED` que dispara una vuelta viaja entera en el `Run`, marcador y texto, y
  ese texto es la unica bandera de que hay una correccion en curso.** `Run.last_reviewed_id` y
  `Run.requested_changes` (`domain/run.py`, con su espejo en `RunPayload`) se persisten los dos, y
  `Run.correcting_review` es una propiedad derivada de que el segundo no este vacio. **No sigue la
  frontera del gasto y de la deuda de la pull request** -mas abajo-, que se quedan en la invocacion, y el
  motivo es que aqui el dato perdido no es telemetria: es lo que una persona pidio. Con el texto en
  `ConductSliceProgress` y una bandera aparte en el `Run`, una invocacion muerta entre marcar la review y
  entregar la correccion -presupuesto agotado, proceso matado, o al reabrir con `-RETRY`- reanudaba en
  `IMPLEMENT` con la bandera encendida y sin nada que atender, y como el marcador ya habia avanzado,
  entregaba saltandose al juez sin haber corregido nada y sin decirlo. **Dos campos que tienen que
  concordar dejan representable el estado que no debe existir**; uno solo lo hace imposible.
- **El cuerpo de la pull request lo compone un modelo de frontera** (`PullRequestBody`), que fija sus
  encabezados y su orden. Se quedan en castellano: son **contenido del artefacto que lee una persona**,
  en el idioma del issue, no identificadores.

  **La pull request nace lista para revisar, y eso no afloja el control humano.** Lo que hace que el
  merge lo decida una persona es que el programa **no mergea**: se para y termina. Un borrador no anade
  esa garantia y si anade un paso manual que nada recuerda: la pull request queda con todo hecho y sin
  poder fusionarse hasta que alguien se acuerde de sacarla de ahi.
  - **Se asigna a quien esta autenticado**, que es quien conduce el run y quien tiene que mergear, para
    que le aparezca en su lista. Se declara con la forma que resuelve `gh` en la misma llamada, no
    preguntando antes quien eres: una llamada que se puede ahorrar es una llamada que puede fallar.
  - **El commit acredita como co-autor al harness que escribio el codigo**, en un objeto de frontera
    propio y no como una cadena pegada al titulo, porque el **asunto** del commit y el **titulo** de la
    pull request dejan de ser lo mismo en cuanto uno de los dos crece: el puerto expone los dos y el
    caso de uso recibe cada uno por su campo. Lo que **no** se hace es anadirlo como asignado: GitHub
    solo deja asignar colaboradores del repo, asi que seria una llamada que falla o se ignora en
    silencio.

  **Cuatro decisiones sobre ese cuerpo, y ninguna tiene test de contrato**: no hay vocabulario que
  extraer de un cuerpo en prosa, asi que estos parrafos son lo unico que las sostiene.

  1. **Cierra con `Closes #<subissue>`.** Hay **una subissue por slice**, asi que la pull request si
     cierra su issue, y GitHub lo hace solo al fusionar. Con un issue por feature entera esto seria
     mentira, y por eso la referencia depende del formato y no se elige por costumbre.
  2. **No sabe expresar la referencia cross-repo**, porque la subissue le llega como un numero suelto.
     Consecuencia: una slice que viva en otro repo referenciaria ese numero **en el repo de la pull
     request**, que no es donde vive la subissue. No es un olvido: quien conoce los dos repos es quien
     conduce el run, y componer ahi la referencia es mas barato que darle a este modelo una opinion sobre
     repos. Cerrarlo toca las dos piezas, asi que hasta entonces el programa solo entrega correctamente
     slices que viven en el repo de su issue.
  3. **Confirma que los criterios se cumplieron en vez de reproducirlos.** Reproducirlos le da a quien
     revisa lo que ya sabe -los declara la subissue, a un click del `Closes`- y le quita el sitio al *por
     que*, que es todo el trabajo de este cuerpo. Y **donde vive cada test** el programa no lo sabe: el
     informe del implementador trae rutas con su tipo, no un mapa de criterio a test, asi que escribirlo
     seria inventarlo.
  4. **Bajo `## Deuda aceptada` va lo que el implementador declaro haber dejado fuera, junto a los
     hallazgos que sobrevivieron a la vuelta con la que el juez dejo pasar la slice**, que llegan como
     lista y se transportan sin adivinar donde corta una frase. Una lista vacia significa "nada quedo
     fuera", y la seccion solo se emite cuando trae bullets. Los de vueltas anteriores **no** entran:
     pueden haberse corregido despues, y darlos por aceptados seria mentir.

     **Y la deuda llega solo dentro de una invocacion, exactamente como el gasto y por el mismo motivo**:
     no viaja en el `Run` persistido, asi que una invocacion que muera despues de implementar deja a la
     siguiente abriendo la pull request sin `## Deuda aceptada` y sin decir que la hubo. Cerrarlo es la
     misma cirugia que el gasto. Mientras tanto la huella de esa decision es el issue.

  **La intencion inferida se declara en el encabezado.** Cuando la subissue no trae `INTENCION:`, el
  encabezado lo dice; cuando la trae, va plano. La decision es del **formato**, y por eso vive en este
  modelo y no en quien conduce: el dato -declarada o no- ya viaja en lo que le llega. Lo que el programa
  **no** hace es inventarse la prosa que falta: presentar como intencion algo que nadie escribio es justo
  lo que ese encabezado existe para impedir.

## Entrypoints

- Una clase (`Cli`), con `main` como `@classmethod`, que `__main__.py` invoca y que `[project.scripts]`
  declara como el ejecutable `slice-runner`.
- **Es el unico sitio que monta el grafo de dependencias**: elige los adaptadores concretos y los
  inyecta. No hay contenedor de inyeccion: hay un adaptador por puerto, y la costura de test la da el
  constructor. `Cli.run` monta el grafo entero del conductor -seis casos de uso y once puertos- sobre
  **un solo** `Process`, que es tambien la unica costura que necesita su test: doblar ese puerto basta
  para conducir un run sin `gh`, sin `git` y sin harness, y lo que el run hizo o no hizo se lee en el
  `argv` que recibio.
- **Mapea las excepciones tipadas del dominio a codigos de salida**, con `IntEnum`. La respuesta va a
  `stderr` y el resultado a `stdout`, siempre separados: hay tests que comprueban que un fallo no
  escribe nada en `stdout`.
- Los codigos de salida son contrato con quien invoca el programa: **se documentan en la tabla del
  `README.md`** -que un test de contrato compara con el `IntEnum`-, se anaden al final y no se
  reordenan.
- **Un codigo por decision de quien invoca, no uno por excepcion.** La vara para decidir si hace falta
  uno nuevo es: ¿que hace distinto quien lo recibe? De ahi salen los de `run`: el run cerro
  mergeado (`OK`, sigue la siguiente slice), cerro sin mergear (`RUN_UNMERGED`, hay que mirar el issue),
  se agoto la espera con el run vivo -toda espera del run comparte ese codigo, la de la alineacion
  incluida- (`WAIT_EXHAUSTED`, reinvocar es justo lo que toca), los prechecks lo pararon
  (`PRECHECKS_BLOCKED`) y la pull request se cerro sin mergear (`PULL_REQUEST_CLOSED`, reinvocar
  repetiria la espera entera: la decision -reabrirla o dar la slice por muerta- es de una persona). Ese
  ultimo **no cierra el run**: es la otra mitad de "el merge lo decide el usuario", asi que la
  invocacion termina y el run se queda abierto y persistido en `await-merge`, sin `RunState` ni etiqueta
  propios.
  Las excepciones se agrupan por la misma vara: todo lo que significa "el mundo fallo, el estado
  persistido sigue bueno" cae en `RUN_INTERRUPTED` -`gh`, `git`, el foro ilegible, el registro durable-
  y no en un codigo por clase de excepcion.

  **`PROCESS_TIMED_OUT` sale de esa misma vara, no de tener una excepcion mas.** Una
  llamada muerta en su tope no se reinvoca a ciegas -volveria a pagar el tope entero-, asi que la decision
  de quien invoca es distinta de la de `RUN_INTERRUPTED`, donde reinvocar es lo que toca. Lo emite todo
  subcomando que lance un proceso: `verify` tampoco lo colapsa en `NO_USABLE_VERDICT`, porque "el juez
  no dejo veredicto" y "una llamada se colgo" se arreglan mirando sitios distintos. Y lo mapean `verify` y
  `run` -no `main`- porque el `Process` lo inyecta el constructor: mapearlo arriba lo dejaria sin costura
  con la que probarlo.

  **Y por eso el reparto de `run` vive en `_why_the_run_stopped` y no en una cadena de `except`.** Con
  tantos grupos, la cadena pasaba del tope de `return` que mide `PLR0911`; el `match` sobre la excepcion
  deja el reparto entero en un sitio y **la rama generica es `RUN_INTERRUPTED` a proposito**, que es
  literalmente la regla del parrafo de arriba: lo que no tiene codigo propio significa "el mundo fallo, el
  estado persistido sigue bueno". Lo que puede llegar lo acota `Cli.STOPS`, y lo que no este ahi sigue
  saliendo sin capturar, igual que antes.
- **La proyeccion del dominio al codigo de salida es un `match` exhaustivo sin rama generica**
  (`ExitCode.of_the_halt`, como `ExitCode.of` y `IssueLabel.of`): un `Halt` o un `RunState` nuevo rompe
  en `mypy` en vez de caer en un valor por omision. La unica rama que no se puede alcanzar -un cierre
  con el estado en `open`- se agrupa con los cierres sin merge en vez de con el merge, que es el lado
  fail-closed.
- **Una invocacion que el parser rechaza sale con `USAGE_ERROR`, y `--help` con `OK`.** `argparse`
  levanta `SystemExit(2)` para las dos cosas y ese `2` es el codigo que el contrato reserva para "no hay
  veredicto de fiar", asi que un flag mal escrito le contaba a quien invoca que el juez no dejo veredicto.
  `main` traduce ese `SystemExit` mirando su codigo, que es la unica forma de distinguir la ayuda del
  error de uso sin reescribir `argparse`.

## Antipatrones

- Un `cast` para callar a `mypy`.
- `extra="ignore"` en un modelo de frontera. **Una clave desconocida tiene que romper.**
- `strict=True` a nivel de modelo.
- Un `ValidationError` de Pydantic escapando de la capa.
- Duplicar en el programa una regla que ya vive en un script de `skills/` **sin declararlo con su
  motivo** en la seccion de adaptadores: la duplicacion declarada es la decision de esta capa, la
  silenciosa es el fallo.
- `check=True` al lanzar un proceso cuyo `stderr` lleva el motivo del fallo.
- **Lanzar un proceso sin `timeout`**, o lanzarlo con uno que el propio adaptador se inventa en vez de
  recibirlo en los `Budgets`. Una llamada sin tope cuelga el run entero sin diagnostico y sin coste
  acotado.
- Lanzar un proceso **sin pasar por el puerto `Process`**: es donde se aplica el tope, asi que un
  `subprocess` suelto en un adaptador se lo salta.
- Un adaptador que ademas decide politica (reintentos, presupuesto).
