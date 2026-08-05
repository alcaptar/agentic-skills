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
en ingles. El contrato de `explain` (`RunPayload`, `TransitionPayload`) **lo fijamos nosotros y esta en
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
- **`LocalCorpus` y `LocalSkillLibrary` resuelven cada uno la raiz de configuracion de la herramienta**
  (`CLAUDE_CONFIG_DIR` o `~/.claude` expandido), en vez de compartir un objeto que la diga. Es una
  duplicacion declarada de cuatro lineas: lo que comparten no es una regla del programa sino **la
  convencion de Claude Code sobre donde vive su configuracion**, y cada adaptador cuelga de ahi una cosa
  distinta -uno lee los dos arboles de la vara, el otro anexa el par (diff, veredicto) de cada
  verificacion a `slice-runner/corpus/verdicts.jsonl`-. Su casa natural es un objeto propio de esa
  convencion, y se hara cuando exista un tercer adaptador que la necesite; hasta entonces, extraerla
  obligaria a renombrar la constante por la que **todos** los tests que ejecutan una verificacion
  mantienen la suite fuera del home real, que es mas superficie tocada que la duplicacion que ahorra.
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
- Un codigo de salida distinto de cero **es un dato**, no una excepcion: se lanza el proceso con
  `check=False` y el adaptador interpreta, porque el motivo esta en `stderr` y una excepcion lo borra.
- **`GhForum` reutiliza `GhCommandFailedError` de `run_repository.py`** para un exit distinto de cero de
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
  3. **El encabezado de la intencion es fijo**, y el paso 8 obliga a `## Intencion (inferida del issue, no
     declarada)` cuando la intencion no venia declarada. Quien sabe si venia declarada es, otra vez, quien
     leyo el issue -no este modelo-, asi que el interruptor entra con el conductor.

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
