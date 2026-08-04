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
- Un codigo de salida distinto de cero **es un dato**, no una excepcion: se lanza el proceso con
  `check=False` y el adaptador interpreta, porque el motivo esta en `stderr` y una excepcion lo borra.

## Entrypoints

- Una clase (`Cli`), con `main` como `@classmethod`, que `__main__.py` invoca.
- **Es el unico sitio que monta el grafo de dependencias**: elige los adaptadores concretos y los
  inyecta. No hay contenedor de inyeccion: hay un adaptador por puerto, y la costura de test la da el
  constructor.
- **Mapea las excepciones tipadas del dominio a codigos de salida**, con `IntEnum`. La respuesta va a
  `stderr` y el resultado a `stdout`, siempre separados: hay tests que comprueban que un fallo no
  escribe nada en `stdout`.
- Los codigos de salida son contrato con quien invoca el programa: se documentan y no se reordenan.

## Antipatrones

- Un `cast` para callar a `mypy`.
- `extra="ignore"` en un modelo de frontera. **Una clave desconocida tiene que romper.**
- `strict=True` a nivel de modelo.
- Un `ValidationError` de Pydantic escapando de la capa.
- Duplicar en el programa una regla que ya vive en `controles.py` **sin declararlo con su motivo** en la
  seccion de adaptadores: la duplicacion declarada es la decision de esta capa, la silenciosa es el fallo.
- `check=True` al lanzar un proceso cuyo `stderr` lleva el motivo del fallo.
- Un adaptador que ademas decide politica (reintentos, presupuesto).
