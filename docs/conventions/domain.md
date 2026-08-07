# Capa de dominio

Value objects, puertos y excepciones. No conoce ninguna otra capa, no hace entrada/salida y no lleva
Pydantic.

## Value objects

- **Dataclasses `frozen=True, kw_only=True, slots=True`.** Sin excepciones: si algo se construia por
  partes y luego se mutaba, se construye una vez al final o se usa `dataclasses.replace`. Es lo que
  hizo falta en `parse_body` y en `comprueba_higiene_pr`.
- Sin sufijo `VO` ni `ValueObject`.
- Datos y, si hace falta, comportamiento propio. **Nada de serializacion**: convertir a las claves de
  un contrato externo es trabajo de la frontera (`docs/conventions/infrastructure.md`).

## Vocabulario cerrado

**`StrEnum`**, no tuplas de `str` (`Estado`, `MotivoBloqueada`, `EstadoCI`, `Severidad`, `Veredicto`,
`Modo`, `Ruling`, `Severity`, `HygieneBreach`, `ProtectedBranch`...). Los miembros se serializan como su
cadena, asi que ni el formato del issue ni el JSON de salida cambian, pero las comparaciones y los
`choices` de cada interfaz de linea de comandos salen de un solo sitio.

- Nombre del miembro en mayusculas; valor en minusculas, **salvo que el valor sea dato de un
  contrato** que lo fije de otra forma (`Ruling.PASS = "PASA"`).
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

**El vocabulario de cierres duplica uno durable, y esta declarado.** `RunState` es una tercera copia -en
ingles- de lo que ya dicen `Estado`/`MotivoBloqueada` en `skills/slice-runner/scripts/issue_body.py` y
`Veredicto` en `skills/slice-runner/scripts/metrics.py`. Es la misma decision que el resto del programa
-**no importa nada de `skills/`**, ver `docs/conventions/infrastructure.md`- y el mismo motivo: el flujo
viejo esta condenado, sus scripts son stdlib puro con otra vara, y acoplarse a ellos para ahorrar la
duplicacion sale mas caro que la duplicacion. El traductor es `IssueLabel.of(state, step)`
(`domain/issue_label.py`): un `match` exhaustivo sobre el par que proyecta cada cierre de `RunState` a la
etiqueta de GitHub que escribe la frontera (`infrastructure/gh_run_repository.py`), total o explicito -un
par sin regla no cae en una rama generica, rompe en `mypy` en cuanto se anade un cierre o un paso sin
proyectarlo-. El contrato ya esta medido, no pendiente: `tests/test_skill_contracts.py` comprueba que
todo cierre de `RunState` distinto de `MERGED` (que no lleva etiqueta porque cierra GitHub el issue solo,
via `Closes` de la pull request) proyecta a una de las nueve etiquetas del vocabulario, y que ninguna
etiqueta del vocabulario carece de fuente -sale de una proyeccion del traductor, o es una de fuente
manual-. Hay dos etiquetas de fuente manual: `estado:pendiente`, que escribe una persona a mano al crear
la subissue, y `estado:esperando-alineacion`, que escribe `GhRunRepository.pause_for_alignment` antes de que
exista ningun `Run` -la pausa de alineacion ocurre fuera de cualquier `(state, step)` que `IssueLabel.of`
pueda conocer, asi que no hay cierre del que proyectarla-.

**`CiStatus` es la tercera copia declarada del mismo tipo.** `domain/ci_status.py` repite en ingles el
vocabulario `EstadoCI` de `skills/slice-runner/scripts/controles.py` (`verde`, `rojo`, `pendiente`,
`sin-checks`, `desconocido`), igual que `RunState` repite a `Estado` y que `StagedHygiene.FORBIDDEN_PREFIXES` repite
sus prefijos, y por el mismo motivo: el programa **no importa nada de `skills/`**. Los dos traductores al
vocabulario con el que se interroga a `StateMachine` viven del lado del destino, como `IssueLabel.of`:
`Outcome.of_the_ci(status)` y `Outcome.of_the_verdict(verdict)`, los dos con `match` exhaustivo y sin rama
generica, para que la regla no acabe siendo un `if` de quien conduce el run. Como las otras dos copias, esta
**esta medida**: `tests/test_skill_contracts.py` empareja los cinco miembros de `CiStatus` con los cinco de
`EstadoCI` **por significado y no por cadena** -uno esta en ingles y el otro en castellano, asi que comparar
los valores pondria `green` frente a `verde` y fallaria con el contrato sano-, de modo que anadir o quitar un
estado en un solo lado pone `make check` en rojo. El emparejamiento se escribe una vez en el propio test,
porque es lo unico de esta duplicacion que no se puede derivar de ninguno de los dos lados.

**La higiene del indice es politica, y sus prefijos prohibidos son una duplicacion declarada mas.**
`StagedHygiene.of(staged=..., declared=...)` (`domain/staged_hygiene.py`) devuelve las ofensas
-`HygieneOffence`, con el path y su `HygieneBreach`- de lo que hay en el indice frente a lo que el
implementador declaro, y la tupla vacia es el indice limpio. Tres decisiones que no son deriva:

- **Un artefacto prohibido lo es aunque este declarado.** `StagedHygiene.FORBIDDEN_PREFIXES` es un
  backstop, no una regla mas del allow-list: si lo pudiera levantar quien declara las rutas, no
  protegeria de nada.
- **Fail-closed sin rama especial.** Con `declared` vacio todo lo staged sale `NOT_DECLARED`, que es lo
  que cae solo de la regla general. Y **"nada staged" no es asunto de esta politica**: eso ya lo dice
  `EmptyIndexError` cuando se va a leer el diff, y reimplementarlo aqui seria un segundo sitio donde
  decidir lo mismo.
- **Los prefijos duplican a proposito los de `skills/slice-runner/scripts/controles.py`**, por el mismo
  motivo que `RunState` duplica a `Estado`: el programa no importa nada de `skills/` (ver
  `docs/conventions/infrastructure.md`), el flujo viejo esta condenado, y acoplarse a el para ahorrar la
  duplicacion sale mas caro que la duplicacion. La copia esta **medida**, no pendiente:
  `tests/test_skill_contracts.py` compara los dos conjuntos, asi que anadir un prefijo en un solo lado
  pone `make check` en rojo.

Cinco decisiones mas de `StateMachine` y de los `Budgets` que le entran no son deriva, y estan aqui para
que no se "arreglen" hacia el lado facil:

- **La separacion minima entre ticks es una sola, para los tres tipos de tick.** La prosa solo pone
  numero donde la cuenta es load-bearing -la ventana de gracia de la integracion continua-, y deja los
  demas en "ticks acotados con un timeout razonable". Un segundo campo para el tick del merge seria un
  numero que nadie ha medido; el que hay sale de un caso real medido en dos pull requests, asi que
  gobierna las tres esperas. Consecuencia aceptada: mover el de la ventana mueve tambien la cadencia con
  la que se sondea el merge.
- **El tope de espera de una invocacion son 30 minutos (`total_wait_seconds`), y acota la invocacion, no
  el run.** La integracion continua de este repo esta medida entre 15 y 33 segundos sobre 25 runs, asi
  que el numero no lo fija ella: lo fija el repo destino peor, y hay uno escrito -un `make test` de ~20
  minutos, en `skills/slice-spec/SKILL.md`- que hay que despejar con margen. Por arriba lo acota la otra
  espera: el merge es **una decision humana**, y 30 minutos es lo bastante corto para que agotarlos
  termine la invocacion en vez de retener el proceso durante horas, que es lo que prescribe el paso 10 de
  `skills/slice-runner/SKILL.md`. **Agotarlo no cierra el run**: lo deja abierto y persistido en su paso,
  con `wait-exhausted` diciendo que reinvocar es justo lo que toca.
- **El tope de una llamada a un proceso externo es una hora (`process_timeout_seconds`), y es un backstop
  contra una llamada que no vuelve, no un valor de ajuste.** Vive en `Budgets` -aunque quien lo aplica sea
  un adaptador- porque es el mismo tipo de dato que los otros: un numero medido con el que se acota una
  espera, y tenerlo aqui es lo que evita que cada adaptador se invente el suyo. Lo mas largo que se ha
  medido llamar son los sobres de `claude -p` de `src/slice_runner/tests/payloads/`, cuyo mayor tarda 51
  segundos, y lo mas largo declarado es el `make test` de ~20 minutos de `skills/slice-spec/SKILL.md`: una
  hora los despeja a los dos con margen, que es lo que se le pide a un backstop -ponerlo bajo no ahorra
  nada, mata un control sano a mitad-.

  **Es un solo numero para las tres clases de llamada** -el harness, los controles y los `git`/`gh`-, por
  el mismo motivo que la separacion entre ticks es una sola: un campo por clase serian dos numeros que
  nadie ha medido. Consecuencia aceptada: un `gh` colgado tarda una hora en morir, cuando por su
  naturaleza sobraban segundos. Sigue siendo acotado, que es lo que el tope existe para garantizar.
- **El descarte del juez -devolver algo que no es su veredicto- no tiene presupuesto propio.** Es fiel a
  la prosa: no gasta reintento porque **no se ha tocado el codigo**, asi que no es un intento de la fase.
  Lo que cambia al pasar a programa es quien lo acota: antes, la persona mirando; ahora, el presupuesto de
  coste del bullet siguiente, que **si** cierra (`over-budget` -> `aborted-budget`). Darle un contador
  propio seria inventar una politica que ninguna medicion sostiene; dejarlo sin ningun cierre seria un
  bucle que paga una llamada al harness por vuelta y no termina nunca.
- **El coste de una slice son 50 dolares (`slice_cost_usd`), y es un backstop contra un bucle sin cierre,
  no un valor de ajuste.** Nacio en 25 $ cuando el registro durable no tenia ni un dolar real y lo unico
  medido eran las llamadas grabadas en `src/slice_runner/tests/payloads/`, cuya mayor son **0.343 $**: dos
  ordenes de magnitud de margen sobre lo unico que se sabia. Ese parrafo prometia re-fijarlo con dolares
  reales en cuanto hubiera muestras, y **esto es ese momento**. Siete slices conducidas por el programa
  miden **5.14, 10.75, 15.07, 25.46 y 27.73 $**, o sea que el numero elegido como techo inalcanzable
  resulto estar *dentro* del rango normal: **dos slices sanas murieron con `abortada:presupuesto`**, y las
  dos justo despues de que el juez devolviera `PASA`, porque el limite se comprueba tras pagar la llamada.
  Un backstop que corta slices sanas no es un backstop, es el cierre espurio contra el que este mismo
  bullet advertia.

  El techo sube a 50 $ **sin tocar que se cuenta**: sigue sumando todas las llamadas del run, y por eso el
  descarte del juez sigue acotado (bullet anterior). Contar solo al implementador abarataria el numero a
  costa de dejar ese bucle sin ningun cierre, que es exactamente lo que ese bullet existe para impedir.

  El otro lado de la misma medicion es que **el implementador fija su modelo** (`ImplementerInvocation.
  MODEL`) en vez de heredar el de quien lanza el run: los 25-28 $ se pagaron con Opus porque ninguna
  invocacion declaraba modelo. El juez **no** lo fija a proposito, y hay test de las dos cosas: el que
  produce se puede permitir el barato porque su trabajo lo revisa otro; el que juzga es el ultimo control
  antes de una pull request, y ahi ahorrar es ahorrar en la garantia.

  Y **un gasto no medido cuenta como agotado**, no como cero: `HarnessSpend` distingue "todavia no se ha
  medido nada" de "cero medido" (`measured`), y lo que no se puede sumar no se puede acotar, asi que un
  harness que jamas deja medicion -el sobre no llego a parsearse- cierra el run en vez de girar gratis
  para siempre. Es la misma eleccion fail-closed que `CiStatus.UNKNOWN`: el precio del falso positivo es
  una reinvocacion, y el del falso negativo es el bucle que este numero existe para cortar.

  **La pregunta se hace por llamada, no por el agregado**, y esa firma es load-bearing:
  `cost_exhausted(call=..., total=...)` mira primero si **esa** llamada dejo medicion y solo despues suma.
  Preguntarselo al agregado tenia el agujero entero dentro: como una llamada sin medicion no anade nada a
  la suma, bastaba **una** medicion previa en la invocacion -el `implement` del propio run- para que el
  total quedase `measured` para siempre, y a partir de ahi cada llamada que muriera sin sobre parseable
  dejaba el total congelado por debajo del limite. El descarte del juez vuelve al mismo paso con
  `wait_seconds=0` y sin presupuesto propio, asi que eso era exactamente el bucle que paga una llamada al
  harness por vuelta y no termina nunca.

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

Los `dict[str, object]` que quedan son todos frontera de serializacion.

## Antipatrones

- Un dataclass del dominio sin `frozen=True, kw_only=True, slots=True`.
- Un `to_dict()` en el dominio. **La traduccion al contrato externo vive en la frontera.**
- Una tupla de `str` como vocabulario cerrado.
- `Optional[Enum]` cuando lo que se modela es un estado ausente: eso es un miembro mas del enum.
- Un `dict` como valor de retorno de una funcion de logica.
- Pydantic en cualquier fichero de `domain/`.
