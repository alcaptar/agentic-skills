# Tests

## Como se mide todo

```bash
make check   # ruff check + ruff format + mypy strict + pytest; todo verde
```

Targets sueltos: `make test`, `make check-types`, `make check-style`, `make check-format`,
`make fix-linting`.

**Lanzalo siempre con `uv`.** El programa de `src/` depende de `pydantic`, asi que un
`python3 -m pytest` con el interprete del sistema pasa o falla segun lo que tengas instalado, y eso no
es una vara.

Para acortar el ciclo:

```bash
make test PYTEST_ARGS="-m 'not integration' --nf -x --tb=short --disable-warnings --color=no --no-header"
```

## El marcador `integration`

Un solo marcador, con un criterio que no se discute en review: **el test lanza un subproceso de
verdad** (`git`, un comando declarado, un ejecutable). Es lo que cuesta tiempo y lo que depende de la
maquina. Escribir en `tmp_path` no entra.

- Se aplica a la **clase** cuando el arbol nuevo la agrupa, y a la funcion en `tests/`, que todavia
  es function-based.
- `-m "not integration"` es el subconjunto rapido para el ciclo; **la suite entera sigue siendo la vara
  al cerrar una slice y en la integracion continua**. El marcador acorta el bucle, no lo que se exige.

## Los dos arboles, y por que

| | Que cubre |
|---|---|
| `src/slice_runner/tests/` | El programa. Co-localizado dentro del paquete, espejando las capas. |
| `tests/` | Los scripts de `skills/` y los contratos que no tienen paquete donde vivir -entre el programa y su documentacion, entre dos vocabularios del propio dominio, el puente con `metrics.py`, y los invariantes que escanean el arbol-. |

Lo compartido por los dos arboles vive en `src/slice_runner/tests/`:
`git_repo.py` -la clase `Git`, con la rama base, el helper de `git` y el repo recien inicializado- y
`real_process.py` -`Real.process()`, el `LocalProcess` con los `Budgets` del repo, por el motivo que
declara el apartado de Dobles-. **La direccion es esa** porque `src` entra
en el `pythonpath` y el directorio de `conftest` no, asi que `src/slice_runner/tests/` no puede consumir
de `tests/` y al reves si.

`Git.BASE_BRANCH` se fija explicitamente (`git init -b`) porque `init.defaultBranch` es config de la
maquina y el bloque de `diff-bundle` se cae en una que use `main`.

Lo compartido por la suite de `tests/` vive en `tests/conftest.py`: la fixture `repo` y los helpers de
escribir/stagear. No vuelvas a definirlos en un fichero de tests -hubo tres `_write` con firmas
distintas a la vez, y leer cualquier test obligaba a subir a la cabecera-.

## Forma de un test

- **Dentro de una clase**, agrupados por el comportamiento que fijan. Nunca funciones sueltas en el
  arbol nuevo.
- **Cero prosa**, igual que el codigo de produccion: el nombre del test es la frase.
- El nombre dice **que se garantiza y por que**, no que metodo se llama:
  `test_a_finding_without_a_line_leaves_the_key_out_instead_of_emitting_null`.
- Los helpers de un test son `@staticmethod` de su clase de test, o viven en un modulo compartido
  (`argv.py`), pero **nunca sueltos a nivel de modulo**.

## Object Mothers

**Los objetos de un test los construye un mother**, no el propio test:
`src/slice_runner/tests/mothers/{cosa}_mother.py`.

Un mother da defaults sensatos y deja que cada test nombre **solo lo que su caso cambia**, que es lo que
hace legible el assert. Sin ellos, el mismo diccionario de hallazgo se copiaba en dos ficheros de test
con valores distintos y ninguno decia por que.

Los metodos son **escenarios con nombre** (`without_line`, `passing`, `high_severity_finding`), no un
`create(...)` con todo por defecto: asi el test dice de que caso va sin leer los argumentos.

## Payloads grabados

`src/slice_runner/tests/payloads/` son sobres de llamadas **reales** a `claude -p` y a `gh`, guardados tal
como llegaron, y los carga `HarnessEnvelopeMother`. Es lo que hace que el test de frontera mida la carga
literal en vez de un modelo nuestro de ella, y de ahi salen datos que nadie escribiria a mano: las claves de
`usage`, el coste que cita `docs/conventions/domain.md`, un `permission_denials` vacio.

**Cuando cambia el contrato del contenido, se reescribe a mano el campo afectado -en `structured_output` y
en su copia dentro de `result`, que el harness escribe dos veces- en vez de regrabar el sobre.** Es
divergencia declarada de "grabados", y el motivo es que no hay nada que grabar: ninguna llamada vieja puede
traer el campo con la forma nueva, y regrabar arrastraria de paso el resto del sobre -el coste entre ellos-,
que es justo lo que otros tests fijan. Lo hizo la slice-09 con `left_out`, de frase a lista. Lo que **no**
autoriza es tocar el sobre: si lo que cambia es una clave del harness, hay que regrabar, porque ahi la forma
real es lo unico que se esta midiendo.

## Dobles

- **`create_autospec(X, spec_set=True, instance=True)`** para puertos sin estado.
- **Dobles con estado a mano**, en `src/slice_runner/tests/doubles.py`: `RecordedProcess` graba el
  `argv` y el `stdin` que recibio. Un `Mock` no sirve cuando el test necesita preguntar por lo que se le
  paso.
- **Un doble dobla lo que su nombre dice y nada mas.** La orden inyecta **un solo** `Process` al lector
  del diff y al juez, asi que `RealExceptTheJudge` y `UnrunnableJudge` lanzan `git` de verdad y solo
  interceptan al juez. Un doble que respondiera a cualquier `argv` con el sobre del juez haria que el
  lector leyese JSON donde espera un diff, y el test pasaria o fallaria por el motivo equivocado.
- **El doble de una conversacion entera contesta por `argv`, no por orden.** `ScriptedProcess` devuelve
  las salidas en el orden en que se le pasaron y sirve para **un** adaptador, donde el orden es parte de
  lo que se mide. Un run completo pasa por `gh`, `git`, el harness y el script de metricas, y ahi el orden
  es detalle de implementacion: `AnsweringByArgv` responde segun los tokens del `argv` y **lanza cuando
  nadie escribio respuesta** para un comando. Eso es lo que convierte "no repite el trabajo ya hecho" en
  algo comprobable: si el run implementase, el doble no tendria que contestar y el test se cae con el
  comando delante, en vez de pasar por casualidad.
- **El proceso de verdad tambien se pide a un sitio**: `Real.process()` (`real_process.py`, junto a
  `doubles.py`) da el `LocalProcess` con los `Budgets` del repo, y lo consumen **los dos arboles**. No es un
  doble -es el adaptador real- y esta ahi porque el tope por llamada entra por constructor y **no tiene
  default** (ver `docs/conventions/infrastructure.md`): sin un sitio comun, veintiuna llamadas de test
  elegirian cada una su presupuesto, que es la politica repartida que el default existe para impedir.
- **Nada de mockear value objects**: se usan instancias reales.
- El arrange **no se construye con la pieza bajo prueba**. El repo de un test de `GitDiffReader` se
  monta con `git` de verdad, no con el propio `GitDiffReader`.

## Que se testea y que no

- **Outside-in, y en este orden**: primero los tests de la **capa de aplicacion** con los puertos
  doblados, luego los de **infraestructura**. Lo de dentro del dominio se cubre **por ese camino**, no
  con tests propios.
- **No hay tests unitarios de dominio**, ni siquiera cuando el dominio tiene comportamiento. Que
  `Judge.also_reading` no muta el juez inyectado se comprueba en el test del caso de uso -ejecutandolo
  dos veces y mirando el juez que se le paso-, y que `Verdict` rechaza un `PASS` con un hallazgo `high`
  se comprueba en el test de
  frontera y en el de la orden, que es el camino real por el que llega un veredicto incoherente. La
  unica excepcion es un value object con validacion propia que no se pueda alcanzar de otra forma. Un
  test que solo comprueba que un dataclass guarda lo que le pasas mide el lenguaje, no el codigo.
- **Aplicacion**: puertos mockeados por constructor, y el assert sobre el **efecto observable** (que
  recibio el puerto, que devolvio el caso de uso), no sobre la llamada.
- **Frontera**: el assert es la **carga literal** que se envia o se recibe, no un modelo de ella
  reimplementado en el test. Comparar contra un modelo propio del formato es reescribir el mapeo y
  aprobarlo por construccion.
- **Antes de anadir un test, comprobar si el comportamiento ya esta cubierto.** Solo entra si aporta
  una dimension distinta.

## Los contratos de `tests/`, repartidos por lo que miden

`make check` **tambien cubre los `.md`**, no solo el codigo, pero no todo lo que vive en `tests/` mide
lo mismo, y cada cosa vive en el fichero que le corresponde -asi lo que dependa de un consumidor
condenado se retira sin tocar los demas-:

- **`test_skill_contracts.py`**: los contratos entre el programa y su documentacion viva -las skills,
  la rubrica del juez, el `README.md`-. Compara:
  - las herramientas que `src/slice_runner/` concede al juez vs las que declara su prompt
  - las claves del hallazgo en la rubrica vs los `alias` de `FindingPayload`
  - los veredictos y las severidades de la rubrica vs los que el programa acepta
  - el ejemplo, las reglas duras y el checklist de `validate` de `slice-spec/SKILL.md` entre si, y
    contra lo que el programa (`ParentBody`, `SubissueBody`, `GhRunRepository`, `IssueLabel`) lee
  - la ventana de gracia de la integracion continua, escrita en `Budgets` y en la prosa que la cita
  - el nombre del ejecutable instalado, igual en `pyproject.toml` y en cada doc que dice como lanzarlo
  - los codigos de salida del `README.md` vs `ExitCode`

  Cada test **extrae** el vocabulario de ambos lados y los compara, asi que reescribir las dos copias a
  la vez pasa y tocar solo una falla. Si editas una skill y `test_skill_contracts.py` se pone rojo, es
  que has movido una mitad del contrato: mueve la otra.

- **`test_domain_vocabulary_contracts.py`**: dos contratos del dominio del programa consigo mismo, sin
  ningun documento de por medio -que todo cierre de `RunState` distinto de `MERGED` proyecta a una
  etiqueta de `IssueLabel`, y que ninguna etiqueta del vocabulario carece de fuente (ver
  `docs/conventions/domain.md`)-.

- **`test_metrics_bridge_contract.py`**: el ultimo puente con `metrics.py`, declarado en
  `docs/conventions/infrastructure.md` -los veredictos del vocabulario durable del programa vs los de
  `metrics.py`, y la fila que construye el programa pasada por el lector real del script
  (`Fila.from_row`)-.

- **`test_pipeline_invariants.py`**: seis invariantes que escanean el arbol en vez de comparar dos
  copias de la misma prosa:

  **Que ninguna llamada a un proceso externo se lanza sin tope**
  (`test_no_call_to_an_external_process_is_launched_without_a_cap`). Recorre el arbol sintactico de todo
  `.py` que git siga en `src/slice_runner/`, `skills/*/scripts/`, `smoke/fixture/` y `tests/`, y falla por
  cada llamada sin `timeout`. El programa lo cumple por construccion -lanza todo por el puerto `Process`,
  y el tope se aplica en `LocalProcess`-, pero eso vale mientras nadie lance un proceso por su cuenta, y
  **la prosa de `docs/conventions/infrastructure.md` no puede impedirlo**: cuando el tope estaba escrito
  solo para las skills, quien juzgaba el programa no tenia con que fallarlo.

  **El alcance es "toda llamada", asi que ni el arbol de test ni la forma de lanzar quedan fuera.** Los
  dos son el mismo fallo: una vara que solo mira donde ya se cumple no mide nada.

  - **`tests/` entra igual que el codigo.** Un helper de test que se cuelga cuelga `make check`, que es
    la vara entera del repo, y ademas es donde vivia el propio helper que hace cumplir la regla. Los tres
    que quedaban sin tope no se capan con un numero suyo: se lanzan por donde ya hay uno -`Git.run` para
    el `git`, `Real.process()` para los dos que arrancan un ejecutable-, que es lo mismo que impide que
    cada llamada elija su presupuesto.
  - **Cuenta como lanzar un proceso `subprocess.run/call/check_call/check_output/Popen` y
    `os.system/popen`**, no solo el `subprocess.run` que este repo escribe hoy: keyear en la costumbre
    deja pasar las otras cinco formas sin tope ninguno. `Popen` y las dos de `os` **no aceptan
    `timeout`**, asi que no tienen forma capada y cuentan siempre como sin tope; quien necesite una de
    verdad, que la justifique al llegar. Lo pin `test_the_scan_counts_as_uncapped_every_way_of_launching_a_process_not_only_subprocess_run`,
    que fija sobre una fuente sintetica que las seis formas cuentan y no solo la que escribe hoy.

  Comprueba ademas que **toda ruta de este repo citada en los `.md` existe**
  (`test_every_repo_path_cited_in_the_docs_still_exists`). Aqui no se enlaza con markdown: se citan
  rutas en backticks, asi que lo que se valida es el token. Solo entran los que empiezan por un
  directorio de primer nivel del repo, lo que deja fuera por construccion los nombres sueltos
  (`metrics.py`), las rutas de otros repos y los patrones de rama (`slice/NN-name`). Tres entradas no se
  escanean, cada una por lo que **es**: `docs/superpowers/specs/` (registro fechado, describe el arbol
  de su dia), `skills/slice-spec/references/observabilidad.md` (documenta rutas de repos ajenos) y
  `playground/tasks/` (entrada congelada de un experimento, no se actualiza).

  Y que **el fixture del smoke se lintea con la misma vara que la raiz**
  (`test_the_smoke_fixture_is_linted_with_the_same_yardstick_as_the_repo`): el mismo `select` de
  `[tool.ruff.lint]`, porque la fixture es el arbol que el runner slicea de verdad en el smoke, y una
  vara mas laja ahi le daria un pase que no vale nada.

  Y que **ninguna llamada que escribe con el arnes en `conduct_slice.py` escapa al descarte-y-reintento**
  (`test_no_call_that_writes_with_the_harness_in_conduct_slice_escapes_the_discard_and_retry_treatment`).
  Recorre el arbol sintactico de ese fichero y falla si algun `self._x.y(...)` no anidado en un `try`
  cuyo `except` capture `MeasuredCallError` no esta en `_KNOWN_NOT_HARNESS_WRITING`, y si el total de
  llamadas que si cuentan no es exactamente tres: la prosa de `docs/conventions/domain.md` sobre el
  descarte del juez no podia impedir que las otras dos llamadas siguieran matando el run entero, igual
  que le paso al tope por llamada antes de que existiera su propio escaneo.

  **La lista nombra lo que NO escribe con el arnes, no lo que si.** Una allowlist de las tres llamadas
  conocidas no puede fallar ante una cuarta anadida sin tratamiento -sale un `total` que sigue en 3-, asi
  que el escaneo invierte el criterio: nombra cada `self._x.y(...)` de hoy que **no** es el arnes, y
  cualquier llamada que el escaneo no reconoce cuenta como si lo fuera. El coste es la propia lista -unas
  treinta entradas que hay que ampliar si aparece un `self._x.y(...)` legitimamente no relacionado con el
  arnes-, y lo fija
  `test_a_self_call_not_named_safe_is_treated_as_harness_writing_even_if_the_scan_has_never_seen_it` sobre
  una fuente sintetica, igual que el meta-test del tope por llamada: una llamada a un puerto que el
  escaneo nunca ha visto cuenta como sin tratar por defecto, en vez de pasar en silencio como le pasaba a
  la allowlist que sustituye.

## Antipatrones

- Un test como funcion suelta en el arbol nuevo.
- Un comentario o un docstring en un test.
- Un test que lanza un subproceso y no lleva `@pytest.mark.integration`.
- Construir un objeto de dominio a mano en el test cuando hay mother, o duplicar en el test las
  constantes del mother.
- Un helper de test suelto a nivel de modulo, o repetido en dos ficheros.
- Arrange construido con la pieza bajo prueba.
- Assert contra un modelo del formato reimplementado en el test, en vez de contra la carga literal.
- Un test de dominio. Lo que hay dentro se cubre desde aplicacion y desde la frontera.
