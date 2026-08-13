# Capa de dominio

Value objects, puertos y excepciones. No conoce ninguna otra capa, no hace entrada/salida y no lleva
Pydantic.

## Value objects

- **Dataclasses `frozen=True, kw_only=True, slots=True`.** Sin excepciones: lo que se construia por
  partes y luego se mutaba, se construye una vez al final o se rehace con `dataclasses.replace`.
- Sin sufijo `VO` ni `ValueObject`.
- Datos y, si hace falta, comportamiento propio. **Nada de serializacion**: convertir a las claves de
  un contrato externo es trabajo de la frontera (`docs/conventions/infrastructure.md`).

## Vocabulario cerrado

**`StrEnum`**, no tuplas de `str` (`Estado`, `MotivoBloqueada`, `EstadoCI`, `Severidad`, `Veredicto`,
`Modo`, `Ruling`, `Severity`, `HygieneBreach`, `ProtectedBranch`...). Los miembros se serializan como su
cadena, asi que ni el formato del issue ni el JSON de salida cambian, pero las comparaciones y los
`choices` de cada interfaz de linea de comandos salen de un solo sitio.

- Nombre del miembro en mayusculas; valor en minusculas, **salvo que el valor sea dato de un
  contrato** que lo fije de otra forma (`Ruling.PASS = "PASS"`).
- En `argparse`, `choices=[str(x) for x in Enum]`: con `list(Enum)` el mensaje de error muestra el
  `repr` del miembro.
- Codigos de salida de un ejecutable: `IntEnum`, y el mapeo desde el vocabulario del dominio con un
  `match` exhaustivo, para que anadir un miembro rompa en `mypy` en vez de caer en silencio en la
  rama generica.
- **Un puerto contesta con el vocabulario, no con un `bool` derivado de el.** `Forum.pull_request_state`
  devuelve `PullRequestState` (`merged`, `open`, `closed`) porque `gh pr view --json state` ya distingue
  los tres. El `merged: bool` que hubo antes colapsaba "cerrada sin mergear" con "todavia abierta", que es
  el mismo fallo que el `Optional[Enum]` del apartado de antipatrones: quien conducia el run tickeaba el
  tope entero esperando un merge que ya no podia llegar, y cada reinvocacion repetia la espera. La
  traduccion desde las cadenas de `gh` vive en la frontera (`docs/conventions/infrastructure.md`).
- **La pertenencia se pregunta contra los valores, no con `in`.** `ProtectedBranch.protects(name)`
  compara contra el `value` de cada miembro: en Python 3.11 -el minimo que declara
  `docs/conventions/architecture.md`- un `name in cls` con una cadena que no es miembro lanza
  `TypeError`, y la guarda que impide commitear en `master` no puede romper por la forma de preguntar
  justo cuando la rama es una cualquiera.

## Puertos

- Interfaces con `ABC` y `@abstractmethod`. Nada mas: sin implementacion por defecto, sin estado.
- El puerto declara lo que el dominio necesita, no lo que el adaptador sabe hacer.

## Politica: la logica pura vive aqui, no en aplicacion

Lo que es **regla exacta** -que paso viene despues de un resultado, cuando se agota un presupuesto- es
un objeto del dominio, no prosa de una skill ni un `if` en un caso de uso. Forma: dataclass frozen con
**su configuracion inyectada** (`StateMachine(budgets=Budgets())`), sin entrada/salida y sin conocer a
nadie. `Budgets` es un value object de configuracion normal: lo construye el entrypoint y entra como
dato, igual que el `Judge` (ver `docs/conventions/application.md`).

- **Total o explicita**: un par de entrada que la politica no describe **lanza** su excepcion, no cae en
  una rama generica. `ImpossibleTransitionError` existe para que un `(paso, resultado)` sin regla se vea
  en el momento y no se confunda con "no pasa nada".
- **Devuelve un value object con el efecto entero**, no un booleano ni un `dict`: `Transition` lleva el
  paso siguiente, el estado en que queda el run y cuantos segundos hay que esperar. Un consumidor que
  tuviera que recomponer eso volveria a tener politica repartida.
- **Se cubre desde fuera**, como todo el dominio: la tabla de `(paso, resultado)` entra por el
  subcomando que la expone. No hay tests unitarios de dominio (`docs/conventions/testing.md`).

**El vocabulario de cierres duplica uno durable, y esta declarado.** `RunState` es una copia declarada
-en ingles- de `Veredicto` en `skills/slice-runner/scripts/metrics.py`. (Duplicaba tambien
`Estado`/`MotivoBloqueada` de `issue_body.py`, retirado ya con el flujo
viejo por no tener consumidor.) Es la misma decision que el resto del programa -**no importa nada de
`skills/`**, ver `docs/conventions/infrastructure.md`- y el mismo motivo: sus scripts son stdlib puro
con otra vara, y acoplarse a ellos para ahorrar la duplicacion sale mas caro que la duplicacion. El
traductor es `IssueLabel.of(state, step)`
(`domain/issue_label.py`): un `match` exhaustivo sobre el par que proyecta cada cierre de `RunState` a la
etiqueta de GitHub que escribe la frontera (`infrastructure/gh_run_repository.py`), total o explicito -un
par sin regla no cae en una rama generica, rompe en `mypy` en cuanto se anade un cierre o un paso sin
proyectarlo-. El contrato ya esta medido, no pendiente: `test_domain_vocabulary_contracts.py` comprueba que
todo cierre de `RunState` distinto de `MERGED` (que no lleva etiqueta porque cierra GitHub el issue solo,
via `Closes` de la pull request) proyecta a una etiqueta del vocabulario, y que ninguna etiqueta del
vocabulario carece de fuente -sale de una proyeccion del traductor, o es de fuente manual-. **De fuente
manual es la que se escribe fuera de cualquier `(state, step)` que `IssueLabel.of` pueda conocer**, que
es lo que pasa antes de que exista ningun `Run`. Una etiqueta nueva sin proyeccion ni fuente manual
declarada pone `make check` en rojo.

**`CiStatus` repite en ingles el vocabulario `verde`/`rojo`/`pendiente`/`sin-checks`/`desconocido`.**
Hasta que se retiro con el flujo viejo, `domain/ci_status.py` era la copia declarada de `EstadoCI` en
`controles.py`, igual que `RunState` repite a `Veredicto` y que
`StagedHygiene.FORBIDDEN_PREFIXES` repetia los suyos: el motivo era que el programa **no importa nada
de `skills/`**. Retirado el script, `CiStatus` es el unico sitio donde vive ese vocabulario. Los dos
traductores al vocabulario con el que se interroga a `StateMachine` viven del lado del destino, como
`IssueLabel.of`: `Outcome.of_the_ci(status)` y `Outcome.of_the_verdict(verdict)`, los dos con `match`
exhaustivo y sin rama generica, para que la regla no acabe siendo un `if` de quien conduce el run.

**La higiene del indice es politica, y sus prefijos prohibidos son una duplicacion declarada mas.**
`StagedHygiene.of(staged=..., declared=...)` (`domain/staged_hygiene.py`) devuelve las ofensas
-`HygieneOffence`, con el path y su `HygieneBreach`- de lo que hay en el indice frente a lo que el
implementador declaro, y la tupla vacia es el indice limpio. Las decisiones que no son deriva:

- **Un artefacto prohibido lo es aunque este declarado.** `StagedHygiene.FORBIDDEN_PREFIXES` es un
  backstop, no una regla mas del allow-list: si lo pudiera levantar quien declara las rutas, no
  protegeria de nada.
- **Un rechazo de higiene no gasta presupuesto de controles.** **Son cosas distintas**: un control rojo
  es codigo que falla y lo puede arreglar otra vuelta del implementador; un rechazo de higiene es un
  informe incompleto -toco ficheros que no declaro- y no dice nada sobre si el codigo esta bien. Por eso
  tiene resultado propio (`Outcome.HYGIENE_REJECTED`), contador propio y presupuesto propio, y agotarlo
  cierra el run con un estado que nombra la higiene y no los controles. **Dos causas que no se arreglan
  igual no comparten contador**, aqui y en los descartes del juez.
- **Fail-closed sin rama especial.** Con `declared` vacio todo lo staged sale `NOT_DECLARED`, que es lo
  que cae solo de la regla general. Y **"nada staged" no es asunto de esta politica**: eso ya lo dice
  `EmptyIndexError` cuando se va a leer el diff, y reimplementarlo aqui seria un segundo sitio donde
  decidir lo mismo.
- **Los prefijos duplicaban a proposito los de `controles.py`**, por el
  mismo motivo que `RunState` duplica a `Veredicto`: el programa no importa nada de `skills/` (ver
  `docs/conventions/infrastructure.md`). El script se retiro con el flujo viejo por no tener consumidor,
  asi que `StagedHygiene.FORBIDDEN_PREFIXES` es hoy el unico sitio donde viven estos prefijos.

Las decisiones de `StateMachine` y de los `Budgets` que le entran tampoco son deriva, y estan aqui para
que no se "arreglen" hacia el lado facil. **Los valores concretos viven en `Budgets`, y de donde sale cada
uno esta en `docs/design-notes.md`**: aqui va la regla que los gobierna, no la medicion que los fijo.

- **Un numero por concepto, no uno por caso.** Hay una sola separacion minima entre ticks para todas las
  esperas y un solo tope para todas las clases de llamada a un proceso externo. Partirlos por caso serian
  numeros que nadie ha medido, y un numero sin medicion no es una regla: es una preferencia. Consecuencia
  aceptada, y se acepta a proposito: mover el de la ventana mueve tambien la cadencia del sondeo del
  merge, y un `gh` colgado tarda en morir lo mismo que una suite entera.
- **El tope de espera acota la invocacion, no el run.** Agotarlo **no cierra** nada: deja el run abierto y
  persistido en su paso, diciendo que reinvocar es justo lo que toca.
- **La espera tiene dos topes, y eso no rompe el bullet de arriba: lo aplica.** Esperar a la integracion
  continua y esperar a una persona **no son el mismo concepto**, aunque los dos se midan en segundos y
  durante un tiempo compartieran numero. A la CI se la espera porque **esta trabajando**, y su tope existe
  para cazarla **colgada**: media hora es de sobra, y pasado eso el numero ya no dice "ten paciencia" sino
  "algo va mal". A una persona se la espera porque **esta en otra cosa**, y ahi no hay nada que cazar: un
  `-GO` que tarda media manana es el flujo funcionando, no una anomalia. Un solo numero obliga a elegir
  entre no detectar nunca una CI colgada o matar runs sanos por ir a comer, y **elegia lo segundo**.
- **Y el contador se reinicia en cada paso, que es lo que hace honestos a los dos topes.** Con un
  acumulador unico para todo el run, **el ultimo que espera paga lo que gastaron los demas**: medido en la
  slice-10 de este repo el 2026-08-13, 42 ticks esperando el `-GO` y 2 la CI dejaron **16** para el merge
  -8 minutos de los 30-, y el run murio en `WAIT_EXHAUSTED` con la pull request sana y a punto de
  mergearse. Nada de eso se leia en el tope: decia 30 minutos y entregaba 8, con el reparto dependiendo de
  lo que una persona hubiera tardado antes. Un tope que solo se cumple si nadie se entretiene aguas arriba
  no acota nada.
- **El tope por llamada vive en `Budgets` aunque quien lo aplique sea un adaptador**, porque es el mismo
  tipo de dato que los demas: un numero medido con el que se acota una espera. Tenerlo aqui es lo que
  evita que cada adaptador se invente el suyo.
- **El descarte del juez -devolver algo que no es su veredicto- no tiene presupuesto propio.** No gasta
  reintento porque **no se ha tocado el codigo**, asi que no es un intento de la fase. Quien lo acota es el
  presupuesto de coste, que **si** cierra. Darle un contador propio seria inventar una politica que
  ninguna medicion sostiene; dejarlo sin ningun cierre seria un bucle que paga una llamada al harness por
  vuelta y no termina nunca.
- **El presupuesto de coste impide la siguiente llamada; no tira la que ya se pago.** Un veredicto que
  aprueba nunca se convierte en `over-budget` -entregar no cuesta harness-, y la llamada siguiente se corta
  **antes** de invocar, no despues de pagarla. Las dos comprobaciones conviven a proposito: la de despues
  cierra el bucle de descartes del bullet anterior, la de antes es la que impide tirar una aprobacion.
- **La pregunta del coste se hace por llamada, no por el agregado**, y esa firma es load-bearing: se mira
  primero si **esa** llamada dejo medicion y solo despues se suma. Al agregado se le puede preguntar
  eternamente sin que conteste que no, porque lo que no se mide no suma.
- **Un gasto no medido cuenta como agotado**, no como cero: lo que no se puede sumar no se puede acotar.
  Es la misma eleccion fail-closed que el indeterminado de la integracion continua: el precio del falso
  positivo es una reinvocacion, y el del falso negativo es el bucle que el tope existe para cortar.
- **Lo que se cuenta son todas las llamadas del run.** Contar solo al implementador abarataria el numero a
  costa de dejar sin cierre el bucle del descarte.

## Excepciones

- Nombradas por lo que pasa, no por donde: `InvalidVerdictError`, `EmptyIndexError`,
  `UnresolvableRepoOrBaseError`.
- El catalogo es el de las excepciones **del dominio**. Un puerto que solo consume la infraestructura
  lleva la suya con el (`ProcessNotRunnableError`, en `infrastructure/process.py`): esta declarado con su
  motivo en `docs/conventions/architecture.md`.
- Jerarquia cuando el consumidor necesita distinguir: `EmptyIndexError` y
  `UnresolvableRepoOrBaseError` heredan de `DiffNotReadableError` porque la interfaz de linea de
  comandos les da codigos de salida distintos, y quien no distingue captura la de arriba.
- Heredan del tipo que corresponde (`ValueError`, `OSError`), no de `Exception` a secas.

## Nada de `dict` crudo como valor de retorno de logica

Un `dict` que cruza dos funciones propias se lee con `.get()` en el consumidor, y ahi una clave mal
escrita y una ausente dan lo mismo -era el fallo de `build_scorecard` y de `_slice_info`, que ademas
obligaba a tres `assert isinstance(...)` en produccion solo para `mypy`-.

Los `dict[str, object]` que quedan son todos frontera de serializacion, con una excepcion declarada:
`ClosedSliceRecord.budgets`/`models_by_role` (`domain/closed_slice_record.py`) tambien llegan como
`dict[str, object]`, sin tipar contra `Budgets`/`RoleModels`. Es la relectura del mismo campo que
`docs/conventions/infrastructure.md` ya declara para `MetricsEntryPayload` en la escritura, y el motivo
es el mismo: la fila viene de un registro durable historico que pudo escribirse con una forma distinta
de esos dos value objects, y reconstruirlos aqui romperia con cualquier clave anadida, renombrada o
ausente entre versiones. Ninguna logica de dominio ni de aplicacion los destructura -
`ListClosedSlices.execute` los reenvia enteros y la vista solo los menciona como hueco declarado-; el
unico consumidor es la frontera de serializacion de salida (`ClosedSliceRecordPayload`), que es donde
de verdad viven.

## Antipatrones

- Un dataclass del dominio sin `frozen=True, kw_only=True, slots=True`.
- Un `to_dict()` en el dominio. **La traduccion al contrato externo vive en la frontera.**
- Una tupla de `str` como vocabulario cerrado.
- `Optional[Enum]` cuando lo que se modela es un estado ausente: eso es un miembro mas del enum.
- Un `dict` como valor de retorno de una funcion de logica.
- Pydantic en cualquier fichero de `domain/`.
