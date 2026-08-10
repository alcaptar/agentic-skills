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
| `tests/` | Los scripts de `skills/` y los **contratos entre `.md`**, que no tienen paquete donde vivir. |

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
  dos veces y mirando el juez que se le paso-, y que `Verdict` rechaza un `PASA` con un hallazgo `alta`
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

## Los contratos entre los `.md`

`make check` **tambien cubre los `.md`**, no solo el codigo. `tests/test_skill_contracts.py` compara los
contratos que hoy estan escritos dos veces:

- veredictos de `metrics.py`
- el vocabulario del log durable y el argv de `record`, entre el programa y `metrics.py`
- las herramientas que `src/slice_runner/` concede al juez vs las que declara su prompt
- las claves del hallazgo en la rubrica vs los `alias` de `FindingPayload`
- los veredictos y las severidades de la rubrica vs los que el programa acepta
- el criterio de degradacion sin subagentes, duplicado a proposito en `slice-runner` y `deploy-watch`

Cada test **extrae** el vocabulario de ambos lados y los compara, asi que reescribir las dos copias a la
vez pasa y tocar solo una falla. Si editas una skill y `make check` se pone rojo ahi, es que has movido
una mitad del contrato: mueve la otra.

Mide ademas dos cosas que no son dos copias de un vocabulario, sino una convencion contra el arbol:

**Que ninguna llamada a un proceso externo se lanza sin tope**
(`test_no_call_to_an_external_process_is_launched_without_a_cap`). Recorre el arbol sintactico de todo
`.py` que git siga en `src/slice_runner/`, `skills/*/scripts/`, `smoke/fixture/` y `tests/`, y falla por
cada llamada sin `timeout`. El programa lo cumple por construccion -lanza todo por el puerto `Process`, y
el tope se aplica en `LocalProcess`-, pero eso vale mientras nadie lance un proceso por su cuenta, y **la
prosa de `docs/conventions/infrastructure.md` no puede impedirlo**: cuando el tope estaba escrito solo
para las skills, quien juzgaba el programa no tenia con que fallarlo. Cazo cuatro llamadas de
`controles.py` y cuatro helpers de test, uno de ellos el que hace cumplir esta misma regla.

**El alcance es "toda llamada", asi que ni el arbol de test ni la forma de lanzar quedan fuera.** Los dos
son el mismo fallo: una vara que solo mira donde ya se cumple no mide nada.

- **`tests/` entra igual que el codigo.** Un helper de test que se cuelga cuelga `make check`, que es la
  vara entera del repo, y ademas es donde vivia el propio helper que hace cumplir la regla. Los tres que
  quedaban sin tope no se capan con un numero suyo: se lanzan por donde ya hay uno -`Git.run` para el
  `git`, `Real.process()` para los dos que arrancan un ejecutable-, que es lo mismo que impide que cada
  llamada elija su presupuesto.
- **Cuenta como lanzar un proceso `subprocess.run/call/check_call/check_output/Popen` y `os.system/popen`**,
  no solo el `subprocess.run` que este repo escribe hoy: keyear en la costumbre deja pasar las otras cinco
  formas sin tope ninguno. `Popen` y las dos de `os` **no aceptan `timeout`**, asi que no tienen forma
  capada y cuentan siempre como sin tope; quien necesite una de verdad, que la justifique al llegar.

Comprueba ademas que **toda ruta de este repo citada en los `.md` existe**
(`test_every_repo_path_cited_in_the_docs_still_exists`). Aqui no se enlaza con markdown: se citan rutas
en backticks, asi que lo que se valida es el token. Solo entran los que empiezan por un directorio de
primer nivel del repo, lo que deja fuera por construccion los nombres sueltos (`metrics.py`), las
rutas de otros repos y los patrones de rama (`slice/NN-name`). Dos ficheros no se escanean, cada uno por
lo que **es**: `docs/superpowers/specs/` (registro fechado, describe el arbol de su dia) y
`skills/slice-spec/references/observabilidad.md` (documenta rutas de repos ajenos).

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
