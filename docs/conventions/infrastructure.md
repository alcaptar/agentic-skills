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
- **Un `alias` por campo, y de ahi salen las tres cosas**: el `--json-schema` que se le manda al juez,
  la validacion de lo que devuelve, y el JSON que emite la interfaz de linea de comandos. Antes eran
  tres copias cosidas a mano y existia un test de contrato solo para que no divergieran.
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

### El `alias` traduce; cuando no hay nada que traducir, no se escribe

`VerdictPayload` lleva `alias` en cada campo porque el contrato del juez esta en castellano y el codigo
en ingles. El contrato de `explain` (`RunPayload`, `TransitionPayload`) y el de `run`
(`ConductedSlicePayload`) **los fijamos nosotros y estan en
ingles**, asi que la clave del contrato ya es el nombre del campo y un `alias` identico solo seria ruido
que hay que mantener en dos sitios. `by_alias=True` cae en el nombre del campo cuando no hay alias, con
lo que el esquema, la validacion y la salida siguen saliendo de un solo sitio, que es lo que la regla
protege.

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
  `Process`, y valida el veredicto con sus propios modelos. Hubo una version que reutilizaba
  `escribe_diff_bundle` y `valida_veredicto` de `controles.py` para no duplicar logica, y el resultado
  fue peor: obligaba a que el programa arrastrase el `pythonpath` del script, a escribir un `files.txt`
  que solo el flujo viejo necesita, y a pasar el veredicto por un validador que Pydantic ya hacia
  redundante -de `valida_veredicto` solo quedaba util un invariante, que ahora vive en `Verdict`, donde
  le toca-. **Acoplar el flujo nuevo al viejo para ahorrar duplicacion sale mas caro que la
  duplicacion**, porque el viejo esta condenado: el rango del diff son tres flags y su motivo esta en
  las convenciones, no en el codigo del script.
- **El juez es un objeto, no un prompt suelto.** `Judge(rubric, tools, readable)` es un value object del
  dominio y agrupa **todo lo que define al juez**; quien lo construye con la rubrica de este repo es
  `src/slice_runner/infrastructure/slice_verifier_judge.py`, y el entrypoint lo inyecta al caso de uso.
  La forma viene del agente raiz de `roman_expert/chat_agents` en
  `mercadona/mo.staff.django-playground`, y **sustituye a un `PromptProvider`** que solo devolvia texto:
  con la rubrica detras de un puerto, las herramientas como constante de `JudgeInvocation` y los
  directorios legibles derivados del repo dentro del `argv`, lo que definia al juez vivia en tres capas y
  nada obligaba a que cuadrase -la rubrica ordenaba cargar skills que el juez no podia leer, y el
  veredicto salia igual de limpio-. Un puerto para un valor constante era indireccion; el invariante
  necesitaba un objeto.
- **El texto de la rubrica se queda en infraestructura**, no en la factoria de aplicacion como en el chat
  de agentes de ese repo: aqui el prompt es lo que se le manda a **un ejecutable concreto** por su
  entrada estandar, con su esquema y sus flags, y cambia con la receta medida contra `claude -p`. Que la
  capa que conoce el harness sea la misma que redacta lo que el harness recibe es lo que evita que
  aplicacion tenga opinion sobre el transporte. `agents/slice-verifier.md` es del **flujo viejo** y se
  queda congelado: el programa no lo lee. Son dos copias de la rubrica a proposito, con la del programa
  diciendo la verdad sobre lo que el programa manda.
- **La metodologia del implementador tiene la misma duplicacion declarada, por el mismo motivo.**
  `SliceImplementerBrief` (`src/slice_runner/infrastructure/slice_implementer_brief.py`) es lo que el
  programa le manda a `claude -p` por su entrada estandar, con su propio `TOOLS` y su propio texto de
  metodologia. `agents/slice-implementer.md` es del **flujo viejo** y se queda congelado igual que
  `agents/slice-verifier.md`: el programa no lo lee. Son dos copias del brief a proposito, con la del
  programa diciendo la verdad sobre lo que el programa manda.
- **Lo que no cambia entre invocaciones es constante; los datos de la slice los compone la invocacion.**
  `SliceImplementerBrief.TEXT` y la rubrica de `SliceVerifierJudge` son texto fijo, y `## Datos de la
  slice` y `## Datos del run` los redactan `ImplementerInvocation` y `JudgeInvocation` a partir del
  `Assignment` y del `SliceUnderReview` que reciben. **Aplicacion no compone texto de prompt**: pasa
  objetos del dominio y es la frontera la que decide como se escriben, por el mismo motivo por el que el
  texto fijo vive aqui. Y los dos prompts **cierran con el dato**, nunca con la metodologia: lo variable
  al final es lo que evita que un delimitador tenga que sobrevivir a su propio contenido -en el juez, el
  diff es literalmente lo ultimo del prompt-.

  Las dos invocaciones llevan **su propio `_counted`** -el par "encabezado con cuantos son" mas una linea
  por entrada- en vez de compartirlo, por el mismo motivo por el que `ClaudeConfig` no existio hasta que
  tuvo tres consumidores (bullet siguiente): lo que comparten no es una regla del programa sino la forma
  de una lista, cada prompt es un contrato con un agente distinto y **nada exige que se parezcan**, asi
  que extraerlas hoy fijaria un parecido que no es invariante. Con un tercer prompt se extrae, y esa
  condicion ya se ha cobrado una vez, asi que no es una promesa que nadie piense cumplir.

  **Hay dos invocadores del juez y solo uno llena esos campos.** `ConductSlice._judging` los llena
  enteros -senal, criterios y fuentes de la slice, y el checklist del issue-, porque el conductor tiene
  el issue delante. `Cli._params`, el del subcomando `verify` suelto, construye el `VerifySliceParams`
  con `signal=""` y las tres tuplas a cero porque por el `argv` solo recibe repo, base e identificador,
  y ese sigue siendo un camino vivo -es como se juzga un diff a mano, sin montar un run-. La
  consecuencia es que un `verify` suelto emite `- criterios de aceptacion (0):`, y **eso no es un
  transitorio que caduque**: es lo que significa juzgar sin issue. Por eso la rubrica **describe la
  carga en vez de prometerla llena**: dice que los campos viajan siempre, que pueden venir vacios y que
  un campo vacio es un insumo que no ha llegado -que el juez reporta como falta de dato, no como item
  conforme-. Lo que **no** se hace es volver a escribir que esos insumos no existen: la afirmacion falsa
  no es "puede venir vacio", es "nunca llega". Y los campos entran **sin default** en
  `VerifySliceParams` a proposito, que es lo que obligo al conductor a llenarlos en vez de heredar el
  vacio en silencio.
- **La raiz de configuracion de la herramienta la resuelve `ClaudeConfig`** (`CLAUDE_CONFIG_DIR`, o
  `~/.claude` expandido, con la variable vacia tratada como ausente). La comparten `LocalSkillLibrary`
  -que lee los dos arboles de la vara- y `MetricsInvocation` -que resuelve la ruta del script del
  registro durable-, porque lo que comparten no es una regla del programa sino **la convencion de Claude
  Code sobre donde vive su configuracion**: de ahi que viva en un objeto propio y no colgada de uno de
  los dos adaptadores. Se extrajo al aparecer el tercer consumidor, que es la condicion que la
  duplicacion anterior se habia puesto a si misma. **`LocalCorpus` se queda con su copia**, y eso es
  deuda declarada y abierta, no precedente: migrarla obliga a renombrar la constante por la que **todos**
  los tests que ejecutan una verificacion mantienen la suite fuera del home real, que es mas superficie
  tocada de la que ha pedido ninguna slice; se hace entera cuando se toque ese adaptador, no a medias.
- **`LocalCorpus.record` escribe a disco sin red, y un `OSError` suyo sale del programa sin mapear.** La
  recogida del corpus (`src/slice_runner/infrastructure/local_corpus.py`) ocurre en el camino feliz y
  **despues** de que exista el veredicto, asi que un sistema de ficheros que no deje anexar tira una
  verificacion ya pagada -el juez ya corrio- y el proceso sale por la excepcion con `1`, que es
  precisamente el codigo que el contrato reserva para el veto: quien invoca no puede distinguir "el juez
  veta" de "no se pudo escribir el corpus". Se acepta porque la alternativa hoy es peor: **decidir aqui
  que hacer con el fallo de escritura seria inventar una politica que ningun criterio pidio**, y un
  adaptador que decide politica es antipatron declarado de esta misma capa. El precedente vivo es
  `LocalControlRunner.run` (`src/slice_runner/infrastructure/local_control_runner.py`), que escribe su log
  igual de desprotegido. Cuando se cierre, se cierra **decidiendo la politica** -si el corpus es
  best-effort, si su fallo es un cierre propio del run, y con que codigo de salida se distingue-, no
  capturando el `OSError` a escondidas dentro del adaptador.
- **El registro durable lo escribe `metrics.py` como subproceso, y su vocabulario esta duplicado a
  proposito.** `MetricsScriptLog` implementa el puerto `MetricsLog` invocando el script por el puerto
  `Process`, no importandolo: el programa no importa nada de `skills/` (arriba), y ademas el formato del
  log -que sobrevive a los runs y tiene historico escrito- sigue teniendo **un solo escritor**.
  Consecuencia aceptada: los tres vocabularios del cierre existen dos veces -en ingles dentro del programa
  (`RunState`, `DiscardCause`) y con las palabras del log en la frontera (`DurableVerdict`, `DurableCi`,
  `DurableDiscardCause`, en `metrics_invocation.py`)-, con un `match`
  exhaustivo entre las dos, como `IssueLabel.of`: un cierre nuevo rompe en `mypy` en vez de caer en una
  rama generica, y un run que **no** ha cerrado lanza `RunNotClosedError` en vez de escribir una fila. La
  duplicacion la **mide** `tests/test_skill_contracts.py`, que compara los tres conjuntos y ademas pasa el
  argv que construye el programa por el `argparse` del script: un flag renombrado solo se veria al cerrar
  una slice, que es justo el momento en que un fallo pierde la fila.
- **El programa no escribe ningun numero que no venga del harness.** Del sobre salen coste en dolares,
  turnos y duracion, sumados por slice; `--duracion-s` (reloj de pared) y `--coste-tokens` **no se pasan**,
  porque aqui nadie los mide y no hay puerto de reloj. De ahi que el gasto sea un value object que
  distingue "todavia no se ha medido nada" de "cero medido" (`HarnessSpend.measured`): con nada medido, los
  tres flags no viajan y el script no escribe la clave. Y **todas** las llamadas cuentan, tambien las que
  acaban en excepcion -si no, una fila con tres descartes escribiria un coste sistematicamente por debajo-:
  una vez parseado el sobre, `HarnessOutput.measuring()` cuelga el gasto de la llamada de cualquier
  `MeasuredCallError` que salga del bloque (veredicto incoherente, `is_error`, permiso denegado, informe
  invalido), y solo esa capa puede hacerlo porque es la unica que ve el sobre. Si el sobre **no** llego a
  parsearse no hay nada que colgar y la excepcion sale con `spend` en `None`: eso es "no medido", no un cero.

  **Ese invariante se cumple dentro de una invocacion, no entre invocaciones, y eso es deuda declarada.**
  El gasto lo acumula `ConductSliceProgress.spends`, que nace vacio en cada `slice-runner run`, y el `Run`
  persistido en la subissue **no lo lleva**. Consecuencia concreta: cualquier slice que haya necesitado
  reinvocarse escribe una fila con el coste de la **ultima** invocacion solamente -y con cero si esa
  invocacion no llamo al harness, como la que solo espera el merge-. Cerrarlo es meter el gasto en el `Run`
  persistido, o sea **tocar el formato del estado durable** (`SubissueBody`), que lo leen tambien todas las
  subissues ya abiertas: se hace entero y con su slice, no a medias. Mientras tanto, el presupuesto de
  coste (`docs/conventions/domain.md`) acota **la invocacion**, que es donde el gasto si esta completo.

  **Deuda vecina, del mismo formato durable: un merge entre invocaciones deja el run sin cerrar.** Si la
  persona mergea la pull request cuando no hay ninguna invocacion corriendo, el `Closes #N` de la pull
  request cierra la subissue, `SliceQueue` deja de considerarla ejecutable y el run **nunca llega a
  cerrarse** ni escribe su fila durable. La slice-17 (`encadenar-deploy-watch`) encadeno `deploy-watch`
  solo en el camino en que el propio run detecta el merge mientras esta corriendo (`_closing`, alcanzable
  unicamente desde `_conducting`); ese camino no llega a este escenario, porque `Prechecks.of_the_subissue`
  corta antes con `PrecheckOutcome.SUBISSUE_ALREADY_CLOSED` en cuanto `subissue.state is IssueState.CLOSED`.
  Detectar el merge de un run que GitHub ya cerro entre invocaciones sigue sin construirse: se declara y no
  se construye.
- **La ruta del script sale de `CLAUDE_CONFIG_DIR`, no del repo** (`ClaudeConfig`, el objeto del
  bullet de arriba): la slice puede vivir en otro repo, donde no hay `skills/` del que colgar una ruta
  relativa.
- Un codigo de salida distinto de cero **es un dato**, no una excepcion: se lanza el proceso con
  `check=False` y el adaptador interpreta, porque el motivo esta en `stderr` y una excepcion lo borra.
- **`GhCi` clasifica la respuesta de `gh pr checks`, y su clasificador es una copia declarada del de
  `skills/slice-runner/scripts/controles.py`.** Tres decisiones que no son deriva, y estan escritas aqui para
  que no se "arreglen" hacia el lado facil mas adelante:

  1. **Se duplica el clasificador en vez de invocar el subcomando `ci-status` del script como subproceso.** El
     programa no importa nada de `skills/` (arriba), y el precedente de lanzar un script por subproceso
     -`MetricsScriptLog` con `metrics.py`- existe por un motivo que **aqui no aplica**: el registro durable
     tiene historico escrito y necesita un solo escritor, asi que la copia seria un segundo escritor del mismo
     fichero. Clasificar la respuesta de `gh` no escribe nada ni recuerda nada entre llamadas: es una funcion
     pura, y de una funcion pura la copia solo puede divergir en la regla. Esa divergencia es la que mide
     `tests/test_skill_contracts.py`, comparando los cinco estados y los tres conjuntos de `bucket`.
  2. **El codigo de salida de `gh pr checks` no se usa: se clasifica el `stdout`.** `gh` sale distinto de cero
     con checks en rojo, con checks pendientes y con una pull request que no existe, asi que el codigo no
     distingue "rojo" de "todavia no" de "no consta". El bullet de arriba dice que un codigo distinto de cero
     es un dato; aqui es un dato que **no dice nada**, y el unico que decide es la salida.
  3. **Un `ValidationError` cae en `CiStatus.UNKNOWN` en vez de en una excepcion**, al contrario que la regla
     general de la capa. Vale **porque el vocabulario del puerto ya tiene el miembro que significa "no se pudo
     medir"**: lanzar seria inventar un segundo camino para lo que `UNKNOWN` ya dice, y quien conduce el run
     tendria que traducirlo de vuelta a ese mismo miembro. Justo por eso **no es permiso general para tragarse
     validaciones**: donde el vocabulario no cubra "no consta", un `ValidationError` se sigue traduciendo a la
     excepcion del dominio. Y no relaja nada, porque `UNKNOWN` es fail-closed: una respuesta que no se lee -no
     es JSON, no es un array, o trae una clave que no pedimos- es `UNKNOWN` y **jamas** "todavia no hay
     checks", que es el fallo que colgo un smoke real durante cuatro minutos con la integracion continua ya
     verde.
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
- **El cuerpo de la pull request duplica a proposito el formato del paso 8 de
  `skills/slice-runner/SKILL.md`.** `PullRequestBody` (`infrastructure/pull_request_body.py`) compone los
  mismos encabezados y en el mismo orden, y es la misma duplicacion declarada que la de la rubrica del juez
  y la del brief del implementador, por el mismo motivo -el flujo viejo esta condenado y el programa no lee
  sus `.md`-. Los encabezados se quedan en castellano: son **contenido del artefacto que lee una persona**,
  en el idioma del issue, no identificadores. Y `gh pr create` va siempre con `--draft`, porque el merge lo
  decide una persona (ver `CLAUDE.md`).

  **Diverge del paso 8 en tres cosas, y las tres son deliberadas.** Al contrario que la duplicacion de los
  prefijos prohibidos -que `tests/test_skill_contracts.py` mide-, **esta no tiene test de contrato**: no hay
  vocabulario que extraer de un cuerpo en prosa, asi que estos tres parrafos son lo unico que la sostiene y
  hay que moverlos a mano cuando se mueva el paso 8.

  1. **Cierra con `Closes #<N>` donde el paso 8 pone `Part of #<N>`.** En el formato nuevo hay **una
     subissue por slice**, asi que la pull request de la slice si cierra su issue; en el viejo el issue es
     la feature entera y cerrarlo con una slice seria mentir.
  2. **No sabe expresar la forma cross-repo `Part of <org>/<repo-del-issue>#<N>`**, porque `subissue: int`
     es un numero suelto. Consecuencia: una slice con `REPO:` a otro repo referenciaria ese numero **en el
     repo de la pull request**, que no es donde vive la subissue. No es un olvido: quien conoce el repo del
     issue y el de la slice es quien conduce el run (la slice-09), y que la referencia se componga ahi es
     mas barato que darle a este modelo una opinion sobre repos. Pero **el conductor solo no basta**: con un
     `subissue: int` no hay forma de pasarle una referencia entera, asi que cerrar esta divergencia toca las
     dos piezas -el campo de este modelo y quien lo rellena-. Hasta que eso pase, el programa solo entrega
     correctamente slices que viven en el repo de su issue.
  3. **La seccion de deuda no la rellena ningun camino, y el insumo que haria falta no existe todavia.**
     `SlicePullRequest.body` pasa `debt=()` siempre, asi que `## Deuda aceptada` no se escribe nunca -la
     seccion solo se emite si trae bullets, que es lo que el paso 8 pide-. Lo unico que el programa tiene
     hoy sobre lo que se decidio **no** arreglar es `Implementation.left_out`, prosa libre del
     implementador: convertirla en bullets seria adivinar donde corta una frase, y quedarse con los
     hallazgos `media`/`baja` del veredicto seria escribir como aceptado lo que quiza si se corrigio en la
     vuelta siguiente. Cerrarlo pide un insumo estructurado -que el informe del implementador declare su
     deuda como lista, no como parrafo-, o sea tocar el contrato del brief; hasta entonces la huella de
     esa decision es el issue y no la pull request.

  **Lo que si esta construido es el interruptor de la intencion**, que aqui fue divergencia hasta que
  entro el conductor: `PullRequestBody` emite `## Intencion (inferida del issue, no declarada)` cuando la
  subissue no trae `INTENCION:` -que es como `SubissueBody` deja el campo, vacio- y el encabezado plano
  cuando si la trae. La decision es del **formato**, y por eso vive en este modelo y no en quien conduce:
  el dato -declarada o no- ya viaja dentro del `SubIssue` que le llega. Lo que el programa **no** hace es
  inventarse la prosa que falta: con la intencion sin declarar, el encabezado lo dice y la seccion se
  queda vacia, porque presentar como intencion algo que nadie escribio es justo lo que ese encabezado
  existe para impedir.

## Entrypoints

- Una clase (`Cli`), con `main` como `@classmethod`, que `__main__.py` invoca y que `[project.scripts]`
  declara como el ejecutable `slice-runner`.
- **Es el unico sitio que monta el grafo de dependencias**: elige los adaptadores concretos y los
  inyecta. No hay contenedor de inyeccion: hay un adaptador por puerto, y la costura de test la da el
  constructor. `Cli.run` monta el grafo entero del conductor -seis casos de uso y nueve puertos- sobre
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
  uno nuevo es: ¿que hace distinto quien lo recibe? De ahi salen los seis de `run`: el run cerro
  mergeado (`OK`, sigue la siguiente slice), cerro sin mergear (`RUN_UNMERGED`, hay que mirar el issue),
  espera a una persona (`AWAITING_ALIGNMENT`, reinvocar no sirve), se agoto la espera con el run vivo
  (`WAIT_EXHAUSTED`, reinvocar es justo lo que toca), los prechecks lo pararon (`PRECHECKS_BLOCKED`) y la
  pull request se cerro sin mergear (`PULL_REQUEST_CLOSED`, reinvocar repetiria la espera entera: la
  decision -reabrirla o dar la slice por muerta- es de una persona). Ese ultimo **no cierra el run**: es
  la otra mitad de "el merge lo decide el usuario", asi que la invocacion termina y el run se queda
  abierto y persistido en `await-merge`, sin `RunState` ni etiqueta propios.
  Las excepciones se agrupan por la misma vara: todo lo que significa "el mundo fallo, el estado
  persistido sigue bueno" cae en `RUN_INTERRUPTED` -`gh`, `git`, el foro ilegible, el registro durable-
  y no en un codigo por clase de excepcion.
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
- Duplicar en el programa una regla que ya vive en `controles.py` **sin declararlo con su motivo** en la
  seccion de adaptadores: la duplicacion declarada es la decision de esta capa, la silenciosa es el fallo.
- `check=True` al lanzar un proceso cuyo `stderr` lleva el motivo del fallo.
- Un adaptador que ademas decide politica (reintentos, presupuesto).
