# Capa de infraestructura

Adaptadores de los puertos, modelos de frontera y entrypoints. Es la unica capa que sabe que hay un
subproceso, un `git` o un sistema de ficheros al otro lado.

## Lo que llega de fuera se valida al entrar

Sin excepcion, y sin `cast`: un `cast` no comprueba, solo calla a `mypy`.

- **En la frontera del programa, el esquema es Pydantic**, un `BaseModel` por concepto, sobre una base
  comun que fija `extra="forbid"`, la traduccion del `ValidationError` y el volcado al contrato.
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

### Un formato ajeno de vocabulario abierto se valida por proyeccion

Cuando lo que llega **no es un contrato que este programa defina ni del que dependa una version fija**
-la transcripcion de una sesion del harness, el JSON de una herramienta externa-, exigir
`extra="forbid"` sobre el objeto entero rompe la lectura con cada campo que el otro lado anada, que es
justo la funcion que ese lector tiene. La regla se mantiene invirtiendo el orden: se **proyecta a mano**
un diccionario con exactamente las claves que se consumen y se valida esa proyeccion, que sigue siendo
`extra="forbid"`. Una clave que si declaramos conocer y que falta o llega con el tipo equivocado sigue
rompiendo.

Distinguir los dos casos es lo que hace legitima la excepcion: un fichero que **este programa escribe
entero**, o una salida documentada de la que dependemos, se valida completo. Y una linea que no es JSON
es corrupcion, no una variante mas de un vocabulario abierto: se lanza en vez de tragarse.

### `strict=True` por campo, no a nivel de modelo

A nivel de modelo rompe el parseo: en modo estricto un `StrEnum` deja de aceptar su propia cadena y un
modelo anidado deja de aceptar un `dict`.

Por campo, donde la coercion es peligrosa: un booleano que dice si algo fallo -sin estricto, la cadena
`"no"` se convierte en `False`, o sea el otro lado declarando el fallo y el programa leyendo que no
hubo- y un numero que puede llegar como texto.

La vara para decidir: **¿que valor equivocado pasaria por bueno, y que decision tomariamos con el?**
Si la respuesta es "ninguna que importe", laxo vale.

### El esquema se emite plano

`JsonSchema.flat` resuelve los `$ref` y borra los `title`. Dos motivos: la **forma plana es la unica
medida de verdad** contra un `claude -p` real, y los `title` solo gastan tokens del prompt. Hay un test
que falla si vuelve a colarse una referencia.

### Un esquema que viaja en un prompt declara **un solo campo**

El harness pierde la frontera entre parametros cuando el modelo emite la llamada a `StructuredOutput`:
el primero se traga su propio cierre y todo lo que venga detras, asi que el segundo llega como texto
dentro del primero y el validador lo reporta como **campo requerido que falta**. La medicion que lo
fijo esta en `docs/design-notes.md`.

Y el dano no acaba en el rechazo. Tras dos o tres, el modelo minimiza para aislar el fallo, el informe
minimo si valida, y **se publica relleno con la firma del programa**. Por eso la regla es la forma del
esquema y no una instruccion mas en el prompt: un brief que pida el campo que falta no puede arreglar
una frontera que se pierde en el transporte.

Consecuencia: el modelo declara un unico campo y el adaptador **publica lo que llega en vez de
componerlo**. Se pierde que el programa garantice las secciones; se gana que no haya forma de fallar la
forma.

**El `description` no es un `title` y por eso se queda.** Un `title` repite el nombre del campo, asi que
solo gasta; un `description` dice **que se pone ahi**, y es lo unico que el agente tiene delante en el
momento de emitir -el brief queda cientos de lineas mas arriba, y `--json-schema` no restringe la
generacion, solo valida despues-. **Consecuencia: donde el esquema describe un campo, el prompt no lo
vuelve a describir**, y hay test que lo mide. Solo lo llevan los payloads cuyo esquema viaja en un
prompt; los que declaran esquema para un almacen durable no lo necesitan, porque ahi nadie emite contra
el esquema.

### El `alias` traduce; cuando no hay nada que traducir, no se escribe

Un contrato que fijamos nosotros y esta en ingles ya tiene la clave en el nombre del campo, y un `alias`
identico solo seria ruido que hay que mantener en dos sitios. `by_alias=True` cae en el nombre del campo
cuando no hay alias, con lo que el esquema, la validacion y la salida siguen saliendo de un solo sitio,
que es lo que la regla protege.

### Un campo que se llama como un builtin rompe las anotaciones de la clase

Pydantic evalua las anotaciones **con el namespace de la clase**, asi que en un modelo con un campo
llamado como un builtin -`type`, porque el otro lado trae esa clave- una anotacion que use ese builtin
explota al importar el modulo. Por eso lo que necesite el builtin **entra como argumento** y no como
`ClassVar` de la clase. Ni el `strict` ni el `from __future__ import annotations` cambian nada aqui.

### Cuidado con `TC002` y las anotaciones de Pydantic

Pydantic resuelve las anotaciones de campo **en runtime** al crear el modelo. Un tipo que `ruff` mueva
a `if TYPE_CHECKING:` deja el modelo *not fully defined* y **revienta en la primera validacion, no al
importar**: un smoke que solo importe el modulo lo da por bueno. Lo evita
`runtime-evaluated-base-classes` en `pyproject.toml`, no la disciplina de quien escribe.

## Adaptadores

- Implementan un puerto y nada mas. **El modulo se llama como la implementacion**, no como el puerto,
  asi que el par puerto/adaptador se lee en el nombre y caben dos implementaciones sin renombrar nada.
- **El programa no importa nada de `skills/`.** Es autocontenido: lanza los procesos el mismo por su
  puerto y valida lo que recibe con sus propios modelos. **Acoplar el flujo nuevo al viejo para ahorrar
  duplicacion sale mas caro que la duplicacion**, asi que las copias que eso genera se declaran y se
  miden con un contrato en vez de eliminarse.
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
  segunda copia que nadie compara, y el programa **no lee `.md` de agente**.
- **Lo que no cambia entre invocaciones es constante; los datos de la slice los compone la invocacion.**
  **Aplicacion no compone texto de prompt**: pasa objetos del dominio y es la frontera la que decide
  como se escriben. Y un prompt **cierra con el dato**, nunca con la metodologia: lo variable al final es
  lo que evita que un delimitador tenga que sobrevivir a su propio contenido.

  **La forma de una lista se extrae cuando deja de ser un parecido y pasa a ser invariante.** Cada
  prompt es un contrato con un agente distinto y nada exige que se parezcan, asi que compartir la forma
  entre dos puede ser coincidencia; cuando la repite un consumidor mas, ya no lo es. **Y una condicion
  asi, escrita, se ejecuta cuando se cumple**: la que nadie ejecuta ensena que este fichero es opinion.
- **Un invocador que no tiene issue delante no llena los mismos campos que el conductor**, asi que la
  rubrica **describe la carga en vez de prometerla llena**: dice que los campos viajan siempre, que
  pueden venir vacios y que un campo vacio es un insumo que no ha llegado -que el agente reporta como
  falta de dato, no como item conforme-. Lo que **no** se hace es escribir que esos insumos no existen.
  Y los campos entran **sin default**, que es lo que obliga a llenarlos en vez de heredar el vacio en
  silencio.
- **Una fuente declarada viaja con su contenido citado por su ruta, y quien lo lee es un adaptador
  compartido, no cada invocacion por su cuenta.** Es la misma regla de la lista que deja de ser parecido
  y pasa a ser invariante, aplicada a lo que citan.
- **Lo que vive bajo el worktree se lee por el puerto de proceso, nunca abriendolo por nuestra cuenta.**
  Es la unica costura documentada del entrypoint: un worktree de test no es un directorio real en disco,
  y toda la suite que lo dobla asume que leerlo pasa por ese puerto. Los adaptadores que leen la raiz de
  configuracion de la maquina son otra familia y si abren ficheros.
- **La raiz de configuracion de la herramienta la resuelve un objeto propio** (la variable de entorno si
  esta puesta, o la raiz por omision expandida, con la variable vacia tratada como ausente). La comparte
  todo adaptador que necesite saber donde vive esa configuracion, porque lo que comparten no es una regla
  del programa sino **la convencion de la herramienta**.
- **Un adaptador que escribe a disco fuera del camino de error no captura su `OSError`.** Sale del
  programa sin mapear, aunque eso colapse con un codigo de salida que significa otra cosa. Se acepta
  porque la alternativa es peor: **decidir aqui que hacer con el fallo de escritura seria inventar una
  politica que ningun criterio pidio**, y un adaptador que decide politica es antipatron declarado de esta
  misma capa. Cuando se cierre, se cierra **decidiendo la politica**, no capturando el `OSError` a
  escondidas.
- **Un adaptador que invoca el harness agrupa su telemetria en un objeto**, por el mismo motivo declarado
  para agrupar dependencias en `docs/conventions/application.md`, y solo la telemetria: lo que cada
  adaptador usa por su cuenta sigue listado suelto. **La linea, para que no se amplie por precedente:**
  esto es de los adaptadores que invocan el harness y dejan constancia de la llamada.
- **El rastro de una llamada lo escribe el adaptador que la hace, no el caso de uso**, y se anexa en
  cuanto la respuesta parsea y **antes** de entrar en el bloque que la mide. Dos motivos, y el segundo es
  el que cierra la decision:

  1. **El unico sitio que ve la respuesta de todas las llamadas es el adaptador.** Una llamada que muere
     dentro del bloque que mide es justo la conversacion que se quiere leer, y en aplicacion no queda
     nada de ella.
  2. **Al caso de uso ya no le cabe, y eso dice lo mismo.** Con un puerto mas suelto la firma salta el
     tope del linter, y empaquetarle los argumentos es del conductor y solo de el (ver
     `docs/conventions/application.md`). Que el linter lo cace ahi es la senal de que escribir el rastro
     es de la capa que ve la respuesta, no de la que orquesta.

  Consecuencia aceptada: una respuesta que **no** parsea no deja rastro -no hay identificador que
  escribir-. Por eso el identificador de sesion es campo **obligatorio** y no opcional: una llamada sin
  identificador no se puede volver a encontrar, que es el fallo que este rastro existe para cerrar.
- **Los almacenes durables viven bajo un mismo directorio y un mismo patron de nombre**, para que un solo
  criterio contesta "donde vive esto".

  **Un almacen se parte en ficheros hermanos cuando lo que pesa y lo que se consulta a menudo no son lo
  mismo**, unidos por una clave y un sello para poder juntarlos. Sin eso, contar lo ligero obliga a leer
  lo pesado.

  **Los payloads de un almacen durable declaran su esquema**, reusando el mismo emisor plano que los que
  viajan en un prompt. Es lo que deja preguntar que campos trae una fila sin abrir el fichero.
- **El registro durable lo escribe el programa el mismo**, con el mismo patron que los demas almacenes y
  un payload de frontera que traduce el dominio a las claves del log. **No delega esa escritura en un
  script fuera de su paquete**: seria una dependencia fisica con codigo que no es referencia.

  Consecuencia aceptada: el vocabulario del cierre existe dos veces -en ingles dentro del programa y con
  las palabras del log en la frontera-, con un `match` exhaustivo entre las dos, y la duplicacion la
  **mide** un contrato que compara los conjuntos de ambos lados y pasa la fila por el lector real del
  script. Una clave renombrada solo se veria al cerrar una slice, que es justo el momento en que un fallo
  pierde la fila.

  **Solo lo que ese script lee por clave literal se queda en castellano; el resto habla el idioma del
  codigo.** El lado que **relee** el log tolera las dos formas con `validation_alias`, para que una fila
  ya escrita con la forma vieja se siga agregando.
- **Un registro que debe tolerar que un value object crezca no nombra sus campos.** La regla general
  existe para que un contrato que cambia de forma rompa donde se declara; aqui se invierte a proposito
  cuando el criterio que trajo la fila pide justo lo contrario: que anadir un campo no obligue a tocar el
  registro. Nombrar cada campo volveria a acoplar la fila durable a la forma exacta de ese value object.
- **El programa no escribe ningun numero que no venga del harness.** Hay puerto de reloj, pero lo que ese
  reloj lee es del programa y no de lo que la llamada costo. De ahi que el gasto sea un value object que
  distingue "todavia no se ha medido nada" de "cero medido": con nada medido, la clave no se escribe.

  **Y todas las llamadas cuentan, tambien las que acaban en excepcion** -si no, una fila con varios
  descartes escribiria un coste sistematicamente por debajo-: una vez parseada la respuesta, el gasto
  cuelga de cualquier error medido que salga del bloque, y solo esta capa puede hacerlo porque es la
  unica que la ve. Si no llego a parsearse no hay nada que colgar: eso es "no medido", no un cero.

  **El gasto sobrevive a la invocacion**: se acumula por invocacion pero se siembra con lo que trae el
  estado persistido y se escribe de vuelta en cada paso que lo cambia, asi que una slice reinvocada sigue
  viendo su presupuesto entero y la fila que cierra el run suma todas las invocaciones.
- **Una pieza del flujo se apaga por el cableado, con un adaptador que no hace nada, y quien lo decide
  es el entrypoint.** Un adaptador mudo implementa el puerto y no lanza nada; el entrypoint lo inyecta
  en lugar del real. **Lo que se apaga es el cableado, no el flujo**: el caso de uso sigue llamando al
  puerto en el mismo sitio y con los mismos datos, asi que reencender es cambiar la linea que lo
  inyecta. Consecuencia aceptada: el adaptador real se queda vivo y sin cablear, sostenido solo por su
  test de frontera.

  **Lo que se mide es que el proceso no se lanza, no que el adaptador mudo no haga nada** -un test suyo
  mediria el lenguaje, ver `docs/conventions/testing.md`-: el doble del puerto revienta con el `argv`
  delante si alguien vuelve a cablear el real.
- Un codigo de salida distinto de cero **es un dato**, no una excepcion: se lanza el proceso con
  `check=False` y el adaptador interpreta, porque el motivo esta en `stderr` y una excepcion lo borra.

  **Pero un codigo que no distingue los casos no clasifica nada por si solo: entonces se clasifica la
  salida.** Cuando una herramienta sale distinto de cero para varios estados que hay que separar, el
  codigo es un dato que no dice nada y el unico que decide es `stdout`.

  **Y un codigo distinto de cero con `stderr` no vacio es el propio comando fallando**, que se distingue
  de una respuesta que si llego pero no se pudo interpretar. Son dos causas y llevan excepcion distinta,
  las dos del **dominio** -aplicacion las captura, asi que tienen que vivir donde pueda importarlas- y
  las dos traducidas al miembro del vocabulario que dice cual fue. **Esto no es permiso general para
  propagar cualquier fallo de lectura**: el vocabulario sigue teniendo miembros para lo que se clasifica
  sin ambiguedad y sin excepcion, y esos siguen sin motivo porque no son un fallo, son una lectura
  valida. Lo que gana la clasificacion es un porque que un `except` generico fundiria en un valor mudo.
- **Dos adaptadores de la misma herramienta comparten su excepcion**, que vive donde la necesito el
  primero que la tuvo: es el mismo fallo -un comando de esa herramienta que sale mal- y el acoplamiento
  declarado sale mas barato que una tercera copia. Su casa natural es un modulo de frontera compartido, y
  se hace cuando exista un tercer adaptador de esa herramienta.
- **Ninguna llamada a un proceso externo se lanza sin tope, y el tope no lo elige el adaptador.** El
  adaptador recibe el presupuesto por constructor y lo pasa como `timeout`; el numero y su motivo viven
  en `docs/conventions/domain.md`, que es lo que separa "aplicar un tope" -trabajo de esta capa- de
  "decidir cual" -politica, y por eso el constructor **no tiene default**: un adaptador de proceso sin
  presupuesto no compila-. Como el programa entero lanza procesos por ese puerto y **solo** por el, el
  tope se aplica en un sitio y no hay adaptador que se lo salte.

  Al agotarse se **falla en cerrado**: se mata al hijo y el adaptador traduce el timeout a su excepcion
  -que vive con el puerto, por el motivo de `docs/conventions/architecture.md`-. Lo que el proceso
  hubiera escrito ya **se descarta**: media respuesta no es una respuesta. No hay reintento aqui:
  reintentar es politica, y esta capa no la decide.
- **Dos campos que tienen que concordar dejan representable el estado que no debe existir; uno solo lo
  hace imposible.** Cuando una bandera dice lo mismo que la no-vacuidad de un dato, la bandera se retira
  y se deriva: asi una invocacion que muera a medias no puede reanudar afirmando algo que no tiene.
- **El cuerpo de la pull request lo compone un modelo de frontera**, que fija sus encabezados y su orden.
  Se quedan en castellano: son **contenido del artefacto que lee una persona**, en el idioma del issue,
  no identificadores.

  **La pull request nace lista para revisar, y eso no afloja el control humano.** Lo que hace que el
  merge lo decida una persona es que el programa **no mergea**: se para y termina. Un borrador no anade
  esa garantia y si anade un paso manual que nada recuerda.
  - **Se asigna a quien esta autenticado**, que es quien conduce el run y quien tiene que mergear. Se
    declara con la forma que resuelve la herramienta en la misma llamada, no preguntando antes quien
    eres: una llamada que se puede ahorrar es una llamada que puede fallar.
  - **El commit acredita como co-autor al harness que escribio el codigo**, en un objeto de frontera
    propio y no como una cadena pegada al titulo, porque el **asunto** del commit y el **titulo** de la
    pull request dejan de ser lo mismo en cuanto uno de los dos crece. Lo que **no** se hace es anadirlo
    como asignado: solo se puede asignar a colaboradores del repo, asi que seria una llamada que falla o
    se ignora en silencio.

  Estas decisiones sobre el cuerpo **no tienen test de contrato**: no hay vocabulario que extraer de un
  cuerpo en prosa, asi que estos parrafos son lo unico que las sostiene.

  1. **La referencia que cierra el issue depende del formato**, no de la costumbre: con una subissue por
     slice la pull request si cierra su issue y la plataforma lo hace sola al fusionar; con un issue por
     feature entera eso seria mentira.
  2. **Confirma que los criterios se cumplieron en vez de reproducirlos.** Reproducirlos le da a quien
     revisa lo que ya sabe -los declara la subissue- y le quita el sitio al *por que*, que es todo el
     trabajo de este cuerpo. Y **donde vive cada test** el programa no lo sabe: el informe del
     implementador trae rutas con su tipo, no un mapa de criterio a test, asi que escribirlo seria
     inventarlo.
  3. **La deuda aceptada es lo que el implementador declaro haber dejado fuera, junto a los hallazgos que
     sobrevivieron a la vuelta con la que el juez dejo pasar la slice.** Llegan como lista y se
     transportan sin adivinar donde corta una frase; una lista vacia significa "nada quedo fuera", y la
     seccion solo se emite cuando trae bullets. Los de vueltas anteriores **no** entran: pueden haberse
     corregido despues, y darlos por aceptados seria mentir.

  **La intencion inferida se declara en el encabezado.** Cuando la subissue no la trae, el encabezado lo
  dice; cuando la trae, va plano. La decision es del **formato**, y por eso vive en el modelo y no en
  quien conduce: el dato -declarada o no- ya viaja en lo que le llega. Lo que el programa **no** hace es
  inventarse la prosa que falta: presentar como intencion algo que nadie escribio es justo lo que ese
  encabezado existe para impedir.

## Entrypoints

- Una clase, con `main` como `@classmethod`, que el modulo ejecutable invoca y que `[project.scripts]`
  declara como el ejecutable instalado.
- **Es el unico sitio que monta el grafo de dependencias**: elige los adaptadores concretos y los
  inyecta. No hay contenedor de inyeccion: hay un adaptador por puerto, y la costura de test la da el
  constructor. El grafo entero del conductor se monta sobre **un solo** puerto de proceso, que es tambien
  la unica costura que necesita su test: doblarlo basta para conducir un run sin tocar ninguna
  herramienta externa, y lo que el run hizo o no hizo se lee en el `argv` que recibio.
- **Mapea las excepciones tipadas del dominio a codigos de salida**, con `IntEnum`. La respuesta va a
  `stderr` y el resultado a `stdout`, siempre separados: hay tests que comprueban que un fallo no
  escribe nada en `stdout`.
- Los codigos de salida son contrato con quien invoca el programa: **se documentan en la tabla del
  `README.md`** -que un test de contrato compara con el `IntEnum`-, se anaden al final y no se
  reordenan.
- **Un codigo por decision de quien invoca, no uno por excepcion.** La vara para decidir si hace falta
  uno nuevo es: ¿que hace distinto quien lo recibe? Todo lo que significa "el mundo fallo, el estado
  persistido sigue bueno" comparte uno solo, y no se parte por clase de excepcion. Una llamada muerta en
  su tope si lleva el suyo, porque reinvocarla a ciegas volveria a pagar el tope entero.

  **Y se mapea donde el puerto de proceso se inyecta por constructor**, no en `main`: arriba quedaria sin
  costura con la que probarlo.

  **Cuando el reparto pasa del tope de `return` que mide el linter, va en un `match` en un sitio** en vez
  de en una cadena de `except`, y **la rama generica es la de "el mundo fallo, el estado sigue bueno" a
  proposito**, que es literalmente la regla de arriba. Lo que puede llegar se acota, y lo que no este ahi
  sigue saliendo sin capturar.
- **La proyeccion del dominio al codigo de salida es un `match` exhaustivo sin rama generica**: un
  miembro nuevo rompe en `mypy` en vez de caer en un valor por omision. Una rama que no se puede
  alcanzar se agrupa con el lado fail-closed.
- **Una invocacion que el parser rechaza sale con su codigo de uso, y `--help` con el de exito.**
  `argparse` levanta `SystemExit(2)` para las dos cosas, y ese `2` puede estar reservado a otra cosa en
  el contrato: hay que traducir ese `SystemExit` mirando su codigo, que es la unica forma de distinguir
  la ayuda del error de uso sin reescribir `argparse`.

## Antipatrones

- Un `cast` en la frontera.
- Un modelo de frontera sin `extra="forbid"`.
- `strict=True` a nivel de modelo.
- Un helper de mapeo en el caso de uso en vez de en el modelo.
- Un `ValidationError` de Pydantic saliendo de la capa.
- Un adaptador que decide politica -reintentos, presupuestos, que hacer con un fallo-.
- Una llamada a un proceso externo sin tope, o un adaptador que elige el suyo.
- Un esquema que viaja en un prompt con mas de un campo.
