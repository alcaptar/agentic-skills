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

**`StrEnum`**, no tuplas de `str`. Los miembros se serializan como su cadena, asi que ni el formato del
issue ni el JSON de salida cambian, pero las comparaciones y los `choices` de cada interfaz de linea de
comandos salen de un solo sitio.

- Nombre del miembro en mayusculas; valor en minusculas, **salvo que el valor sea dato de un contrato**
  que lo fije de otra forma.
- En `argparse`, `choices=[str(x) for x in Enum]`: con `list(Enum)` el mensaje de error muestra el
  `repr` del miembro.
- Codigos de salida de un ejecutable: `IntEnum`, y el mapeo desde el vocabulario del dominio con un
  `match` exhaustivo, para que anadir un miembro rompa en `mypy` en vez de caer en silencio en la
  rama generica.
- **Un puerto contesta con el vocabulario, no con un `bool` derivado de el.** Un booleano colapsa
  estados que se arreglan distinto, y quien lo consume no puede separarlos: el que decia si algo estaba
  fusionado fundia "cerrado sin fusionar" con "todavia abierto", y quien conducia el run tickeaba el tope
  entero esperando algo que ya no podia llegar. **Y si la misma llamada ya distingue las dos cosas, eso no
  es un segundo puerto ni una segunda llamada: es un campo mas de una respuesta que ya se estaba
  leyendo.** La traduccion desde las cadenas de la herramienta vive en la frontera.
- **La pertenencia se pregunta contra los valores, no con `in`.** En la version minima de Python que
  declara `docs/conventions/architecture.md`, un `nombre in cls` con una cadena que no es miembro lanza
  `TypeError`, asi que una guarda no puede romper por la forma de preguntar justo cuando el valor es uno
  cualquiera.
- **Un vocabulario que tambien exista en codigo que no es referencia se declara y se mide con un
  contrato, nunca se comparte por import** (ver `docs/conventions/infrastructure.md`). Su traductor vive
  **del lado del destino**, con `match` exhaustivo y sin rama generica, para que la regla no acabe siendo
  un `if` de quien orquesta, y para que anadir un miembro sin proyectarlo ponga `make check` en rojo en
  vez de caer en una rama por omision.

## Puertos

- Interfaces con `ABC` y `@abstractmethod`. Nada mas: sin implementacion por defecto, sin estado.
- El puerto declara lo que el dominio necesita, no lo que el adaptador sabe hacer.

## Politica: la logica pura vive aqui, no en aplicacion

Lo que es **regla exacta** -que paso viene despues de un resultado, cuando se agota un presupuesto- es
un objeto del dominio, no prosa de una skill ni un `if` en un caso de uso. Forma: dataclass frozen con
**su configuracion inyectada**, sin entrada/salida y sin conocer a nadie. La configuracion es un value
object normal: lo construye el entrypoint y entra como dato (ver `docs/conventions/application.md`).

- **Total o explicita**: un par de entrada que la politica no describe **lanza** su excepcion, no cae en
  una rama generica, para que se vea en el momento y no se confunda con "no pasa nada".
- **Devuelve un value object con el efecto entero**, no un booleano ni un `dict`: el paso siguiente, el
  estado en que queda y cuanto hay que esperar viajan juntos. Un consumidor que tuviera que recomponer eso
  volveria a tener politica repartida.
- **Se cubre desde fuera**, como todo el dominio: la tabla de entradas y salidas entra por el subcomando
  que la expone. No hay tests unitarios de dominio (`docs/conventions/testing.md`).

**Cuando ningun tick arregla algo, cero ticks es la cuenta correcta**: se cierra directo en vez de gastar
la ventana de gracia de una espera que no puede terminar bien. Y **la pregunta de mas solo se paga cuando
la primera lectura salio ambigua**: quien produce esa distincion es quien orquesta, no la politica, porque
una lectura que no separa dos casos no sabe cual tiene delante.

**La higiene del indice es politica.** Compara lo que hay en el indice con lo que el implementador
declaro y devuelve las ofensas; la tupla vacia es el indice limpio. Las decisiones que no son deriva:

- **Un artefacto prohibido lo es aunque este declarado.** La lista de prefijos prohibidos es un backstop,
  no una regla mas del allow-list: si lo pudiera levantar quien declara las rutas, no protegeria de nada.
- **Dos causas que no se arreglan igual no comparten contador.** Un control rojo es codigo que falla y lo
  puede arreglar otra vuelta del implementador; un rechazo de higiene es un informe incompleto -toco
  ficheros que no declaro- y no dice nada sobre si el codigo esta bien. Por eso lleva resultado propio,
  contador propio y presupuesto propio, y agotarlo cierra el run con un estado que nombra la higiene.
- **Fail-closed sin rama especial.** Sin nada declarado, todo lo que este en el indice cae en la ofensa
  general, que es lo que sale solo de la regla. Y **"nada staged" no es asunto de esta politica**: eso ya
  lo dice quien va a leer el diff, y reimplementarlo aqui seria un segundo sitio donde decidir lo mismo.

Las decisiones sobre los presupuestos tampoco son deriva, y estan aqui para que no se "arreglen" hacia el
lado facil. **Los valores concretos viven en el value object de configuracion, y de donde sale cada uno
esta en `docs/design-notes.md`**: aqui va la regla que los gobierna, no la medicion que los fijo.

- **Un numero por concepto, no uno por caso.** Una sola separacion minima entre ticks para todas las
  esperas, un solo tope para todas las clases de llamada a un proceso externo. Partirlos por caso serian
  numeros que nadie ha medido, y un numero sin medicion no es una regla: es una preferencia. Consecuencia
  aceptada a proposito: mover uno mueve todo lo que lo comparte.
- **El tope de espera acota la invocacion, no el run.** Agotarlo **no cierra** nada: deja el run abierto y
  persistido en su paso, diciendo que reinvocar es justo lo que toca.
- **La espera tiene un tope por clase de espera, y eso no rompe el bullet de arriba: lo aplica.** Esperar
  a una maquina y esperar a una persona **no son el mismo concepto**, aunque los dos se midan en segundos.
  A la maquina se la espera porque **esta trabajando**, y su tope existe para cazarla **colgada**: pasado
  el suyo, el numero ya no dice "ten paciencia" sino "algo va mal". A una persona se la espera porque
  **esta en otra cosa**, y ahi no hay nada que cazar: una respuesta que tarda media manana es el flujo
  funcionando, no una anomalia. Un solo numero obliga a elegir entre no detectar nunca una espera colgada
  y cerrar runs sanos porque alguien no estaba delante.
- **Y el contador se reinicia en cada paso, que es lo que hace honestos a esos topes.** Con un acumulador
  unico para todo el run, **el ultimo que espera paga lo que gastaron los demas**, y cuanto le queda
  depende de lo que una persona haya tardado antes: el tope dice una cosa y entrega otra. Un tope que solo
  se cumple si nadie se entretiene aguas arriba no acota nada.
- **El tope por llamada vive con los demas numeros aunque quien lo aplique sea un adaptador**, porque es
  el mismo tipo de dato: un numero medido con el que se acota una espera. Tenerlo aqui es lo que evita que
  cada adaptador se invente el suyo.
- **El descarte de una llamada al arnes no gasta reintento en ninguno de los pasos que la hacen.** Donde
  no se ha tocado el codigo es evidente; donde si, la llamada rota pudo dejar cambios sin comitear pero
  nada de eso llega al indice -un informe que no se puede leer nunca llega al paso que staggea-, asi que
  tampoco es un intento de la fase que un control o un juez lleguen a medir. Quien lo acota es el
  presupuesto de coste, que **si** cierra. Darle contador propio seria inventar una politica que ninguna
  medicion sostiene; dejarlo sin ningun cierre seria un bucle que paga una llamada por vuelta y no termina.
- **El presupuesto de coste impide la siguiente llamada; no tira la que ya se pago.** Un veredicto que
  aprueba nunca se convierte en agotado -entregar no cuesta harness-, y la llamada siguiente se corta
  **antes** de invocar, no despues de pagarla. Las dos comprobaciones conviven a proposito: la de despues
  cierra el bucle de descartes, la de antes es la que impide tirar una aprobacion.
- **La pregunta del coste se hace por llamada, no por el agregado**, y esa firma es load-bearing: se mira
  primero si **esa** llamada dejo medicion y solo despues se suma. Al agregado se le puede preguntar
  eternamente sin que conteste que no, porque lo que no se mide no suma.
- **Un gasto no medido cuenta como agotado**, no como cero: lo que no se puede sumar no se puede acotar.
  Es la misma eleccion fail-closed que una lectura indeterminada: el precio del falso positivo es una
  reinvocacion, y el del falso negativo es el bucle que el tope existe para cortar.
- **Lo que se cuenta son todas las llamadas del run.** Contar solo una parte abarataria el numero a costa
  de dejar sin cierre el bucle del descarte.

## Excepciones

- Nombradas por lo que pasa, no por donde.
- El catalogo es el de las excepciones **del dominio**. Un puerto que solo consume la infraestructura
  lleva la suya con el, declarado con su motivo en `docs/conventions/architecture.md`.
- Jerarquia cuando el consumidor necesita distinguir: se hereda de una comun cuando la interfaz de linea
  de comandos les da codigos de salida distintos, y quien no distingue captura la de arriba.
- Heredan del tipo que corresponde (`ValueError`, `OSError`), no de `Exception` a secas.

## Nada de `dict` crudo como valor de retorno de logica

Un `dict` que cruza dos funciones propias se lee con `.get()` en el consumidor, y ahi una clave mal
escrita y una ausente dan lo mismo. Los `dict[str, object]` que quedan son todos frontera de
serializacion, con la excepcion declarada de un registro durable que debe tolerar que un value object
crezca (`docs/conventions/infrastructure.md`): reconstruirlo aqui romperia con cualquier clave anadida,
renombrada o ausente entre versiones, y ninguna logica lo destructura.

## Antipatrones

- Un dataclass del dominio sin `frozen=True, kw_only=True, slots=True`.
- Un `to_dict()` en el dominio. **La traduccion al contrato externo vive en la frontera.**
- Una tupla de `str` como vocabulario cerrado.
- `Optional[Enum]` cuando lo que se modela es un estado ausente: eso es un miembro mas del enum.
- Un `dict` como valor de retorno de una funcion de logica.
- Pydantic en cualquier fichero de `domain/`.
