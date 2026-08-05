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
`Modo`, `Ruling`, `Severity`...). Los miembros se serializan como su cadena, asi que ni el formato del
issue ni el JSON de salida cambian, pero las comparaciones y los `choices` de cada interfaz de linea
de comandos salen de un solo sitio.

- Nombre del miembro en mayusculas; valor en minusculas, **salvo que el valor sea dato de un
  contrato** que lo fije de otra forma (`Ruling.PASS = "PASA"`).
- En `argparse`, `choices=[str(x) for x in Enum]`: con `list(Enum)` el mensaje de error muestra el
  `repr` del miembro.
- Codigos de salida de un ejecutable: `IntEnum`, y el mapeo desde el vocabulario del dominio con un
  `match` exhaustivo, para que anadir un miembro rompa en `mypy` en vez de caer en silencio en la
  rama generica.

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
etiqueta de GitHub que escribe la frontera (`infrastructure/run_repository.py`), total o explicito -un
par sin regla no cae en una rama generica, rompe en `mypy` en cuanto se anade un cierre o un paso sin
proyectarlo-. El contrato ya esta medido, no pendiente: `tests/test_skill_contracts.py` comprueba que
todo cierre de `RunState` distinto de `MERGED` (que no lleva etiqueta porque cierra GitHub el issue solo,
via `Closes` de la pull request) proyecta a una de las nueve etiquetas del vocabulario, y que ninguna
etiqueta del vocabulario carece de fuente -sale de una proyeccion del traductor, o es una de fuente
manual-. Hay dos etiquetas de fuente manual: `estado:pendiente`, que escribe una persona a mano al crear
la subissue, y `estado:esperando-alineacion`, que escribe `RunRepository.pause_for_alignment` antes de que
exista ningun `Run` -la pausa de alineacion ocurre fuera de cualquier `(state, step)` que `IssueLabel.of`
pueda conocer, asi que no hay cierre del que proyectarla-.

Dos decisiones mas de `StateMachine` que no son deriva, y estan aqui para que no se "arreglen" hacia el
lado facil:

- **La separacion minima entre ticks es una sola, para los tres tipos de tick.** La prosa solo pone
  numero donde la cuenta es load-bearing -la ventana de gracia de la integracion continua-, y deja los
  demas en "ticks acotados con un timeout razonable". Un segundo campo para el tick del merge seria un
  numero que nadie ha medido; el que hay sale de un caso real medido en dos pull requests, asi que
  gobierna las tres esperas. Consecuencia aceptada: mover el de la ventana mueve tambien la cadencia con
  la que se sondea el merge.
- **El descarte del juez -devolver algo que no es su veredicto- no tiene presupuesto propio, y por tanto
  es el unico bucle de la tabla sin cierre propio.** Es fiel a la prosa: no gasta reintento porque **no
  se ha tocado el codigo**, asi que no es un intento de la fase. Lo que cambia al pasar a programa es
  quien lo acota: antes, la persona mirando; ahora, el presupuesto de coste, que **si** cierra
  (`over-budget` -> `aborted-budget`). Ponerle aqui un numero seria inventar una politica que ninguna
  medicion sostiene; lo que no vale es dejarlo sin declarar.

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
